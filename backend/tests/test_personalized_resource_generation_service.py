from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import personalized_resource_generation_service as module


def test_generation_state_machine_rejects_publish_before_review():
    validate_transition = getattr(module, "validate_generation_transition", None)
    assert callable(validate_transition)

    with pytest.raises(module.ResourcePublicationError, match="invalid_transition"):
        validate_transition("drafted", "published")


def test_generation_state_machine_allows_validated_reviewed_publication():
    validate_transition = module.validate_generation_transition

    validate_transition("drafted", "validated")
    validate_transition("validated", "approved")
    validate_transition("approved", "published")
    validate_transition("validated", "approved_with_advice")
    validate_transition("approved_with_advice", "published")


@pytest.mark.asyncio
async def test_generation_records_validation_and_review_lifecycle():
    db = MagicMock()
    db.flush = AsyncMock()
    service = module.PersonalizedResourceGenerationService(db)
    generation = MagicMock(
        status="drafted",
        validation_report=None,
        review_decision=None,
        review_report=None,
    )
    service._get = AsyncMock(return_value=generation)

    await service.record_validation("generation-1", {"status": "passed"})
    await service.record_review("generation-1", {"decision": "approved"})

    assert generation.validation_report == {"status": "passed"}
    assert generation.review_decision == "approved"
    assert generation.review_report == {"decision": "approved"}
    assert generation.status == "approved"


@pytest.mark.asyncio
async def test_publish_requires_validation_and_review_records():
    db = AsyncMock()
    generation = MagicMock(
        id="generation-1",
        status="drafted",
        validation_report=None,
        review_report=None,
        review_decision=None,
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = generation
    db.execute.return_value = result
    service = module.PersonalizedResourceGenerationService(db)

    with pytest.raises(module.ResourcePublicationError, match="validation_required"):
        await service.publish("generation-1")


@pytest.mark.asyncio
async def test_publish_materializes_approved_draft_and_personalized_link():
    db = MagicMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    generation = MagicMock(
        id="generation-1",
        user_id="user-1",
        course_id="course-1",
        source_type="manual",
        run_id=None,
        resource_type="personal_lesson",
        status="approved_with_advice",
        validation_report={"status": "passed"},
        review_decision="approved_with_advice",
        draft={
            "title": "指针复习讲义",
            "description": "针对数组与指针混淆",
            "content": "# 指针",
            "chapter": "第三章",
            "knowledge_point": "指针",
            "tags": ["C语言", "指针"],
        },
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = generation
    db.execute.return_value = result
    service = module.PersonalizedResourceGenerationService(db)

    resource = await service.publish("generation-1")

    assert resource.title == "指针复习讲义"
    assert resource.type == "personal_lesson"
    assert generation.status == "published"
    assert generation.published_resource_id == resource.id
    assert db.add.call_count == 2


@pytest.mark.asyncio
async def test_ai_chat_run_id_is_not_written_to_async_task_foreign_key():
    db = MagicMock()
    db.execute = AsyncMock()
    no_match = MagicMock()
    no_match.scalar_one_or_none.return_value = None
    db.execute.return_value = no_match
    generation = MagicMock(
        user_id="user-1",
        course_id="course-1",
        source_type="ai_chat",
        run_id="run_912e6797c55248338d369ab3af0b43f0",
    )

    link = await module.link_published_generation(
        db,
        generation=generation,
        code_problem_id="problem-1",
    )

    assert link.task_id is None
    assert link.code_problem_id == "problem-1"


@pytest.mark.asyncio
async def test_async_task_generation_keeps_task_link_and_completes_task():
    db = MagicMock()
    db.execute = AsyncMock()
    task = MagicMock(id="task-1", status="processing", progress=50, completed_at=None)
    task_result = MagicMock()
    task_result.scalar_one_or_none.return_value = task
    existing_link = MagicMock()
    link_result = MagicMock()
    link_result.scalar_one_or_none.return_value = existing_link
    db.execute.side_effect = [task_result, link_result]
    generation = MagicMock(
        user_id="user-1",
        course_id="course-1",
        source_type="async_generation",
        run_id="task-1",
    )

    link = await module.link_published_generation(
        db,
        generation=generation,
        resource_id="resource-1",
    )

    assert link is existing_link
    assert link.resource_id == "resource-1"
    assert task.status == "completed"
    assert task.progress == 100
    assert task.completed_at is not None
    db.add.assert_not_called()
