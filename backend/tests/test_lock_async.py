"""MySQL integration test for lock behavior on refresh endpoints.

Covers: lock_timeout (error_code) + lock competition (single active row).
Agent calls mocked. Slow (~18s for timeouts).

Run: python test_lock_async.py
"""
import asyncio
import os
import time
import uuid
from unittest.mock import AsyncMock, patch

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+aiomysql://root:123456@127.0.0.1:3306/duagent?charset=utf8mb4",
)

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import async_session_factory
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.user import RegistrationCode
from app.models.others import UserProfile
from sqlalchemy import func, select, text


async def _register_and_login(client, code, email, username):
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
    user_id = r.json()["data"]["user_id"]

    r = await client.get("/api/v1/auth/captcha")
    d = r.json()["data"]
    ans = _captcha_ans(d)
    r = await client.post("/api/v1/auth/login", json={
        "email": email, "password": "Abc12345",
        "captcha_token": d["captcha_token"], "captcha_code": ans,
    })
    assert "token" in r.json().get("data", {}), f"Login failed: {r.json()}"
    return {"Authorization": f"Bearer {r.json()['data']['token']}"}, user_id


async def _poll_task(client, task_id, headers, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
        data = r.json().get("data", {})
        if data.get("status") in ("completed", "failed"):
            return data
        await asyncio.sleep(0.5)
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
        # Seed
        uname = f"tr_{uuid.uuid4().hex[:8]}"
        email = f"{uname}@test.com"
        codes = [
            RegistrationCode(code=f"tea_{uuid.uuid4().hex[:8]}", role="teacher"),
        ]
        async with async_session_factory() as db:
            db.add_all(codes)
            await db.commit()
            teacher_code = codes[0].code

        headers, user_id = await _register_and_login(client, teacher_code, email, uname)
        r = await client.post("/api/v1/courses", json={"name": "Test Course"}, headers=headers)
        assert r.status_code == 201, f"Course creation failed: {r.json()}"
        course_id = r.json()["data"]["id"]

        lock_name = f"profile_{user_id}_{course_id}"

        # =============================================
        # 1. Acquire lock in independent session
        # =============================================
        lock_session = async_session_factory()
        try:
            lock_result = await lock_session.execute(
                text("SELECT GET_LOCK(:name, 0)"), {"name": lock_name}
            )
            locked = lock_result.scalar()
            chk("lock acquired", locked == 1)
            if not locked:
                print(f"  (skipping lock_timeout test — could not acquire lock {lock_name})")
                return fail == 0

            # =============================================
            # 2. Trigger profile/refresh — background task hits lock timeout
            # =============================================
            print("  (waiting ~5s for GET_LOCK timeout in background task...)")
            with patch("app.api.v1.profile.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
                mock_agent.return_value = {
                    "modal_preference": {},
                    "guidance_level_suggestion": {"recommended": "L3"},
                }
                r = await client.post("/api/v1/profile/refresh", headers=headers, json={"course_id": course_id})
                chk("lock held → 202", r.status_code == 202)
                task_id = r.json()["data"]["task_id"]
                chk("lock held → task_id present", bool(task_id))

                result = await _poll_task(client, task_id, headers, timeout=15)
                chk("lock held → task failed", result and result["status"] == "failed")
                chk("lock held → error_code=lock_timeout",
                    result and result.get("error_code") == "lock_timeout")
        finally:
            await lock_session.execute(
                text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name}
            )
            await lock_session.close()

        # =============================================
        # 2. evaluation/refresh lock_timeout
        # =============================================
        eval_lock_name = f"evaluation_{user_id}_{course_id}"
        eval_lock_session = async_session_factory()
        try:
            lr = await eval_lock_session.execute(
                text("SELECT GET_LOCK(:name, 0)"), {"name": eval_lock_name}
            )
            chk("eval lock acquired", lr.scalar() == 1)

            print("  (waiting ~5s for eval lock timeout...)")
            with patch("app.api.v1.evaluation.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
                mock_agent.return_value = {"progress_table": {"columns": [], "rows": []}}
                r = await client.post("/api/v1/evaluation/refresh", headers=headers, json={"course_id": course_id})
                chk("eval lock held → 202", r.status_code == 202)
                task_id = r.json()["data"]["task_id"]
                result = await _poll_task(client, task_id, headers, timeout=15)
                chk("eval lock held → task failed", result and result["status"] == "failed")
                chk("eval lock held → error_code=lock_timeout",
                    result and result.get("error_code") == "lock_timeout")
        finally:
            await eval_lock_session.execute(
                text("SELECT RELEASE_LOCK(:name)"), {"name": eval_lock_name}
            )
            await eval_lock_session.close()

        # =============================================
        # 3. learning-path/refresh lock_timeout
        # =============================================
        lp_lock_name = f"learningpath_{user_id}_{course_id}"
        lp_lock_session = async_session_factory()
        try:
            lr = await lp_lock_session.execute(
                text("SELECT GET_LOCK(:name, 0)"), {"name": lp_lock_name}
            )
            chk("lp lock acquired", lr.scalar() == 1)

            print("  (waiting ~5s for lp lock timeout...)")
            with patch("app.api.v1.learning_path.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
                mock_agent.return_value = {"nodes": [], "edges": [], "current_position": None}
                r = await client.post("/api/v1/learning-path/refresh", headers=headers, json={"course_id": course_id})
                chk("lp lock held → 202", r.status_code == 202)
                task_id = r.json()["data"]["task_id"]
                result = await _poll_task(client, task_id, headers, timeout=15)
                chk("lp lock held → task failed", result and result["status"] == "failed")
                chk("lp lock held → error_code=lock_timeout",
                    result and result.get("error_code") == "lock_timeout")
        finally:
            await lp_lock_session.execute(
                text("SELECT RELEASE_LOCK(:name)"), {"name": lp_lock_name}
            )
            await lp_lock_session.close()

        # =============================================
        # 4. Lock competition: concurrent refresh → single active row
        # =============================================
        print("\n-- 4. lock competition --")
        with patch("app.api.v1.profile.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = {
                "modal_preference": {},
                "guidance_level_suggestion": {"recommended": "L3"},
            }

            async def _send_refresh():
                r = await client.post("/api/v1/profile/refresh", headers=headers, json={"course_id": course_id})
                return r.json()["data"]["task_id"]

            # Concurrent requests — both background tasks compete for the same lock
            t1, t2 = await asyncio.gather(_send_refresh(), _send_refresh())
            chk("competition → both 202", bool(t1) and bool(t2))

            r1 = await _poll_task(client, t1, headers, timeout=15)
            r2 = await _poll_task(client, t2, headers, timeout=15)
            chk("competition → both terminal",
                r1 and r2 and r1["status"] in ("completed", "failed") and r2["status"] in ("completed", "failed"))

            # Verify only one active row
            async with async_session_factory() as db:
                count_r = await db.execute(
                    select(func.count(UserProfile.id)).where(
                        UserProfile.user_id == user_id,
                        UserProfile.course_id == course_id,
                        UserProfile.is_deleted == False,
                    )
                )
                active_count = count_r.scalar()
            chk("competition → single active row", active_count == 1)

    print(f"\n{'='*50}")
    print(f"  Total: {ok} OK, {fail} FAIL")
    return fail == 0


if __name__ == "__main__":
    import sys
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
