from agent_service.memory.tutoring_retrieval import TutoringRetrievalContext
from agent_service.agents.tutoring import TutoringModelResponse
from agent_service.agents.tutoring_strategy import TutoringStrategy
from agent_service.schemas.tutoring import RecentMessage, TutoringChatRequest, TutoringUserProfile


def test_react_system_prompt_drops_raw_json_instruction() -> None:
    from agent_service.prompts.tutoring import TUTOR_REACT_SYSTEM_PROMPT

    # 不再要求模型直接吐 JSON / markdown 代码块（structured_model 由 generate_response 工具负责）
    assert "JSON 格式输出" not in TUTOR_REACT_SYSTEM_PROMPT
    assert "只输出 JSON" not in TUTOR_REACT_SYSTEM_PROMPT
    assert "markdown 代码块" not in TUTOR_REACT_SYSTEM_PROMPT
    # 仍保留字段语义与教学指引
    assert "knowledge_points" in TUTOR_REACT_SYSTEM_PROMPT
    assert "model_text" in TUTOR_REACT_SYSTEM_PROMPT
    assert "suggestion" in TUTOR_REACT_SYSTEM_PROMPT
