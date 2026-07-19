import asyncio
import importlib
from contextlib import asynccontextmanager
from types import SimpleNamespace

main_module = importlib.import_module("agent_service_v2.main")
from agent_service_v2.tools.web_search_mcp import (
    DEFAULT_WEB_SEARCH_PACKAGE,
    WEB_SEARCH_INTERNAL_TOOL_NAME,
    WebSearchMCPRuntime,
    WebSearchSettings,
    build_web_search_client,
    build_web_search_runtime_from_environ,
)


class FakeMCPClient:
    def __init__(
        self,
        *,
        tool_names=None,
        connect_error=None,
        discovery_error=None,
        connect_delay=0,
    ):
        self.tool_names = tool_names or [WEB_SEARCH_INTERNAL_TOOL_NAME]
        self.connect_error = connect_error
        self.discovery_error = discovery_error
        self.connect_delay = connect_delay
        self.connect_calls = 0
        self.close_calls = 0
        self.is_connected = False

    async def connect(self):
        self.connect_calls += 1
        if self.connect_delay:
            await asyncio.sleep(self.connect_delay)
        if self.connect_error:
            raise self.connect_error
        self.is_connected = True

    async def list_tools(self):
        if self.discovery_error:
            raise self.discovery_error
        return [SimpleNamespace(name=name) for name in self.tool_names]

    async def close(self):
        self.close_calls += 1
        self.is_connected = False


def test_web_search_client_is_fixed_search_only_stdio_with_minimal_environment():
    settings = WebSearchSettings(enabled=True)
    client = build_web_search_client(
        settings,
        environ={
            "PATH": "/usr/bin",
            "HOME": "/home/service",
            "LLM_API_KEY": "secret",
            "BACKEND_SERVICE_TOKEN": "secret-token",
            "HTTP_PROXY": "http://should-not-leak",
        },
    )

    assert client.is_stateful is True
    assert client.mcp_config.command == "npx"
    assert client.mcp_config.args == ["-y", DEFAULT_WEB_SEARCH_PACKAGE]
    assert client.enable_tools == ["search"]
    assert client.execution_timeout == 12
    assert client.mcp_config.env == {
        "PATH": "/usr/bin",
        "HOME": "/home/service",
        "MODE": "stdio",
        "SEARCH_MODE": "request",
        "MCP_TOOL_SEARCH_NAME": "search",
        "DEFAULT_SEARCH_ENGINE": "baidu",
        "ALLOWED_SEARCH_ENGINES": "baidu,sogou,bing,csdn,juejin",
        "USE_PROXY": "false",
    }


def test_web_search_settings_support_allowed_engines_and_explicit_proxy():
    settings = WebSearchSettings.from_environ(
        {
            "WEB_SEARCH_ENABLED": "true",
            "WEB_SEARCH_DEFAULT_ENGINE": "bing",
            "WEB_SEARCH_ALLOWED_ENGINES": "bing,baidu",
            "WEB_SEARCH_TIMEOUT": "7.5",
            "WEB_SEARCH_USE_PROXY": "true",
            "WEB_SEARCH_PROXY_URL": "http://127.0.0.1:18080",
        }
    )
    client = build_web_search_client(settings, environ={"PATH": "/bin"})

    assert settings.enabled is True
    assert settings.allowed_engines == ("bing", "baidu")
    assert settings.timeout == 7.5
    assert client.mcp_config.env["PROXY_URL"] == "http://127.0.0.1:18080"
    assert client.mcp_config.env["USE_PROXY"] == "true"


def test_invalid_web_search_configuration_disables_runtime_without_raising():
    runtime = build_web_search_runtime_from_environ(
        {
            "WEB_SEARCH_ENABLED": "true",
            "WEB_SEARCH_ALLOWED_ENGINES": "unknown",
        }
    )

    assert runtime.settings.enabled is False
    assert asyncio.run(runtime.start()) is None


def test_runtime_degrades_when_client_configuration_cannot_be_built():
    runtime = build_web_search_runtime_from_environ(
        {
            "WEB_SEARCH_ENABLED": "true",
            "WEB_SEARCH_USE_PROXY": "true",
            "WEB_SEARCH_PROXY_URL": "",
        }
    )

    assert asyncio.run(runtime.start()) is None
    assert runtime.client is None


def test_web_search_runtime_connects_discovers_and_closes_client():
    client = FakeMCPClient()
    runtime = WebSearchMCPRuntime(
        settings=WebSearchSettings(enabled=True),
        client_factory=lambda _settings: client,
    )

    assert asyncio.run(runtime.start()) is client
    assert runtime.client is client
    asyncio.run(runtime.close())

    assert client.connect_calls == 1
    assert client.close_calls == 1
    assert runtime.client is None


def test_web_search_runtime_degrades_when_search_tool_is_missing():
    client = FakeMCPClient(tool_names=["mcp__web_search__fetchWebContent"])
    runtime = WebSearchMCPRuntime(
        settings=WebSearchSettings(enabled=True),
        client_factory=lambda _settings: client,
    )

    assert asyncio.run(runtime.start()) is None
    assert runtime.client is None
    assert client.close_calls == 1


def test_web_search_runtime_degrades_when_tool_discovery_fails():
    client = FakeMCPClient(discovery_error=RuntimeError("discovery failed"))
    runtime = WebSearchMCPRuntime(
        settings=WebSearchSettings(enabled=True),
        client_factory=lambda _settings: client,
    )

    assert asyncio.run(runtime.start()) is None
    assert runtime.client is None
    assert client.close_calls == 1


def test_web_search_runtime_degrades_on_connect_error_and_startup_timeout():
    error_client = FakeMCPClient(connect_error=RuntimeError("contains secret"))
    error_runtime = WebSearchMCPRuntime(
        settings=WebSearchSettings(enabled=True),
        client_factory=lambda _settings: error_client,
    )
    timeout_client = FakeMCPClient(connect_delay=0.05)
    timeout_runtime = WebSearchMCPRuntime(
        settings=WebSearchSettings(enabled=True),
        client_factory=lambda _settings: timeout_client,
        startup_timeout=0.001,
    )

    assert asyncio.run(error_runtime.start()) is None
    assert asyncio.run(timeout_runtime.start()) is None
    assert error_runtime.client is None
    assert timeout_runtime.client is None


def test_fastapi_lifespan_owns_web_search_runtime(monkeypatch):
    calls = []

    class FakeRuntime:
        async def start(self):
            calls.append("start")
            return "connected-client"

        async def close(self):
            calls.append("close")

    @asynccontextmanager
    async def fake_team_lifespan(_app):
        calls.append("team-start")
        yield
        calls.append("team-close")

    monkeypatch.setattr(
        main_module,
        "build_web_search_runtime_from_environ",
        lambda: FakeRuntime(),
    )
    monkeypatch.setattr(
        main_module.team_runtime_app.router,
        "lifespan_context",
        fake_team_lifespan,
    )

    async def run_lifespan():
        async with main_module.lifespan(main_module.app):
            assert main_module.app.state.web_search_client == "connected-client"

    asyncio.run(run_lifespan())

    assert calls == ["start", "team-start", "team-close", "close"]
    assert main_module.app.state.web_search_client is None
