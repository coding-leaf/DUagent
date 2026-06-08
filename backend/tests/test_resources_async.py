"""MySQL integration test for resources/generate + webhooks/agent.

Covers: generate 202, webhook completed/failed/idempotent, auth, payload validation.
Requires MySQL + WEBHOOK_SECRET in .env. Agent calls mocked.

Run: python test_resources_async.py
"""
import asyncio
import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+aiomysql://root:123456@127.0.0.1:3306/duagent?charset=utf8mb4",
)

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import async_session_factory
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.course import Course
from app.models.user import RegistrationCode
from app.models.others import AsyncTask, Resource
from sqlalchemy import func, select


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


def _webhook_headers(with_secret=True):
    h = {"Content-Type": "application/json"}
    if with_secret:
        h["X-Webhook-Secret"] = "duagent-webhook-dev-secret"
    return h


async def _create_bound_ready_course(
    teacher_id,
    *,
    knowledge_status="ready",
    chunk_count=3,
):
    suffix = uuid.uuid4().hex[:8]
    class_course_id = f"class_{suffix}"
    catalog_id = f"catalog_{suffix}"
    class_name = f"Bound Course {suffix}"
    async with async_session_factory() as db:
        course = Course(
            id=class_course_id,
            name=class_name,
            course_code=f"C{suffix[:7]}",
            teacher_id=teacher_id,
        )
        catalog = CourseCatalog(
            id=catalog_id,
            title=f"Ready Catalog {suffix}",
            status="ready",
            knowledge_status=knowledge_status,
            chunk_count=chunk_count,
        )
        offering = CourseOffering(
            id=class_course_id,
            name=class_name,
            catalog_id=catalog_id,
            teacher_id=teacher_id,
            class_code=course.course_code,
        )
        db.add_all([course, catalog, offering])
        await db.commit()
    return {
        "class_course_id": class_course_id,
        "catalog_id": catalog_id,
        "catalog_title": f"Ready Catalog {suffix}",
    }


async def _count_resource_generation_tasks(course_id, user_id):
    async with async_session_factory() as db:
        result = await db.execute(
            select(func.count()).select_from(AsyncTask).where(
                AsyncTask.task_type == "resource_generation",
                AsyncTask.course_id == course_id,
                AsyncTask.user_id == user_id,
            )
        )
        return result.scalar() or 0


@pytest.mark.asyncio
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
            RegistrationCode(code=f"stu_{uuid.uuid4().hex[:8]}", role="student"),
            RegistrationCode(code=f"tea_{uuid.uuid4().hex[:8]}", role="teacher"),
        ]
        async with async_session_factory() as db:
            db.add_all(codes)
            await db.commit()
            teacher_code = codes[1].code

        headers, user_id = await _register_and_login(client, teacher_code, email, uname)

        # Create a legacy course without CourseOffering binding
        r = await client.post("/api/v1/courses", json={"name": "Test Course"}, headers=headers)
        assert r.status_code == 201, f"Course creation failed: {r.json()}"
        legacy_course_id = r.json()["data"]["id"]
        course_context = await _create_bound_ready_course(user_id)
        course_id = course_context["class_course_id"]

        # =============================================
        # 1. resources/generate ready gate
        # =============================================
        print("\n-- 1. resources/generate ready gate --")

        legacy_count_before = await _count_resource_generation_tasks(legacy_course_id, user_id)
        r = await client.post("/api/v1/resources/generate", json={
            "course_id": legacy_course_id,
        }, headers=headers)
        legacy_count_after = await _count_resource_generation_tasks(legacy_course_id, user_id)
        chk("legacy course without offering → 404", r.status_code == 404)
        chk("legacy course without offering → course_catalog_missing",
            r.json().get("detail", {}).get("code") == "course_catalog_missing")
        chk("legacy course without offering → no AsyncTask",
            legacy_count_after == legacy_count_before)

        dirty_context = await _create_bound_ready_course(
            user_id,
            knowledge_status="dirty",
            chunk_count=3,
        )
        dirty_count_before = await _count_resource_generation_tasks(
            dirty_context["class_course_id"],
            user_id,
        )
        r = await client.post("/api/v1/resources/generate", json={
            "course_id": dirty_context["class_course_id"],
        }, headers=headers)
        dirty_count_after = await _count_resource_generation_tasks(
            dirty_context["class_course_id"],
            user_id,
        )
        chk("dirty catalog → 409", r.status_code == 409)
        chk("dirty catalog → course_material_missing",
            r.json().get("detail", {}).get("code") == "course_material_missing")
        chk("dirty catalog → no AsyncTask", dirty_count_after == dirty_count_before)

        partial_context = await _create_bound_ready_course(
            user_id,
            knowledge_status="partial",
            chunk_count=2,
        )
        with patch("app.api.v1.resources.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = {"task_id": "ignored", "estimated_duration": 60}
            r = await client.post("/api/v1/resources/generate", json={
                "course_id": partial_context["class_course_id"],
            }, headers=headers)
            chk("partial catalog → 202", r.status_code == 202)
            partial_task_id = r.json()["data"]["task_id"]
            chk("partial catalog → task_id present", bool(partial_task_id))
            partial_payload = mock_agent.await_args.args[1]
            chk("partial catalog → agent receives catalog_id",
                partial_payload["course_id"] == partial_context["catalog_id"])

            rt = await client.get(f"/api/v1/tasks/{partial_task_id}", headers=headers)
            td = rt.json().get("data", {})
            chk("partial catalog → task_type=resource_generation",
                td.get("task_type") == "resource_generation")
            chk("partial catalog → class_course_id recorded",
                td.get("result", {}).get("class_course_id") == partial_context["class_course_id"])
            chk("partial catalog → catalog_id recorded",
                td.get("result", {}).get("catalog_id") == partial_context["catalog_id"])
            chk("partial catalog → degraded recorded",
                td.get("result", {}).get("degraded") is True)

        print("\n-- 1b. resources/generate success --")
        with patch("app.api.v1.resources.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = {"task_id": "ignored", "estimated_duration": 60}
            r = await client.post("/api/v1/resources/generate", json={
                "course_id": course_id,
            }, headers=headers)
            chk("generate → 202", r.status_code == 202)
            task_id = r.json()["data"]["task_id"]
            chk("generate → task_id present", bool(task_id))
            success_payload = mock_agent.await_args.args[1]
            chk("generate → agent receives catalog_id",
                success_payload["course_id"] == course_context["catalog_id"])

            rt = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
            td = rt.json().get("data", {})
            chk("generate → task_type=resource_generation",
                td.get("task_type") == "resource_generation")

        # =============================================
        # 2. webhook completed → resources written
        # =============================================
        print("\n-- 2. webhook completed → resources written --")
        webhook_payload = {
            "task_id": task_id,
            "task_type": "resource_generation",
            "status": "completed",
            "result": {
                "resources": [
                    {"title": "Test Doc", "type": "document", "chapter": "ch1",
                     "knowledge_point": "kp1", "description": "doc description",
                     "content": "content here", "tags": []},
                    {"title": "Test Code", "type": "code", "chapter": "ch2",
                     "knowledge_point": "kp2", "description": "code description",
                     "content": "print(1)", "tags": []},
                ]
            },
        }
        r = await client.post("/api/v1/webhooks/agent", json=webhook_payload,
                              headers=_webhook_headers())
        chk("webhook completed → 200", r.status_code == 200)

        rt = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
        td = rt.json().get("data", {})
        chk("webhook completed → task completed", td.get("status") == "completed")

        async with async_session_factory() as db:
            res_r = await db.execute(
                select(Resource).where(Resource.is_deleted == False)
            )
            resources = res_r.scalars().all()
            chk("webhook completed → resources written", len(resources) >= 2)

        # =============================================
        # 3. webhook failed → task failed + error_code
        # =============================================
        print("\n-- 3. webhook failed --")
        async with async_session_factory() as db:
            fail_task = AsyncTask(
                task_type="resource_generation",
                status="processing",
                user_id=user_id,
                course_id=course_id,
            )
            db.add(fail_task)
            await db.commit()
            fail_task_id = fail_task.id

        failed_payload = {
            "task_id": fail_task_id,
            "task_type": "resource_generation",
            "status": "failed",
            "error_code": "agent_crash",
            "error_message": "Agent process died",
        }
        r = await client.post("/api/v1/webhooks/agent", json=failed_payload,
                              headers=_webhook_headers())
        chk("webhook failed → 200", r.status_code == 200)

        rt = await client.get(f"/api/v1/tasks/{fail_task_id}", headers=headers)
        td = rt.json().get("data", {})
        chk("webhook failed → task status=failed", td.get("status") == "failed")
        chk("webhook failed → error_code present",
            td.get("error_code") and td["error_code"] != "")

        # =============================================
        # 4. webhook idempotency
        # =============================================
        print("\n-- 4. webhook idempotency --")
        resource_count_before = len(resources)

        r = await client.post("/api/v1/webhooks/agent", json=webhook_payload,
                              headers=_webhook_headers())
        chk("webhook idempotent → 200", r.status_code == 200)

        async with async_session_factory() as db:
            res_r = await db.execute(
                select(Resource).where(Resource.is_deleted == False)
            )
            resource_count_after = len(res_r.scalars().all())
        chk("webhook idempotent → no duplicate resources",
            resource_count_after == resource_count_before)

        # =============================================
        # 5. webhook auth — correct secret + business processed
        # =============================================
        print("\n-- 5. webhook auth (correct secret) --")
        async with async_session_factory() as db:
            auth_task = AsyncTask(
                task_type="resource_generation",
                status="processing",
                user_id=user_id,
                course_id=course_id,
            )
            db.add(auth_task)
            await db.commit()
            auth_task_id = auth_task.id

        auth_payload = {
            "task_id": auth_task_id,
            "task_type": "resource_generation",
            "status": "completed",
            "result": {"resources": [{"title": "Auth Test", "type": "document",
                                      "chapter": "ch1", "knowledge_point": "kp1",
                                      "description": "auth description",
                                      "content": "x", "tags": []}]},
        }
        r = await client.post("/api/v1/webhooks/agent", json=auth_payload,
                              headers=_webhook_headers(with_secret=True))
        chk("auth correct → 200", r.status_code == 200)

        rt = await client.get(f"/api/v1/tasks/{auth_task_id}", headers=headers)
        td = rt.json().get("data", {})
        chk("auth correct → task completed (business processed)",
            td.get("status") == "completed")

        # =============================================
        # 6. webhook auth — bad secret → 401
        # =============================================
        print("\n-- 6. webhook auth (bad secret) --")
        bad_headers = _webhook_headers()
        bad_headers["X-Webhook-Secret"] = "wrong-secret"
        r = await client.post("/api/v1/webhooks/agent", json=auth_payload,
                              headers=bad_headers)
        chk("auth bad secret → 401", r.status_code == 401)

        # =============================================
        # 7. webhook task_type mismatch → 400
        # =============================================
        print("\n-- 7. webhook task_type mismatch --")
        mismatch_payload = {
            "task_id": task_id,
            "task_type": "quiz_generation",
            "status": "completed",
            "result": {},
        }
        r = await client.post("/api/v1/webhooks/agent", json=mismatch_payload,
                              headers=_webhook_headers())
        chk("task_type mismatch → 400", r.status_code == 400)

        # =============================================
        # 8. webhook malformed completed payloads → 400
        # =============================================
        print("\n-- 8. webhook malformed completed payloads --")

        async def create_processing_task():
            async with async_session_factory() as db:
                invalid_task = AsyncTask(
                    task_type="resource_generation",
                    status="processing",
                    user_id=user_id,
                    course_id=course_id,
                )
                db.add(invalid_task)
                await db.commit()
                return invalid_task.id

        invalid_payloads = [
            ("completed missing result", {"status": "completed"}),
            ("completed missing resources", {"status": "completed", "result": {}}),
            ("resources not array", {"status": "completed", "result": {"resources": {}}}),
            ("resource not object", {"status": "completed", "result": {"resources": ["bad"]}}),
            (
                "resource missing required field",
                {
                    "status": "completed",
                    "result": {
                        "resources": [
                            {
                                "title": "Missing Description",
                                "type": "document",
                                "chapter": "ch1",
                                "knowledge_point": "kp1",
                                "content": "x",
                                "tags": [],
                            }
                        ]
                    },
                },
            ),
            (
                "resource invalid type",
                {
                    "status": "completed",
                    "result": {
                        "resources": [
                            {
                                "title": "Bad Type",
                                "type": "audio",
                                "description": "bad type",
                                "chapter": "ch1",
                                "knowledge_point": "kp1",
                                "content": "x",
                                "tags": [],
                            }
                        ]
                    },
                },
            ),
        ]

        async with async_session_factory() as db:
            count_r = await db.execute(select(Resource).where(Resource.is_deleted == False))
            invalid_resource_count_before = len(count_r.scalars().all())

        for name, partial_payload in invalid_payloads:
            invalid_task_id = await create_processing_task()
            payload = {
                "task_id": invalid_task_id,
                "task_type": "resource_generation",
                **partial_payload,
            }
            r = await client.post("/api/v1/webhooks/agent", json=payload,
                                  headers=_webhook_headers())
            chk(f"{name} → 400", r.status_code == 400)

            rt = await client.get(f"/api/v1/tasks/{invalid_task_id}", headers=headers)
            td = rt.json().get("data", {})
            chk(f"{name} → task remains processing", td.get("status") == "processing")

        async with async_session_factory() as db:
            count_r = await db.execute(select(Resource).where(Resource.is_deleted == False))
            invalid_resource_count_after = len(count_r.scalars().all())
        chk("malformed completed payloads → no resources written",
            invalid_resource_count_after == invalid_resource_count_before)

        # =============================================
        # 9. webhook malformed status/failed payload → 400
        # =============================================
        print("\n-- 9. webhook malformed status/failed payload --")
        invalid_task_id = await create_processing_task()
        r = await client.post("/api/v1/webhooks/agent", json={
            "task_id": invalid_task_id,
            "task_type": "resource_generation",
            "status": "unknown",
        }, headers=_webhook_headers())
        chk("invalid status → 400", r.status_code == 400)

        failed_missing_message_task_id = await create_processing_task()
        r = await client.post("/api/v1/webhooks/agent", json={
            "task_id": failed_missing_message_task_id,
            "task_type": "resource_generation",
            "status": "failed",
        }, headers=_webhook_headers())
        chk("failed missing error_message → 400", r.status_code == 400)

    print(f"\n{'='*50}")
    print(f"  Total: {ok} OK, {fail} FAIL")
    assert fail == 0
    return fail == 0


if __name__ == "__main__":
    import sys
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
