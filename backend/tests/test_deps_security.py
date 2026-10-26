import inspect
import os
import sys

import pytest
from fastapi import HTTPException


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.deps import get_download_user, verify_webhook_secret
from app.api.v1.catalogs import _webhook_url as catalog_webhook_url
from app.api.v1.personalized_resources import _webhook_url as personalized_webhook_url
from app.api.v1.resources import _webhook_url as resource_webhook_url
from app.core.config import Settings, settings
from app.core.security import create_token, decode_token
from starlette.requests import Request


@pytest.mark.asyncio
async def test_verify_webhook_secret_production_mode_empty_secret_raises_503(monkeypatch):
    monkeypatch.setattr(settings, "WEBHOOK_SECRET", "")
    monkeypatch.setattr(settings, "DEBUG", False)

    with pytest.raises(HTTPException) as exc_info:
        await verify_webhook_secret()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == 50300
    assert "Webhook secret 未配置" in exc_info.value.detail["message"]


@pytest.mark.asyncio
async def test_verify_webhook_secret_debug_mode_empty_secret_allowed(monkeypatch):
    monkeypatch.setattr(settings, "WEBHOOK_SECRET", "")
    monkeypatch.setattr(settings, "DEBUG", True)

    # Should not raise in DEBUG mode
    await verify_webhook_secret()


@pytest.mark.asyncio
async def test_verify_webhook_secret_matching_secret(monkeypatch):
    monkeypatch.setattr(settings, "WEBHOOK_SECRET", "my-secret")

    # Wrong secret -> 401
    with pytest.raises(HTTPException) as exc_info:
        await verify_webhook_secret(x_webhook_secret="wrong")
    assert exc_info.value.status_code == 401

    # Correct secret -> passes
    await verify_webhook_secret(x_webhook_secret="my-secret")


def test_get_download_user_signature_has_no_query_token():
    sig = inspect.signature(get_download_user)
    assert "token" not in sig.parameters
    assert "credentials" in sig.parameters


def test_production_weak_jwt_secret_rejected_on_token_ops(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)

    for weak_key in ("", "duagent-jwt-secret-change-in-production", "replace-with-jwt-secret"):
        monkeypatch.setattr(settings, "JWT_SECRET_KEY", weak_key)

        with pytest.raises(HTTPException) as exc_info:
            create_token("user-1", "student")
        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["code"] == 50300
        assert "JWT secret 未安全配置" in exc_info.value.detail["message"]

        with pytest.raises(HTTPException) as exc_info:
            decode_token("some.fake.token")
        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["code"] == 50300
        assert "JWT secret 未安全配置" in exc_info.value.detail["message"]

    # Secure key passes
    strong_key = "a" * 32
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", strong_key)
    token = create_token("user-1", "student")
    assert isinstance(token, str)
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "user-1"


def test_debug_mode_allows_default_jwt_secret(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "duagent-jwt-secret-change-in-production")

    token = create_token("user-1", "student")
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "user-1"


def test_validate_production_security():
    # In debug mode, no exception raised
    debug_settings = Settings(DEBUG=True, JWT_SECRET_KEY="", WEBHOOK_SECRET="")
    debug_settings.validate_production_security()

    # In production mode, weak JWT key fails
    prod_weak_jwt = Settings(
        DEBUG=False,
        JWT_SECRET_KEY="duagent-jwt-secret-change-in-production",
        WEBHOOK_SECRET="secure-webhook-secret-1234",
    )
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        prod_weak_jwt.validate_production_security()

    # In production mode, weak WEBHOOK_SECRET fails
    prod_weak_webhook = Settings(
        DEBUG=False,
        JWT_SECRET_KEY="a" * 32,
        WEBHOOK_SECRET="replace-with-secret",
    )
    with pytest.raises(ValueError, match="WEBHOOK_SECRET"):
        prod_weak_webhook.validate_production_security()

    # In production mode, strong keys pass
    prod_secure = Settings(
        DEBUG=False,
        JWT_SECRET_KEY="a" * 32,
        WEBHOOK_SECRET="b" * 32,
    )
    prod_secure.validate_production_security()


def test_webhook_url_generation_ignores_malicious_host_header(monkeypatch):
    monkeypatch.setattr(settings, "BACKEND_INTERNAL_BASE_URL", "http://127.0.0.1:8001")
    scope = {
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "server": ("evil.attacker.com", 80),
        "headers": [(b"host", b"evil.attacker.com")],
    }
    fake_request = Request(scope)

    assert catalog_webhook_url(fake_request) == "http://127.0.0.1:8001/api/v1/webhooks/agent"
    assert resource_webhook_url(fake_request) == "http://127.0.0.1:8001/api/v1/webhooks/agent"
    assert personalized_webhook_url(fake_request) == "http://127.0.0.1:8001/api/v1/webhooks/agent"

