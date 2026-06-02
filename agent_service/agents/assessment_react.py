"""基于 AgentScope ReActAgent 的 assessment 出题适配器，提供推理循环、格式自检与工具调用。

失败时降级到现有 generate_questions_with_llm() → rule-based fallback。
"""

from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg

from agent_service.core.logging import get_logger
from agent_service.prompts.assessment import build_question_react_system_prompt
from agent_service.prompts.assessment import build_question_generation_user_message

logger = get_logger(__name__)


class QuestionGeneratorReActAgent:
    """基于 ReActAgent 的出题适配器，封装推理循环、toolkit 和 memory。

    输入：chat_model (OpenAIChatModel)、formatter (DeepSeekChatFormatter)、
          可选 toolkit、memory、max_iters。
    输出：generate() 返回解析后的 list[dict] 或 None（降级）。
    """

    def __init__(
        self,
        chat_model,
        formatter,
        toolkit=None,
        memory=None,
        max_iters: int = 5,
    ) -> None:
        self._agent = ReActAgent(
            name="QuestionGenerator",
            sys_prompt=build_question_react_system_prompt(),
            model=chat_model,
            formatter=formatter,
            toolkit=toolkit,
            memory=memory or InMemoryMemory(),
            max_iters=max_iters,
        )

    async def generate(self, request, course_knowledge_context: str | None = None) -> list[dict] | None:
        """调用 ReActAgent 生成题目，返回原始 dict 列表供下层 _coerce_questions 解析。"""
        from agent_service.agents.assessment import _parse_question_payload

        user_message = build_question_generation_user_message(
            request, course_knowledge_context=course_knowledge_context
        )
        try:
            result = await self._agent(
                Msg(name="user", role="user", content=user_message),
            )
            raw_text = result.get_text_content()
            if not raw_text:
                return None
            return _parse_question_payload(raw_text)
        except Exception:
            logger.warning("QuestionGeneratorReActAgent.generate 调用失败或解析失败，降级到 fallback", exc_info=True)
            return None
