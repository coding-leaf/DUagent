from __future__ import annotations

from typing import Any
from agentscope.tool import FunctionTool

from agent_service_v2.tools.backend_learning_client import (
    BackendLearningClient,
    BackendLearningClientError,
)


def build_oj_execution_tools(
    *,
    client: BackendLearningClient | None,
) -> list[FunctionTool]:
    async def run_code_in_oj(
        code: str,
        language: str,
        stdin: str = "",
        **_ignored: Any,
    ) -> dict[str, Any]:
        if client is None:
            return {
                "status": "degraded",
                "reason": "backend_learning_client_not_configured",
                "compile_status": "UNKNOWN",
                "execution": None,
                "message": "OJ execution client not configured. Please fallback to LLM manual static code analysis.",
            }
        try:
            return await client.post_json(
                "/internal/ai-chat/oj/evaluate",
                {
                    "code": code,
                    "language": language,
                    "stdin": stdin,
                },
            )
        except BackendLearningClientError as exc:
            # Gracefully degrade to static reasoning when the backend is offline
            return {
                "status": "degraded",
                "reason": exc.reason,
                "compile_status": "UNKNOWN",
                "execution": None,
                "message": f"OJ评测服务不可用，请启动LLM静态分析对代码进行人工走查与逻辑判定。原因: {exc.reason}",
            }

    return [
        FunctionTool(
            run_code_in_oj,
            name="run_code_in_oj",
            description=(
                "Compile and execute source code (C, Python, Java, C++, Go, JS etc.) inside an isolated online sandbox. "
                "Returns compilation output or stdout. Use this tool to verify student code errors or test generated questions."
            ),
            is_read_only=True,
        )
    ]
