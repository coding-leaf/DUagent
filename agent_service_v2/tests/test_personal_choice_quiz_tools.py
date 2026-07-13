import asyncio
import json

from agentscope.workspace import LocalWorkspace

from agent_service_v2.tools.personal_choice_quiz import build_personal_choice_quiz_tools


class FakeClient:
    def __init__(self):
        self.calls = []

    async def post_json(self, path, payload):
        self.calls.append((path, payload))
        return {
            "status": "published",
            "title": payload["title"],
            "question_ids": ["question-1", "question-2"],
            "question_count": 2,
            "artifact": {
                "id": "quiz-generation-1",
                "type": "QuizCard",
                "title": payload["title"],
                "course_id": payload["course_id"],
                "question_ids": ["question-1", "question-2"],
            },
        }


def _text(chunk) -> str:
    return chunk.content[0].text


def test_personal_choice_quiz_tool_publishes_and_creates_matching_card(tmp_path):
    client = FakeClient()
    tool = build_personal_choice_quiz_tools(
        client=client,
        user_id="student-1",
        course_id="course-1",
        conversation_id="conversation-1",
        run_id="run-1",
        workspace=LocalWorkspace(workdir=str(tmp_path), workspace_id="ws"),
    )[0]
    questions = [
        {
            "type": "single_choice",
            "content": "哪个运算符用于取地址？",
            "options": [{"key": "A", "text": "&"}, {"key": "B", "text": "*"}],
            "answer": "A",
            "explanation": "& 用于取地址。",
            "difficulty": "easy",
        },
        {
            "type": "multi_choice",
            "content": "选择合法操作。",
            "options": [{"key": "A", "text": "取地址"}, {"key": "B", "text": "解引用"}],
            "answer": ["A", "B"],
            "explanation": "两者都是合法操作。",
            "difficulty": "medium",
        },
    ]

    response = asyncio.run(
        tool.call(
            title="指针练习",
            chapter="指针",
            knowledge_point="指针基础",
            questions=questions,
        )
    )
    data = json.loads(_text(response))

    assert data["status"] == "published"
    assert data["outcome"] == "success"
    assert data["artifact"]["type"] == "QuizCard"
    assert client.calls[0][0] == "/internal/ai-chat/choice-quizzes"
    assert client.calls[0][1]["questions"] == questions
    assert not list(tmp_path.rglob("*.json"))
