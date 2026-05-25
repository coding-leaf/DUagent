import asyncio

import httpx
import pytest

from agent_service.tools import smoke_tutoring_api


def test_smoke_tutoring_api_reports_httpx_timeout(monkeypatch, capsys) -> None:
    class TimeoutClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        def stream(self, *args, **kwargs):
            raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(smoke_tutoring_api.httpx, "AsyncClient", TimeoutClient)

    with pytest.raises(SystemExit) as exc_info:
        asyncio.run(smoke_tutoring_api.main())

    assert exc_info.value.code == 1
    assert "request timed out after 30s" in capsys.readouterr().out
