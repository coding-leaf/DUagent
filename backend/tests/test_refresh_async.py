"""MySQL integration test for active refresh endpoint async behavior.

Covers profile and evaluation refresh endpoints:
  - 202 + task_id returned immediately
  - Background task completes (success) or fails (Agent error)
  - DB records written on success

Requires: MySQL running, `duagent` database with tables created.
Agent calls are mocked — Agent Service not required.

Run: python test_refresh_async.py
"""
import asyncio
import os
import time
import uuid
from unittest.mock import AsyncMock, patch
import pytest

# Override to match local MySQL port (Docker default 3306, .env may differ)
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+aiomysql://root:123456@127.0.0.1:3306/duagent?charset=utf8mb4",
)

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import Base
from app.db.session import async_session_factory, engine
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.agent_client import AgentServiceError
from app.models.user import RegistrationCode, User
from app.models.others import AsyncTask, UserProfile, Evaluation, CourseKnowledgeGraph
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from sqlalchemy import func, select, text


async def _register_and_login(client, code, email, username):
    """Register a user and return auth headers."""
    import re

    def _captcha_ans(d):
        nums = re.findall(r"\d+", d["captcha_question"])
        return str(int(nums[0]) + int(nums[1])) if "+" in d["captcha_question"] else str(int(nums[0]) - int(nums[1]))

    r = await client.get("/api/v1/auth/captcha")
    d = r.json()["data"]
    ans = _captcha_ans(d)
    r = await client.post("/api/v1/auth/register", json={
        "registration_code": code, "email": email, "password": "Abc12345",
        "username": username, "captcha_token": d["captcha_token"], "captcha_code": ans,
    })
    assert r.status_code == 201, f"Register failed: {r.status_code} {r.json()}"

    r = await client.get("/api/v1/auth/captcha")
    d = r.json()["data"]
    ans = _captcha_ans(d)
    r = await client.post("/api/v1/auth/login", json={
        "email": email, "password": "Abc12345",
        "captcha_token": d["captcha_token"], "captcha_code": ans,
    })
    assert "token" in r.json().get("data", {}), f"Login failed: {r.json()}"
    return {"Authorization": f"Bearer {r.json()['data']['token']}"}


async def _poll_task(client, task_id, headers, timeout=15):
    """Poll GET /tasks/{task_id} until terminal or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
        body = r.json()
        data = body.get("data")
        if data and data.get("status") in ("completed", "failed"):
            return data
        await asyncio.sleep(0.3)
    return None


@pytest.mark.asyncio
async def test():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    ok = fail = 0

    def chk(name, cond):
        nonlocal ok, fail
        tag = "OK" if cond else "FAIL"
        print(f"  {tag}  {name}")
        if cond:
            ok += 1
        else:
            fail += 1
            assert cond, name
        return cond

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Seed registration codes (unique per run)
        codes = [
            RegistrationCode(code=f"stu_{uuid.uuid4().hex[:8]}", role="student"),
            RegistrationCode(code=f"tea_{uuid.uuid4().hex[:8]}", role="teacher"),
        ]
        async with async_session_factory() as db:
            db.add_all(codes)
            await db.commit()
            teacher_code = codes[1].code

        uname = f"tr_{uuid.uuid4().hex[:8]}"
        email = f"{uname}@test.com"
        headers = await _register_and_login(client, teacher_code, email, uname)

        # Create a course (teacher creates, then refresh endpoints reference it)
        r = await client.post("/api/v1/courses", json={"name": "Test Course"}, headers=headers)
        assert r.status_code == 201, f"Course creation failed: {r.json()}"
        course_id = r.json()["data"]["id"]
        async with async_session_factory() as db:
            user_r = await db.execute(select(User).where(User.email == email))
            current_user = user_r.scalars().first()

        # =============================================
        # 1. profile/refresh success
        # =============================================
        print("\n-- 1. profile/refresh success --")
        with patch("app.api.v1.profile.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = {
                "modal_preference": {"video_animation": 80},
                "guidance_level_suggestion": {"recommended": "L3"},
                "knowledge_coordinates": [],
                "cognitive_blindspots": [],
                "drive_intent": {"type": "casual"},
                "discipline_badge": {"subject": "math"},
            }
            r = await client.post("/api/v1/profile/refresh", headers=headers, json={"course_id": course_id})
            chk("profile/refresh → 202", r.status_code == 202)
            task_id = r.json()["data"]["task_id"]
            chk("profile/refresh → task_id present", bool(task_id))

            # Verify true async: task should still be processing immediately after 202
            r_imm = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
            imm_data = r_imm.json().get("data", {})
            chk("profile/refresh → still processing on immediate poll",
                imm_data.get("status") == "processing")

            result = await _poll_task(client, task_id, headers)
            chk("profile/refresh → completed", result and result["status"] == "completed")
            await asyncio.sleep(0.5)


            # Verify DB write
            async with async_session_factory() as db:
                pf_r2 = await db.execute(
                    select(UserProfile).where(
                        UserProfile.course_id == course_id,
                        UserProfile.is_deleted == False,
                    )
                )
                profile = pf_r2.scalars().first()
                chk("profile/refresh → DB record written", profile is not None)
                drive_intent = profile.drive_intent or {}
                chk(
                    "profile/refresh → learning_habits persisted",
                    isinstance(drive_intent.get("learning_habits"), dict),
                )
                chk(
                    "profile/refresh → knowledge_progress_summary persisted",
                    isinstance(drive_intent.get("knowledge_progress_summary"), dict),
                )
                used_lock_r = await db.execute(
                    text("SELECT IS_USED_LOCK(:name)"),
                    {"name": f"profile_{current_user.id}_{course_id}"},
                )
                chk("profile/refresh → lock released", used_lock_r.scalar() is None)

        # =============================================
        # 2. profile/refresh duplicate request reuses active processing task
        # =============================================
        print("\n-- 2. profile/refresh duplicate request reuses active processing task --")
        async with async_session_factory() as db:
            existing_task = AsyncTask(
                task_type="profile_refresh",
                status="processing",
                user_id=current_user.id,
                course_id=course_id,
            )
            db.add(existing_task)
            await db.commit()
            existing_task_id = existing_task.id

        r = await client.post("/api/v1/profile/refresh", headers=headers, json={"course_id": course_id})
        chk("profile duplicate → 202", r.status_code == 202)
        chk("profile duplicate → existing task_id", r.json()["data"]["task_id"] == existing_task_id)
        async with async_session_factory() as db:
            count_r = await db.execute(
                select(func.count()).select_from(AsyncTask).where(
                    AsyncTask.task_type == "profile_refresh",
                    AsyncTask.user_id == current_user.id,
                    AsyncTask.course_id == course_id,
                    AsyncTask.status == "processing",
                    AsyncTask.is_deleted == False,
                )
            )
            chk("profile duplicate → no new processing task", count_r.scalar() == 1)
            existing = await db.get(AsyncTask, existing_task_id)
            existing.status = "failed"
            existing.error_code = "test_cleanup"
            existing.error_message = "test cleanup"
            await db.commit()

        # =============================================
        # 3. evaluation/refresh success
        # =============================================
        print("\n-- 5. evaluation/refresh success --")
        async with async_session_factory() as db:
            kg = CourseKnowledgeGraph(
                course_id=course_id,
                version=1,
                is_active=True,
                source_type="test",
                generation_strategy="test",
                nodes=[
                    {"id": "node_pointer", "name": "指针基础", "chapter": "指针"},
                    {"id": "node_array", "name": "数组", "chapter": "数组"},
                    {"id": "node_malloc", "name": "动态内存", "chapter": "动态内存"},
                ],
                edges=[],
            )
            db.add(kg)
            question_pointer = QuizQuestion(
                course_id=course_id,
                chapter="指针",
                knowledge_point="指针基础",
                type="single_choice",
                source="baseline",
                content="指针题",
                options=[{"key": "A", "text": "正确"}],
                correct_answer="A",
            )
            question_array = QuizQuestion(
                course_id=course_id,
                chapter="数组",
                knowledge_point="数组",
                type="single_choice",
                source="baseline",
                content="数组题",
                options=[{"key": "A", "text": "正确"}],
                correct_answer="A",
            )
            db.add_all([question_pointer, question_array])
            await db.flush()
            quiz_session = QuizSession(
                user_id=current_user.id,
                course_id=course_id,
                chapter="指针",
                score=100,
                correct_count=1,
                total_count=1,
                time_spent=180,
            )
            db.add(quiz_session)
            await db.flush()
            db.add(
                QuizAnswer(
                    quiz_id=quiz_session.id,
                    question_id=question_pointer.id,
                    user_answer="A",
                    is_correct=True,
                    correct_answer="A",
                )
            )
            await db.commit()

        with patch("app.api.v1.evaluation.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = {
                "progress_table": {"columns": [], "rows": []},
                "mastery_table": {"columns": [], "rows": []},
                "resource_usage_table": {"columns": [], "rows": []},
                "summary_text": "Good progress",
            }
            r = await client.post("/api/v1/evaluation/refresh", headers=headers, json={"course_id": course_id})
            chk("eval/refresh → 202", r.status_code == 202)
            task_id = r.json()["data"]["task_id"]
            chk("eval/refresh → task_id present", bool(task_id))

            r_imm = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
            imm_data = r_imm.json().get("data", {})
            chk("eval/refresh → still processing on immediate poll",
                imm_data.get("status") == "processing")

            result = await _poll_task(client, task_id, headers)
            chk("eval/refresh → completed", result and result["status"] == "completed")
            await asyncio.sleep(0.5)


            async with async_session_factory() as db:
                ev_r = await db.execute(
                    select(Evaluation).where(
                        Evaluation.course_id == course_id,
                        Evaluation.is_deleted == False,
                    )
                )
                chk("eval/refresh → DB record written", ev_r.scalars().first() is not None)
                used_lock_r = await db.execute(
                    text("SELECT IS_USED_LOCK(:name)"),
                    {"name": f"evaluation_{current_user.id}_{course_id}"},
                )
                chk("eval/refresh → lock released", used_lock_r.scalar() is None)

            r = await client.get(f"/api/v1/evaluation?course_id={course_id}", headers=headers)
            chk("eval/get → 200", r.status_code == 200)
            body = r.json()
            rows = body.get("data", {}).get("node_progress", [])
            by_id = {row.get("node_id"): row for row in rows}
            chk("eval/get → scored node present",
                by_id.get("node_pointer", {}).get("assessment_state") in {"scored", "mastered"})
            chk("eval/get → scored node score",
                by_id.get("node_pointer", {}).get("mastery_score") == 100)
            chk("eval/get → scored node label",
                by_id.get("node_pointer", {}).get("mastery_label") == "A")
            chk("eval/get → scored node duration",
                by_id.get("node_pointer", {}).get("study_duration_seconds") == 180)
            chk("eval/get → pending practice node",
                by_id.get("node_array", {}).get("assessment_state") == "pending_practice")
            chk("eval/get → default pass node",
                by_id.get("node_malloc", {}).get("assessment_state") in {"unassessed_default_pass", "unstarted"})
            chk("eval/get → default pass label",
                by_id.get("node_malloc", {}).get("mastery_label") in {"未测评/默认通过", "无测评"})

        # =============================================
        # 6. evaluation/refresh Agent failure
        # =============================================
        print("\n-- 6. evaluation/refresh Agent failure --")
        with patch("app.api.v1.evaluation.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.side_effect = AgentServiceError(
                message="eval failed", status_code=500, agent_code=50001)
            r = await client.post("/api/v1/evaluation/refresh", headers=headers, json={"course_id": course_id})
            chk("eval Agent error → 202", r.status_code == 202)
            task_id = r.json()["data"]["task_id"]
            result = await _poll_task(client, task_id, headers)
            chk("eval Agent error → failed", result and result["status"] == "failed")
            await asyncio.sleep(0.5)

            chk("eval Agent error → error_code",
                result and "50001" in str(result.get("error_code", "")))
            async with async_session_factory() as db:
                used_lock_r = await db.execute(
                    text("SELECT IS_USED_LOCK(:name)"),
                    {"name": f"evaluation_{current_user.id}_{course_id}"},
                )
                chk("eval Agent error → lock released", used_lock_r.scalar() is None)

        # =============================================
        # 6B. duplicate refresh reuses active processing task
        # =============================================
        print("\n-- 6B. duplicate refresh reuses active processing task --")
        async with async_session_factory() as db:
            existing_task = AsyncTask(
                task_type="evaluation_refresh",
                status="processing",
                user_id=current_user.id,
                course_id=course_id,
            )
            db.add(existing_task)
            await db.commit()
            existing_task_id = existing_task.id

        r = await client.post("/api/v1/evaluation/refresh", headers=headers, json={"course_id": course_id})
        chk("eval duplicate → 202", r.status_code == 202)
        chk("eval duplicate → existing task_id", r.json()["data"]["task_id"] == existing_task_id)
        async with async_session_factory() as db:
            count_r = await db.execute(
                select(func.count()).select_from(AsyncTask).where(
                    AsyncTask.task_type == "evaluation_refresh",
                    AsyncTask.user_id == current_user.id,
                    AsyncTask.course_id == course_id,
                    AsyncTask.status == "processing",
                    AsyncTask.is_deleted == False,
                )
            )
            chk("eval duplicate → no new processing task", count_r.scalar() == 1)
            existing = await db.get(AsyncTask, existing_task_id)
            existing.status = "failed"
            existing.error_code = "test_cleanup"
            existing.error_message = "test cleanup"
            await db.commit()

    print(f"\n{'='*50}")
    print(f"  Total: {ok} OK, {fail} FAIL")
    return fail == 0


if __name__ == "__main__":
    import sys
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
