"""统一 Agent Service HTTP 客户端。

职责：
- 统一读取 AGENT_SERVICE_URL
- 统一 timeout / 错误处理 / 响应包装校验
- post_json: 同步 JSON 请求，返回校验后的 data
- stream_sse: 流式 SSE 请求，返回 httpx 异步迭代器
"""

from typing import AsyncIterator, Optional

import httpx
from fastapi import HTTPException, status

from app.core.config import settings


class AgentServiceError(Exception):
    """Agent Service 返回的非 2xx 或业务错误。"""
    def __init__(self, message: str, status_code: int = 502, agent_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        self.agent_code = agent_code
        super().__init__(message)


class AgentClient:
    """Agent Service HTTP 客户端。

    路由层不要散落 httpx 调用，统一走此类，方便后续加日志、超时、重试和熔断。
    """

    def __init__(self, timeout: float = 60.0):
        self.base_url: str = settings.AGENT_SERVICE_URL.rstrip("/")
        self.timeout: float = timeout

    async def post_json(self, path: str, payload: dict) -> dict:
        """POST JSON 到 Agent Service，校验响应包装并返回 data 字段。

        Args:
            path: Agent 接口路径，如 "/agent/v1/profile/generate"
            payload: 请求体

        Returns:
            Agent 响应中的 data 字段 (dict)

        Raises:
            AgentServiceError: Agent 异常、超时或返回业务错误
        """
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
        except httpx.TimeoutException:
            raise AgentServiceError("Agent Service 响应超时", status_code=504)
        except httpx.ConnectError:
            raise AgentServiceError("无法连接 Agent Service", status_code=503)

        if resp.status_code >= 500:
            raise AgentServiceError(
                f"Agent Service 内部错误 (HTTP {resp.status_code})",
                status_code=502,
            )

        try:
            body = resp.json()
        except Exception:
            raise AgentServiceError("Agent Service 返回非 JSON 响应", status_code=502)

        # 校验统一包装 {code, message, data}
        agent_code: int = body.get("code", -1)
        if resp.status_code >= 400 or (agent_code != 200 and agent_code != 201 and agent_code != 202):
            raise AgentServiceError(
                body.get("message", "Agent Service 返回业务错误"),
                status_code=502,
                agent_code=agent_code,
            )

        return body.get("data", {})

    async def stream_sse(self, path: str, payload: dict) -> AsyncIterator[bytes]:
        """POST 到 Agent Service 并返回 SSE 流迭代器（异步生成器）。

        使用 async with 管理 client 生命周期，避免 client 过早释放导致
        协程未被等待的问题。

        Args:
            path: Agent 接口路径
            payload: 请求体

        Yields:
            bytes chunk from Agent SSE stream

        Raises:
            AgentServiceError: 连接异常、超时或非 2xx 响应
        """
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as http_client:
                async with http_client.stream("POST", url, json=payload) as resp:
                    if resp.status_code >= 400:
                        await resp.aread()
                        try:
                            body = resp.json()
                            msg = body.get("message", f"Agent Service 错误 (HTTP {resp.status_code})")
                        except Exception:
                            msg = f"Agent Service 错误 (HTTP {resp.status_code})"
                        raise AgentServiceError(msg, status_code=502)

                    async for chunk in resp.aiter_bytes():
                        yield chunk
        except httpx.TimeoutException:
            raise AgentServiceError("Agent Service SSE 连接超时", status_code=504)
        except httpx.ConnectError:
            raise AgentServiceError("无法连接 Agent Service (SSE)", status_code=503)


# 模块级单例
agent_client = AgentClient()
