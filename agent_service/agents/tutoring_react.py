"""基于 AgentScope ReActAgent 的 tutoring 适配器，提供 reasoning loop + knowledge + toolkit + memory。

失败时降级到规则兜底。
"""

from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg

from agent_service.core.logging import get_logger
from agent_service.prompts.tutoring import TUTOR_REACT_SYSTEM_PROMPT
from agent_service.schemas.tutoring import TutoringStructuredOutput

logger = get_logger(__name__)


class TutorReActAgent:
    """基于 ReActAgent 的 tutor 适配器，封装推理循环、knowledge、toolkit 和 memory。

    输入：chat_model (OpenAIChatModel)、formatter (DeepSeekChatFormatter)、
          可选 toolkit、memory、knowledge、max_iters。
    输出：generate() 返回 structured metadata(dict)/文本(str)/None。
    """

    def __init__(
        self,
        chat_model,
        formatter,
        toolkit=None,
        memory=None,
        knowledge=None,
        max_iters: int = 5,
    ) -> None:
        self._chat_model = chat_model
        self._agent = ReActAgent(
            name="EduTutor",
            sys_prompt=TUTOR_REACT_SYSTEM_PROMPT,
            model=chat_model,
            formatter=formatter,
            toolkit=toolkit,
            knowledge=knowledge,
            memory=memory or InMemoryMemory(),
            max_iters=max_iters,
        )

    async def generate(self, user_message: str) -> dict | str | None:
        """调用 ReActAgent 生成回答。

        返回值：
        - dict：成功产出 structured_model（来自 result.metadata），含 model_text 等字段；
        - str：未产出结构化输出时回退到纯文本（交由上游兜底解析）；
        - None：调用异常，走规则兜底。
        """
        try:
            kwargs = {}
            if not _should_skip_structured_model(self._chat_model):
                kwargs["structured_model"] = TutoringStructuredOutput
            result = await self._agent(
                Msg(name="user", role="user", content=user_message),
                **kwargs,
            )
            if result.metadata:
                return result.metadata
            return result.get_text_content()
        except Exception:
            logger.warning("TutorReActAgent.generate 调用失败，降级到规则兜底", exc_info=True)
            return None


def _should_skip_structured_model(chat_model) -> bool:
    """DeepSeek thinking/reasoning models reject AgentScope's forced tool_choice."""
    model_name = str(getattr(chat_model, "model_name", "") or "").lower()
    return "deepseek" in model_name and (
        "reasoner" in model_name
        or "r1" in model_name
        or "v4" in model_name
        or "thinking" in model_name
    )
