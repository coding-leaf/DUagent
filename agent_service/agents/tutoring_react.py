"""基于 AgentScope ReActAgent 的 tutoring 适配器，提供 reasoning loop + knowledge + toolkit + memory。

失败时降级到现有 generate_tutoring_model_response() → rule-based fallback。
"""

from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg

from agent_service.core.logging import get_logger
from agent_service.prompts.tutoring import TUTOR_REACT_SYSTEM_PROMPT

logger = get_logger(__name__)


class TutorReActAgent:
    """基于 ReActAgent 的 tutor 适配器，封装推理循环、knowledge、toolkit 和 memory。

    输入：chat_model (OpenAIChatModel)、formatter (DeepSeekChatFormatter)、
          可选 toolkit、memory、knowledge、max_iters。
    输出：generate() 返回模型文本或 None（降级）。
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

    async def generate(self, user_message: str) -> str | None:
        """调用 ReActAgent 生成回答，输入用户消息文本，输出模型回复或 None（失败降级）。"""
        try:
            result = await self._agent(
                Msg(name="user", role="user", content=user_message),
            )
            return result.get_text_content()
        except Exception:
            logger.warning("TutorReActAgent.generate 调用失败，降级到 fallback", exc_info=True)
            return None
