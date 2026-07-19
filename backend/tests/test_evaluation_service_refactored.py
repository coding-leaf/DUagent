import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from app.services.evaluation_service import EvaluationService, run_evaluation_refresh_background
from app.models.others import AsyncTask, Evaluation
from app.models.user import User


@asynccontextmanager
async def mock_evaluation_lock(db, user_id, course_id):
    yield "mock_lock"


@pytest.mark.asyncio
@patch("app.services.evaluation_service.build_node_progress_rows")
async def test_get_evaluation_not_found(mock_build_node_progress):
    mock_build_node_progress.return_value = [{"node_id": "n1", "status": "completed"}]
    db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = None
    db.execute.return_value = mock_res

    service = EvaluationService(db)
    res = await service.get_evaluation("u123", "c456")
    assert res["course_id"] == "c456"
    assert res["summary_text"] == ""
    assert res["node_progress"] == [{"node_id": "n1", "status": "completed"}]
    assert res["generated_at"] is None


@pytest.mark.asyncio
@patch("app.services.evaluation_service.build_node_progress_rows")
async def test_get_evaluation_found(mock_build_node_progress):
    mock_build_node_progress.return_value = []
    db = AsyncMock()
    mock_eval = Evaluation(
        user_id="u123",
        course_id="c456",
        summary_text="Great performance",
        generated_at=datetime(2026, 6, 20, 20, 0, 0, tzinfo=timezone.utc),
        is_deleted=False
    )
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = mock_eval
    db.execute.return_value = mock_res

    service = EvaluationService(db)
    res = await service.get_evaluation("u123", "c456")
    assert res["course_id"] == "c456"
    assert res["summary_text"] == "Great performance"
    assert res["generated_at"] == "2026-06-20T20:00:00+00:00"


@pytest.mark.asyncio
@patch("app.services.evaluation_service.EvaluationService._assemble_evaluation_payload")
async def test_refresh_evaluation_student_not_enrolled(mock_payload):
    db = AsyncMock()
    student = User(id="u123", role="student")

    mock_enroll_res = MagicMock()
    mock_enroll_res.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_enroll_res

    service = EvaluationService(db)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await service.refresh_evaluation(student, "c456")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
@patch("app.services.evaluation_service.EvaluationService._assemble_evaluation_payload")
async def test_refresh_evaluation_task_exists(mock_payload):
    db = AsyncMock()
    student = User(id="u123", role="student")

    mock_task = AsyncTask(id="t123", status="processing")
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = MagicMock()
    mock_res.scalars().first.return_value = mock_task
    db.execute.return_value = mock_res

    service = EvaluationService(db)
    res = await service.refresh_evaluation(student, "c456")
    assert res["task_id"] == "t123"


@pytest.mark.asyncio
@patch("app.services.evaluation_service.EvaluationService._assemble_evaluation_payload")
@patch("app.services.evaluation_service.run_evaluation_refresh_background")
async def test_refresh_evaluation_creates_task(mock_run_bg, mock_payload):
    db = AsyncMock()
    student = User(id="u123", role="student")

    mock_enroll_res = MagicMock()
    mock_enroll_res.scalar_one_or_none.return_value = MagicMock()
    mock_task_res = MagicMock()
    mock_task_res.scalars().first.return_value = None

    db.execute.side_effect = [mock_enroll_res, mock_task_res]
    mock_payload.return_value = {"dummy": "payload"}

    service = EvaluationService(db)
    res = await service.refresh_evaluation(student, "c456")
    assert "task_id" in res
    mock_run_bg.assert_called_once()


@pytest.mark.asyncio
@patch("app.services.evaluation_service.evaluation_lock", mock_evaluation_lock)
@patch("app.services.evaluation_service.agent_client")
@patch("app.services.evaluation_service.build_node_progress_rows")
@patch("app.services.evaluation_service.async_session_factory")
async def test_run_evaluation_refresh_background_success(
    mock_session_factory,
    mock_build_node_progress,
    mock_agent_client
):
    db = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = db

    mock_agent_client.post_json = AsyncMock(return_value={
        "progress_table": {"columns": []},
        "mastery_table": {"columns": ["k", "score"], "rows": [["math", 90]]},
        "summary_text": "Good math skill"
    })
    mock_build_node_progress.return_value = [{"node_id": "n1", "status": "completed"}]

    mock_evals = MagicMock()
    mock_evals.scalars().all.return_value = []
    db.execute.return_value = mock_evals

    await run_evaluation_refresh_background("t123", "u123", "c456", {"dummy": "payload"})

    db.commit.assert_called_once()
    db.add.assert_called_once()
    added_eval = db.add.call_args[0][0]
    assert isinstance(added_eval, Evaluation)
    assert added_eval.summary_text == "Good math skill"
    assert added_eval.progress_table["rows"] == [{"node_id": "n1", "status": "completed"}]


@pytest.mark.asyncio
@patch("app.services.evaluation_service.agent_client")
@patch("app.services.evaluation_service.async_session_factory")
async def test_run_evaluation_refresh_background_lock_timeout(
    mock_session_factory,
    mock_agent_client
):
    @asynccontextmanager
    async def failing_evaluation_lock(db, user_id, course_id):
        raise RuntimeError("GET_LOCK timeout: mock_lock")
        yield "mock_lock"

    with patch("app.services.evaluation_service.evaluation_lock", failing_evaluation_lock):
        db = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = db
        mock_agent_client.post_json = AsyncMock(return_value={})

        await run_evaluation_refresh_background("t123", "u123", "c456", {})

        db.rollback.assert_called_once()
        db.commit.assert_called_once()

