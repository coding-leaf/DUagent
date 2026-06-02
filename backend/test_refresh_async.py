"""MySQL integration test for refresh endpoint async behavior.

Covers 3 refresh endpoints (profile / evaluation / learning-path):
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

# Override to match local MySQL port (Docker default 3306, .env may differ)
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+aiomysql://root:123456@127.0.0.1:3306/duagent?charset=utf8mb4",
)

from app.db.session import async_session_factory
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.user import RegistrationCode
from app.models.others import UserProfile, Evaluation, LearningPath
from sqlalchemy import select


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


async def test():
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
            r = await client.post(f"/api/v1/profile/refresh?course_id={course_id}", headers=headers)
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

            # Verify DB write
            async with async_session_factory() as db:
                pf_r2 = await db.execute(
                    select(UserProfile).where(
                        UserProfile.course_id == course_id,
                        UserProfile.is_deleted == False,
                    )
                )
                chk("profile/refresh → DB record written", pf_r2.scalars().first() is not None)

        # =============================================
        # 2. profile/refresh Agent failure
        # =============================================
        print("\n-- 2. profile/refresh Agent failure --")
        from app.services.agent_client import AgentServiceError

        with patch("app.api.v1.profile.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.side_effect = AgentServiceError(
                message="Agent unavailable", status_code=503, agent_code=50301)
            r = await client.post(f"/api/v1/profile/refresh?course_id={course_id}", headers=headers)
            chk("Agent error → 202", r.status_code == 202)
            task_id = r.json()["data"]["task_id"]
            result = await _poll_task(client, task_id, headers)
            chk("Agent error → failed", result and result["status"] == "failed")
            chk("Agent error → error_code",
                result and "50301" in str(result.get("error_code", "")))

        # =============================================
        # 3. evaluation/refresh success
        # =============================================
        print("\n-- 3. evaluation/refresh success --")
        with patch("app.api.v1.evaluation.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = {
                "progress_table": {"columns": [], "rows": []},
                "mastery_table": {"columns": [], "rows": []},
                "resource_usage_table": {"columns": [], "rows": []},
                "summary_text": "Good progress",
            }
            r = await client.post(f"/api/v1/evaluation/refresh?course_id={course_id}", headers=headers)
            chk("eval/refresh → 202", r.status_code == 202)
            task_id = r.json()["data"]["task_id"]
            chk("eval/refresh → task_id present", bool(task_id))

            r_imm = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
            imm_data = r_imm.json().get("data", {})
            chk("eval/refresh → still processing on immediate poll",
                imm_data.get("status") == "processing")

            result = await _poll_task(client, task_id, headers)
            chk("eval/refresh → completed", result and result["status"] == "completed")

            async with async_session_factory() as db:
                ev_r = await db.execute(
                    select(Evaluation).where(
                        Evaluation.course_id == course_id,
                        Evaluation.is_deleted == False,
                    )
                )
                chk("eval/refresh → DB record written", ev_r.scalars().first() is not None)

        # =============================================
        # 4. evaluation/refresh Agent failure
        # =============================================
        print("\n-- 4. evaluation/refresh Agent failure --")
        with patch("app.api.v1.evaluation.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.side_effect = AgentServiceError(
                message="eval failed", status_code=500, agent_code=50001)
            r = await client.post(f"/api/v1/evaluation/refresh?course_id={course_id}", headers=headers)
            chk("eval Agent error → 202", r.status_code == 202)
            task_id = r.json()["data"]["task_id"]
            result = await _poll_task(client, task_id, headers)
            chk("eval Agent error → failed", result and result["status"] == "failed")
            chk("eval Agent error → error_code",
                result and "50001" in str(result.get("error_code", "")))

        # =============================================
        # 5. learning-path/refresh success
        # =============================================
        print("\n-- 5. learning-path/refresh success --")
        with patch("app.api.v1.learning_path.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = {
                "nodes": [{"id": "n1", "name": "Intro", "status": "pending", "mastery": 0, "order": 0}],
                "edges": [],
                "current_position": {"node_id": "n1", "node_name": "Intro"},
            }
            r = await client.post(f"/api/v1/learning-path/refresh?course_id={course_id}", headers=headers)
            chk("lp/refresh → 202", r.status_code == 202)
            task_id = r.json()["data"]["task_id"]
            chk("lp/refresh → task_id present", bool(task_id))

            r_imm = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
            imm_data = r_imm.json().get("data", {})
            chk("lp/refresh → still processing on immediate poll",
                imm_data.get("status") == "processing")

            result = await _poll_task(client, task_id, headers)
            chk("lp/refresh → completed", result and result["status"] == "completed")

            async with async_session_factory() as db:
                lp_r = await db.execute(
                    select(LearningPath).where(
                        LearningPath.course_id == course_id,
                        LearningPath.is_deleted == False,
                    )
                )
                chk("lp/refresh → DB record written", lp_r.scalars().first() is not None)

        # =============================================
        # 6. learning-path/refresh Agent failure
        # =============================================
        print("\n-- 6. learning-path/refresh Agent failure --")
        with patch("app.api.v1.learning_path.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.side_effect = AgentServiceError(
                message="lp failed", status_code=500, agent_code=50002)
            r = await client.post(f"/api/v1/learning-path/refresh?course_id={course_id}", headers=headers)
            chk("lp Agent error → 202", r.status_code == 202)
            task_id = r.json()["data"]["task_id"]
            result = await _poll_task(client, task_id, headers)
            chk("lp Agent error → failed", result and result["status"] == "failed")
            chk("lp Agent error → error_code",
                result and "50002" in str(result.get("error_code", "")))

    print(f"\n{'='*50}")
    print(f"  Total: {ok} OK, {fail} FAIL")
    return fail == 0


if __name__ == "__main__":
    import sys
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
