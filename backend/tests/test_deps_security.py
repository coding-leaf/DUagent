import inspect
import os
import sys

import pytest
from fastapi import HTTPException


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.deps import get_download_user, verify_webhook_secret
from app.core.config import settings


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
