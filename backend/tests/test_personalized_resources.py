from datetime import datetime
from types import SimpleNamespace

import pytest

from app.api.v1.personalized_resources import list_personalized_resources
from app.models.others import UserPersonalizedResource


class _Result:
    def __init__(self, *, scalar=None, items=None):
        self._scalar = scalar
        self._items = items or []

    def scalar(self):
        return self._scalar

    def scalars(self):
        return SimpleNamespace(all=lambda: self._items)


class _SequencedDb:
    def __init__(self, results):
        self._results = iter(results)

    async def execute(self, _statement):
        return next(self._results)


@pytest.mark.asyncio
async def test_list_personalized_resources_projects_owned_code_problem_summary():
    personalized_resource = UserPersonalizedResource(
        id="link-1",
        user_id="student-1",
        course_id="course-1",
        code_problem_id="problem-1",
        source_type="ai_chat",
        created_at=datetime(2026, 7, 11, 8, 0, 0),
    )
    code_problem = SimpleNamespace(
        id="problem-1",
        title="统计元音字母",
        language="cpp",
        difficulty="easy",
        chapter="字符串",
        knowledge_point="循环",
    )
    db = _SequencedDb(
        [
            _Result(scalar=1),
            _Result(items=[personalized_resource]),
            _Result(scalar=0, items=[code_problem]),
            _Result(scalar=0),
        ]
    )

    response = await list_personalized_resources(
        course_id="course-1",
        source_type=None,
        page=1,
        page_size=20,
        current_user=SimpleNamespace(id="student-1"),
        db=db,
    )

    assert response["data"]["items"] == [
        {
            "id": "link-1",
            "source_type": "ai_chat",
            "created_at": "2026-07-11T08:00:00",
            "task_id": None,
            "task_status": None,
            "resource": None,
            "question": None,
            "code_problem": {
                "id": "problem-1",
                "title": "统计元音字母",
                "language": "cpp",
                "difficulty": "easy",
                "chapter": "字符串",
                "knowledge_point": "循环",
            },
        }
    ]
def test_generate_request_accepts_natural_language_goal_with_optional_hints():
    from app.schemas.personalized import PersonalizedResourceGenerateRequest

    request = PersonalizedResourceGenerateRequest(
        course_id="course-1",
        goal="根据我的薄弱点生成一份指针复习资料",
        knowledge_point="指针",
        resource_preferences=["personal_lesson", "diagram"],
        difficulty="medium",
    )

    assert request.generate_type == "resource"
    assert request.source_type == "manual"
    assert request.resource_preferences == ["personal_lesson", "diagram"]
