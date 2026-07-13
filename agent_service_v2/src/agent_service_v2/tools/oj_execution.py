from __future__ import annotations

from typing import Any
from agentscope.tool import FunctionTool

from agent_service_v2.tools.backend_learning_client import (
    BackendLearningClient,
    BackendLearningClientError,
)
from agent_service_v2.tools.contracts import edu_tool_result, normalize_tool_result
from agent_service_v2.tools.input_models import OJExecutionInput


def build_oj_execution_tools(
    *,
    client: BackendLearningClient | None,
) -> list[FunctionTool]:
    async def run_code_in_oj(
        code: str,
        language: str,
        stdin: str = "",
    ) -> dict[str, Any]:
        """Compile and run source code in the configured online judge.

        Args:
            code: Complete source code to compile and execute.
            language: Canonical language value such as c, cpp, python, java, go, or javascript.
            stdin: Optional complete standard input for this execution.
        """
        request = OJExecutionInput(code=code, language=language, stdin=stdin)
        if client is None:
            return edu_tool_result(
                status="degraded",
                reason="backend_learning_client_not_configured",
                retryable=True,
                data={
                    "compile_status": "UNKNOWN",
                    "execution": None,
                    "message": "OJ execution client not configured. Please fallback to LLM manual static code analysis.",
                },
            )
        try:
            data = await client.post_json(
                "/internal/ai-chat/oj/evaluate",
                {
                    **request.model_dump(),
                },
            )
            return normalize_tool_result(data)
        except BackendLearningClientError as exc:
            # Gracefully degrade to static reasoning when the backend is offline
            return edu_tool_result(
                status="degraded",
                reason=exc.reason,
                retryable=True,
                data={
                    "compile_status": "UNKNOWN",
                    "execution": None,
                    "message": f"OJ评测服务不可用，请启动LLM静态分析对代码进行人工走查与逻辑判定。原因: {exc.reason}",
                },
            )

    tools = [
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
    tools[0].input_schema = OJExecutionInput.tool_schema()
    return tools
