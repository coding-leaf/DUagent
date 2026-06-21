import asyncio
import time
from agent_service.core.ai import get_ai_providers, ChatMessage
from agent_service.core.config import settings
from agent_service.schemas.assessment import (
    AssessmentEvaluateRequest,
    AssessmentQuestion,
    AssessmentAnswer,
    AssessmentResult,
    PerQuestionResult,
    Diagnosis
)
from agent_service.agents.assessment import (
    evaluate_assessment_data,
    _EvalDiagnosisStructuredOutput
)

async def test_real_evaluation():
    providers = get_ai_providers()
    chat = providers.chat
    
    if not chat:
        print("Chat provider not configured.")
        return
        
    # Build a mock request for 3 questions
    request = AssessmentEvaluateRequest(
        user_id="test_student_123",
        course_id="c_python_base",
        quiz_id="q_session_01",
        questions=[
            AssessmentQuestion(
                id="q_01",
                type="single_choice",
                content="在 Python 中，下面哪个是合法的变量名？",
                options=[
                    {"key": "A", "text": "2var"},
                    {"key": "B", "text": "my-var"},
                    {"key": "C", "text": "my_var"},
                    {"key": "D", "text": "class"}
                ],
                correct_answer="C",
                knowledge_point="Python 变量命名规范"
            ),
            AssessmentQuestion(
                id="q_02",
                type="single_choice",
                content="下列关于 Python 列表的说法中，错误的是？",
                options=[
                    {"key": "A", "text": "列表是可变的（mutable）"},
                    {"key": "B", "text": "列表中的元素类型必须相同"},
                    {"key": "C", "text": "可以使用 append() 方法向列表末尾添加元素"},
                    {"key": "D", "text": "支持通过索引和切片访问元素"}
                ],
                correct_answer="B",
                knowledge_point="Python 列表基本操作"
            )
        ],
        answers=[
            AssessmentAnswer(question_id="q_01", answer="A"),  # Wrong
            AssessmentAnswer(question_id="q_02", answer="B")   # Correct
        ]
    )
    
    # Get the rule-based result first
    rule_result = evaluate_assessment_data(request)
    
    from agent_service.prompts.assessment import (
        build_evaluate_system_prompt,
        build_evaluate_user_message
    )
    
    messages = [
        ChatMessage(role="system", content=build_evaluate_system_prompt()),
        ChatMessage(role="user", content=build_evaluate_user_message(request, rule_result)),
    ]
    
    from agentscope.message import Msg
    formatted = await chat._format_messages(messages, Msg)
    
    # 1. Benchmark default (Thinking Enabled)
    print("\n--- Running Evaluation with Thinking Enabled (Default) ---")
    start = time.time()
    try:
        response_data = await chat.model(
            formatted,
            structured_model=_EvalDiagnosisStructuredOutput
        )
        elapsed = time.time() - start
        print(f"Success! Elapsed time: {elapsed:.2f}s")
        print(f"Content: {response_data.content}")
    except Exception as e:
        print(f"Failed: {e}")
        
    # 2. Benchmark thinking disabled
    print("\n--- Running Evaluation with Thinking Disabled (extra_body) ---")
    start = time.time()
    try:
        response_data = await chat.model(
            formatted,
            structured_model=_EvalDiagnosisStructuredOutput,
            extra_body={"thinking": {"type": "disabled"}}
        )
        elapsed = time.time() - start
        print(f"Success! Elapsed time: {elapsed:.2f}s")
        print(f"Content: {response_data.content}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_real_evaluation())
