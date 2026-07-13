from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from agentscope.mcp import MCPClient, StdioMCPConfig


logger = logging.getLogger(__name__)

DEFAULT_WEB_SEARCH_PACKAGE = "open-websearch@2.1.11"
WEB_SEARCH_MCP_NAME = "web_search"
WEB_SEARCH_TOOL_NAME = "search"
WEB_SEARCH_INTERNAL_TOOL_NAME = "mcp__web_search__search"
WEB_SEARCH_STARTUP_TIMEOUT = 30.0
SUPPORTED_WEB_SEARCH_ENGINES = (
    "baidu",
    "sogou",
    "bing",
    "csdn",
    "juejin",
)


@dataclass(frozen=True)
class WebSearchSettings:
    enabled: bool = False
    package: str = DEFAULT_WEB_SEARCH_PACKAGE
    default_engine: str = "baidu"
    allowed_engines: tuple[str, ...] = SUPPORTED_WEB_SEARCH_ENGINES
    timeout: float = 12.0
    use_proxy: bool = False
    proxy_url: str = "http://127.0.0.1:7890"

    @classmethod
    def from_environ(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> WebSearchSettings:
        source = environ if environ is not None else os.environ
        allowed_engines = _parse_allowed_engines(
            source.get(
                "WEB_SEARCH_ALLOWED_ENGINES",
                ",".join(SUPPORTED_WEB_SEARCH_ENGINES),
            )
        )
        default_engine = source.get("WEB_SEARCH_DEFAULT_ENGINE", "baidu").strip().lower()
        if default_engine not in SUPPORTED_WEB_SEARCH_ENGINES:
            raise ValueError("unsupported WEB_SEARCH_DEFAULT_ENGINE")
        if default_engine not in allowed_engines:
            default_engine = allowed_engines[0]

        package = source.get("WEB_SEARCH_PACKAGE", DEFAULT_WEB_SEARCH_PACKAGE).strip()
        if not package:
            raise ValueError("WEB_SEARCH_PACKAGE must not be empty")

        return cls(
            enabled=_parse_bool(source.get("WEB_SEARCH_ENABLED", "false")),
            package=package,
            default_engine=default_engine,
            allowed_engines=allowed_engines,
            timeout=_parse_positive_float(
                source.get("WEB_SEARCH_TIMEOUT", "12"),
                name="WEB_SEARCH_TIMEOUT",
            ),
            use_proxy=_parse_bool(source.get("WEB_SEARCH_USE_PROXY", "false")),
            proxy_url=source.get(
                "WEB_SEARCH_PROXY_URL",
                "http://127.0.0.1:7890",
            ).strip(),
        )


def build_web_search_client(
    settings: WebSearchSettings,
    environ: Mapping[str, str] | None = None,
) -> MCPClient:
    return MCPClient(
        name=WEB_SEARCH_MCP_NAME,
        is_stateful=True,
        mcp_config=StdioMCPConfig(
            command="npx",
            args=["-y", settings.package],
            env=_build_subprocess_env(settings, environ=environ),
        ),
        enable_tools=[WEB_SEARCH_TOOL_NAME],
        execution_timeout=settings.timeout,
    )


class WebSearchMCPRuntime:
    def __init__(
        self,
        *,
        settings: WebSearchSettings,
        client_factory: Callable[[WebSearchSettings], MCPClient] = build_web_search_client,
        startup_timeout: float = WEB_SEARCH_STARTUP_TIMEOUT,
    ) -> None:
        self.settings = settings
        self._client_factory = client_factory
        self._startup_timeout = startup_timeout
        self._client: MCPClient | None = None

    @property
    def client(self) -> MCPClient | None:
        return self._client

    async def start(self) -> MCPClient | None:
        if not self.settings.enabled:
            logger.info("Web search MCP is disabled")
            return None

        client: MCPClient | None = None
        try:
            client = self._client_factory(self.settings)
            async with asyncio.timeout(self._startup_timeout):
                await client.connect()
                tools = await client.list_tools()
            tool_names = {tool.name for tool in tools}
            if tool_names != {WEB_SEARCH_INTERNAL_TOOL_NAME}:
                raise RuntimeError("required search tool was not discovered")
        except asyncio.CancelledError:
            if client is not None:
                await _close_client_safely(client)
            raise
        except Exception as exc:
            if client is not None:
                await _close_client_safely(client)
            logger.warning(
                "Web search MCP disabled after startup failure: %s",
                type(exc).__name__,
            )
            return None

        self._client = client
        logger.info("Web search MCP connected with search-only tool access")
        return client

    async def close(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            await _close_client_safely(client)


def build_web_search_runtime_from_environ(
    environ: Mapping[str, str] | None = None,
) -> WebSearchMCPRuntime:
    try:
        settings = WebSearchSettings.from_environ(environ)
    except ValueError as exc:
        logger.warning(
            "Web search MCP disabled because configuration is invalid: %s",
            type(exc).__name__,
        )
        settings = WebSearchSettings(enabled=False)
    return WebSearchMCPRuntime(settings=settings)


async def _close_client_safely(client: MCPClient) -> None:
    if not getattr(client, "is_connected", False):
        return
    try:
        await client.close()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning(
            "Web search MCP close failed: %s",
            type(exc).__name__,
        )


def _build_subprocess_env(
    settings: WebSearchSettings,
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    source = environ if environ is not None else os.environ
    child_env = {
        key: source[key]
        for key in ("PATH", "HOME", "SYSTEMROOT")
        if source.get(key)
    }
    child_env.update(
        {
            "MODE": "stdio",
            "SEARCH_MODE": "request",
            "MCP_TOOL_SEARCH_NAME": WEB_SEARCH_TOOL_NAME,
            "DEFAULT_SEARCH_ENGINE": settings.default_engine,
            "ALLOWED_SEARCH_ENGINES": ",".join(settings.allowed_engines),
            "USE_PROXY": "true" if settings.use_proxy else "false",
        }
    )
    if settings.use_proxy:
        if not settings.proxy_url:
            raise ValueError("WEB_SEARCH_PROXY_URL is required when proxy is enabled")
        child_env["PROXY_URL"] = settings.proxy_url
    return child_env


def _parse_allowed_engines(value: str) -> tuple[str, ...]:
    engines = tuple(dict.fromkeys(item.strip().lower() for item in value.split(",") if item.strip()))
    if not engines:
        raise ValueError("WEB_SEARCH_ALLOWED_ENGINES must not be empty")
    if any(engine not in SUPPORTED_WEB_SEARCH_ENGINES for engine in engines):
        raise ValueError("WEB_SEARCH_ALLOWED_ENGINES contains an unsupported engine")
    return engines


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError("invalid boolean configuration")


def _parse_positive_float(value: str, *, name: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed
