"""基于 AgentScope ReActAgent 的 tutoring 适配器，提供 reasoning loop + knowledge + toolkit + memory。

失败时降级到现有 generate_tutoring_model_response() → rule-based generate_tutoring_events()。
"""

from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg

from agent_service.core.logging import get_logger

logger = get_logger(__name__)

TUTOR_REACT_SYSTEM_PROMPT = (
    "你是 EDUagent 的智能辅导 Agent，基于 ReActAgent 推理循环。"
    "回答必须贴合用户画像、课程范围和检索上下文，优先引导理解。"
    "请以 JSON 格式输出回复，JSON object 包含三个字段："
    "model_text（面向学生的自然语言讲解）、"
    "knowledge_points（1到3个字符串数组，本轮涉及的知识点）、"
    "suggestion（字符串，下一步学习建议）。"
    "只输出 JSON，不要加 markdown 代码块或其他说明文字。"
)


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
