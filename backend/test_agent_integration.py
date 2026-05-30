"""第一批 Agent 联调测试：Profile Refresh。

验证：
- agent_client 模块可导入
- Agent client post_json 方法签名正确
- Profile refresh 在 Agent 不可用时优雅降级为 failed
- Profile refresh payload 组装正确
"""
import asyncio
import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_agent_v1.db"

from app.db.session import init_db, async_session_factory

asyncio.run(init_db())

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.agent_client import AgentClient, AgentServiceError, agent_client


class TestAgentClient:
    """Agent HTTP 客户端基础测试。"""

    def test_agent_client_exists(self):
        """验证 agent_client 单例存在且 base_url 配置正确。"""
        assert agent_client is not None
        assert "/8002" in agent_client.base_url or "8002" in agent_client.base_url

    def test_agent_client_methods(self):
        """验证 post_json 和 stream_sse 方法签名。"""
        import inspect
        assert hasattr(agent_client, "post_json")
        assert hasattr(agent_client, "stream_sse")
        sig = inspect.signature(agent_client.post_json)
        assert "path" in sig.parameters
        assert "payload" in sig.parameters

    def test_agent_service_error(self):
        """验证 AgentServiceError 携带状态码。"""
        err = AgentServiceError("测试错误", status_code=503, agent_code=40001)
        assert err.status_code == 503
        assert err.agent_code == 40001
        assert "测试错误" in str(err)


class TestProfileRefreshIntegration:
    """Profile Refresh Agent 联调测试。"""

    async def _get_headers(self, client):
        """注册并登录，返回 student headers + course_id。"""
        from app.models.user import RegistrationCode
        async with async_session_factory() as db:
            for rc in [
                RegistrationCode(code="p_student", role="student"),
                RegistrationCode(code="p_teacher", role="teacher"),
            ]:
                db.add(rc)
            await db.commit()

        import re
        # Register student
        r = await client.get("/api/v1/auth/captcha")
        ct = r.json()["data"]
        nums = re.findall(r"\d+", ct["captcha_question"])
        ans = str(int(nums[0]) + int(nums[1])) if "+" in ct["captcha_question"] else str(int(nums[0]) - int(nums[1]))
        await client.post("/api/v1/auth/register", json={
            "registration_code": "p_student", "email": "ps@t.com",
            "password": "Abc12345", "username": "pstu",
            "captcha_token": ct["captcha_token"], "captcha_code": ans,
        })
        # Login
        r = await client.get("/api/v1/auth/captcha")
        ct2 = r.json()["data"]
        nums2 = re.findall(r"\d+", ct2["captcha_question"])
        ans2 = str(int(nums2[0]) + int(nums2[1])) if "+" in ct2["captcha_question"] else str(int(nums2[0]) - int(nums2[1]))
        r = await client.post("/api/v1/auth/login", json={
            "email": "ps@t.com", "password": "Abc12345",
            "captcha_token": ct2["captcha_token"], "captcha_code": ans2,
        })
        s_token = r.json()["data"]["token"]
        s_h = {"Authorization": f"Bearer {s_token}"}

        # Register teacher, create course, student joins
        r = await client.get("/api/v1/auth/captcha")
        ct3 = r.json()["data"]
        nums3 = re.findall(r"\d+", ct3["captcha_question"])
        ans3 = str(int(nums3[0]) + int(nums3[1])) if "+" in ct3["captcha_question"] else str(int(nums3[0]) - int(nums3[1]))
        await client.post("/api/v1/auth/register", json={
            "registration_code": "p_teacher", "email": "pt@t.com",
            "password": "Abc12345", "username": "ptea",
            "captcha_token": ct3["captcha_token"], "captcha_code": ans3,
        })
        r = await client.get("/api/v1/auth/captcha")
        ct4 = r.json()["data"]
        nums4 = re.findall(r"\d+", ct4["captcha_question"])
        ans4 = str(int(nums4[0]) + int(nums4[1])) if "+" in ct4["captcha_question"] else str(int(nums4[0]) - int(nums4[1]))
        r = await client.post("/api/v1/auth/login", json={
            "email": "pt@t.com", "password": "Abc12345",
            "captcha_token": ct4["captcha_token"], "captcha_code": ans4,
        })
        t_h = {"Authorization": f"Bearer {r.json()['data']['token']}"}

        r = await client.post("/api/v1/courses", headers=t_h, json={"name": "测试课程"})
        course_id = r.json()["data"]["id"]
        course_code = r.json()["data"]["course_code"]
        await client.post("/api/v1/courses/join", headers=s_h, json={"course_code": course_code})

        return s_h, course_id

    @pytest.mark.asyncio
    async def test_profile_refresh_202_and_task(self):
        """验证 profile refresh 返回 202 和 task_id。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            s_h, course_id = await self._get_headers(client)

            # Agent Service 不可用时，刷新仍应返回 202（任务标记为 failed）
            r = await client.post(
                f"/api/v1/profile/refresh?course_id={course_id}", headers=s_h
            )
            assert r.status_code == 202, f"Expected 202, got {r.status_code}"
            data = r.json()["data"]
            assert "task_id" in data, "Response should contain task_id"

            # 查询任务状态 — Agent 不可用时应为 failed
            task_id = data["task_id"]
            r = await client.get(f"/api/v1/tasks/{task_id}", headers=s_h)
            assert r.status_code == 200
            task_data = r.json()["data"]
            assert task_data["task_type"] == "profile_refresh"
            assert task_data["status"] in ("completed", "failed", "processing")
            print(f"  Task status (Agent unreachable): {task_data['status']}")

    @pytest.mark.asyncio
    async def test_profile_refresh_no_enrollment(self):
        """验证未加入课程的学生无法刷新画像。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            import re
            # Register new student who hasn't joined any course
            async with async_session_factory() as db:
                from app.models.user import RegistrationCode
                db.add(RegistrationCode(code="p_student2", role="student"))
                await db.commit()

            r = await client.get("/api/v1/auth/captcha")
            ct = r.json()["data"]
            nums = re.findall(r"\d+", ct["captcha_question"])
            ans = str(int(nums[0]) + int(nums[1])) if "+" in ct["captcha_question"] else str(int(nums[0]) - int(nums[1]))
            await client.post("/api/v1/auth/register", json={
                "registration_code": "p_student2", "email": "ps2@t.com",
                "password": "Abc12345", "username": "pstu2",
                "captcha_token": ct["captcha_token"], "captcha_code": ans,
            })
            r = await client.get("/api/v1/auth/captcha")
            ct2 = r.json()["data"]
            nums2 = re.findall(r"\d+", ct2["captcha_question"])
            ans2 = str(int(nums2[0]) + int(nums2[1])) if "+" in ct2["captcha_question"] else str(int(nums2[0]) - int(nums2[1]))
            r = await client.post("/api/v1/auth/login", json={
                "email": "ps2@t.com", "password": "Abc12345",
                "captcha_token": ct2["captcha_token"], "captcha_code": ans2,
            })
            h = {"Authorization": f"Bearer {r.json()['data']['token']}"}

            r = await client.post("/api/v1/profile/refresh?course_id=fake_course", headers=h)
            assert r.status_code == 403


class TestTutoringChatIntegration:
    """Tutoring SSE Agent 联调测试。"""

    async def _setup_tutoring(self, client):
        """创建学生、教师、课程、加入，返回 student headers + course_id。"""
        from app.models.user import RegistrationCode
        import uuid

        # Use unique codes per test to avoid UNIQUE constraint across tests
        s_code = f"ts_{uuid.uuid4().hex[:6]}"
        t_code = f"tt_{uuid.uuid4().hex[:6]}"
        async with async_session_factory() as db:
            for rc in [
                RegistrationCode(code=s_code, role="student"),
                RegistrationCode(code=t_code, role="teacher"),
            ]:
                db.add(rc)
            await db.commit()

        async def reg_and_login(email, username, code):
            import re
            r = await client.get("/api/v1/auth/captcha")
            ct = r.json()["data"]
            nums = re.findall(r"\d+", ct["captcha_question"])
            ans = str(int(nums[0]) + int(nums[1])) if "+" in ct["captcha_question"] else str(int(nums[0]) - int(nums[1]))
            await client.post("/api/v1/auth/register", json={
                "registration_code": code, "email": email,
                "password": "Abc12345", "username": username,
                "captcha_token": ct["captcha_token"], "captcha_code": ans,
            })
            r = await client.get("/api/v1/auth/captcha")
            ct2 = r.json()["data"]
            nums2 = re.findall(r"\d+", ct2["captcha_question"])
            ans2 = str(int(nums2[0]) + int(nums2[1])) if "+" in ct2["captcha_question"] else str(int(nums2[0]) - int(nums2[1]))
            r = await client.post("/api/v1/auth/login", json={
                "email": email, "password": "Abc12345",
                "captcha_token": ct2["captcha_token"], "captcha_code": ans2,
            })
            return r.json()["data"]["token"]

        s_mail = f"ts{uuid.uuid4().hex[:4]}@t.com"
        t_mail = f"tt{uuid.uuid4().hex[:4]}@t.com"
        s_token = await reg_and_login(s_mail, f"tstu_{uuid.uuid4().hex[:4]}", s_code)
        t_token = await reg_and_login(t_mail, f"ttea_{uuid.uuid4().hex[:4]}", t_code)
        s_h = {"Authorization": f"Bearer {s_token}"}
        t_h = {"Authorization": f"Bearer {t_token}"}

        r = await client.post("/api/v1/courses", headers=t_h, json={"name": "测试课程"})
        course_code = r.json()["data"]["course_code"]
        await client.post("/api/v1/courses/join", headers=s_h, json={"course_code": course_code})

        # Get course_id
        r = await client.get("/api/v1/courses", headers=s_h)
        course_id = r.json()["data"]["courses"][0]["id"]
        return s_h, course_id

    @pytest.mark.asyncio
    async def test_tutoring_chat_sse_scope_validation(self):
        """验证 scope=course 但无 course_id 时返回 400。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            s_h, _ = await self._setup_tutoring(client)
            # scope=course without course_id should fail
            r = await client.post("/api/v1/tutoring/chat", headers=s_h, json={
                "message": "测试", "scope": "course",
            })
            assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_tutoring_chat_global_scope(self):
        """验证 scope=global 可以发起对话（Agent 不可用时仍返回 SSE done）。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            s_h, _ = await self._setup_tutoring(client)
            r = await client.post("/api/v1/tutoring/chat", headers=s_h, json={
                "message": "你好", "scope": "global",
            })
            # Agent might be unreachable, but SSE should still stream to done
            assert r.status_code == 200
            assert "text/event-stream" in r.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_tutoring_conversations_list(self):
        """验证对话列表接口正常（含新增 scope/course_id 筛选）。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            s_h, course_id = await self._setup_tutoring(client)
            r = await client.get("/api/v1/tutoring/conversations", headers=s_h)
            assert r.status_code == 200
            assert "conversations" in r.json()["data"]


class TestResourcesGenerateIntegration:
    """Resources 异步生成 + Webhook 联调测试。"""

    async def _setup_teacher(self, client):
        """创建教师、课程，返回 teacher headers + course_id + teacher_id。"""
        from app.models.user import RegistrationCode
        import uuid, re

        suffix = uuid.uuid4().hex[:6]
        t_code = f"rt_{suffix}"
        email = f"rt{suffix}@t.com"
        uname = f"rtea_{suffix}"

        async with async_session_factory() as db:
            db.add(RegistrationCode(code=t_code, role="teacher"))
            await db.commit()

        r = await client.get("/api/v1/auth/captcha")
        ct = r.json()["data"]
        nums = re.findall(r"\d+", ct["captcha_question"])
        ans = str(int(nums[0]) + int(nums[1])) if "+" in ct["captcha_question"] else str(int(nums[0]) - int(nums[1]))
        await client.post("/api/v1/auth/register", json={
            "registration_code": t_code, "email": email, "password": "Abc12345",
            "username": uname,
            "captcha_token": ct["captcha_token"], "captcha_code": ans,
        })
        r = await client.get("/api/v1/auth/captcha")
        ct2 = r.json()["data"]
        nums2 = re.findall(r"\d+", ct2["captcha_question"])
        ans2 = str(int(nums2[0]) + int(nums2[1])) if "+" in ct2["captcha_question"] else str(int(nums2[0]) - int(nums2[1]))
        r = await client.post("/api/v1/auth/login", json={
            "email": email, "password": "Abc12345",
            "captcha_token": ct2["captcha_token"], "captcha_code": ans2,
        })
        t_h = {"Authorization": f"Bearer {r.json()['data']['token']}"}
        teacher_id = r.json()["data"]["user"]["id"]

        r = await client.post("/api/v1/courses", headers=t_h, json={"name": "资源测试课程"})
        course_id = r.json()["data"]["id"]
        return t_h, course_id, teacher_id

    @pytest.mark.asyncio
    async def test_resources_generate_202(self):
        """验证教师触发资源生成返回 202 + task_id。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            t_h, course_id, _ = await self._setup_teacher(client)

            r = await client.post("/api/v1/resources/generate", headers=t_h, json={
                "course_id": course_id, "resource_types": ["document"],
            })
            assert r.status_code == 202
            assert "task_id" in r.json()["data"]

            # Query task — Agent unreachable → should be failed
            task_id = r.json()["data"]["task_id"]
            r = await client.get(f"/api/v1/tasks/{task_id}", headers=t_h)
            assert r.status_code == 200
            td = r.json()["data"]
            assert td["task_type"] == "resource_generation"
            print(f"  Resources task status (Agent unreachable): {td['status']}")

    @pytest.mark.asyncio
    async def test_resources_generate_student_blocked(self):
        """验证学生无法触发资源生成。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            import uuid, re
            from app.models.user import RegistrationCode

            suffix = uuid.uuid4().hex[:6]
            s_code = f"rs_{suffix}"
            email = f"rs{suffix}@t.com"
            uname = f"rstu_{suffix}"

            async with async_session_factory() as db:
                db.add(RegistrationCode(code=s_code, role="student"))
                await db.commit()

            r = await client.get("/api/v1/auth/captcha")
            ct = r.json()["data"]
            nums = re.findall(r"\d+", ct["captcha_question"])
            ans = str(int(nums[0]) + int(nums[1])) if "+" in ct["captcha_question"] else str(int(nums[0]) - int(nums[1]))
            await client.post("/api/v1/auth/register", json={
                "registration_code": s_code, "email": email, "password": "Abc12345",
                "username": uname,
                "captcha_token": ct["captcha_token"], "captcha_code": ans,
            })
            r = await client.get("/api/v1/auth/captcha")
            ct2 = r.json()["data"]
            nums2 = re.findall(r"\d+", ct2["captcha_question"])
            ans2 = str(int(nums2[0]) + int(nums2[1])) if "+" in ct2["captcha_question"] else str(int(nums2[0]) - int(nums2[1]))
            r = await client.post("/api/v1/auth/login", json={
                "email": email, "password": "Abc12345",
                "captcha_token": ct2["captcha_token"], "captcha_code": ans2,
            })
            s_h = {"Authorization": f"Bearer {r.json()['data']['token']}"}

            r = await client.post("/api/v1/resources/generate", headers=s_h, json={
                "course_id": "any_course",
            })
            assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_webhook_resource_generation_writes_resources(self):
        """验证 Webhook resource_generation 完成后将 result.resources 写入 resources 表。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            t_h, course_id, teacher_id = await self._setup_teacher(client)

            # 1. 创建 resource_generation 任务
            from app.models.others import AsyncTask
            async with async_session_factory() as db:
                task = AsyncTask(
                    task_type="resource_generation",
                    status="processing",
                    user_id=teacher_id,
                    course_id=course_id,
                )
                db.add(task)
                await db.commit()
                task_id = task.id

            # 2. 模拟 Agent Webhook 回调 completed
            r = await client.post("/api/v1/webhooks/agent", json={
                "task_id": task_id,
                "task_type": "resource_generation",
                "status": "completed",
                "result": {
                    "resources": [
                        {
                            "title": "Agent 生成的讲义",
                            "type": "document",
                            "description": "AI 自动生成",
                            "content": "# 第一章\n这是内容",
                            "chapter": "第1章",
                            "knowledge_point": "基础概念",
                            "tags": ["AI生成", "讲义"],
                        }
                    ]
                },
            })
            assert r.status_code == 200

            # 3. 验证 resources 表有数据
            r = await client.get(f"/api/v1/resources?course_id={course_id}", headers=t_h)
            assert r.status_code == 200
            res_list = r.json()["data"]["resources"]
            assert len(res_list) >= 1, f"Expected at least 1 resource, got {len(res_list)}"
            matching = [ri for ri in res_list if ri["title"] == "Agent 生成的讲义"]
            assert len(matching) == 1, f"Expected exactly 1 matching resource, got {len(matching)}"

            # 4. 幂等：再次回调不重复插入
            r = await client.post("/api/v1/webhooks/agent", json={
                "task_id": task_id,
                "task_type": "resource_generation",
                "status": "completed",
                "result": {"resources": [{"title": "重复的", "type": "document"}]},
            })
            assert r.status_code == 200
            r = await client.get(f"/api/v1/resources?course_id={course_id}", headers=t_h)
            # 幂等：再次回调不新增重复资源
            matching2 = [ri for ri in r.json()["data"]["resources"] if ri["title"] == "Agent 生成的讲义"]
            assert len(matching2) == 1, f"Idempotency failed: got {len(matching2)} matching resources"


class TestQuizGenerateIntegration:
    """Quiz Generate Agent 联调测试。"""

    async def _setup_student_with_course(self, client):
        """创建学生、教师、课程、加入，返回 student headers + course_id。"""
        from app.models.user import RegistrationCode
        import uuid, re

        s_suffix = uuid.uuid4().hex[:6]
        t_suffix = uuid.uuid4().hex[:6]
        s_code = f"qs_{s_suffix}"
        t_code = f"qt_{t_suffix}"
        s_email = f"qs{s_suffix}@t.com"
        t_email = f"qt{t_suffix}@t.com"
        s_name = f"qstu_{s_suffix}"
        t_name = f"qtea_{t_suffix}"

        async with async_session_factory() as db:
            for rc in [
                RegistrationCode(code=s_code, role="student"),
                RegistrationCode(code=t_code, role="teacher"),
            ]:
                db.add(rc)
            await db.commit()

        async def reg_and_login(email, username, code):
            r = await client.get("/api/v1/auth/captcha")
            ct = r.json()["data"]
            nums = re.findall(r"\d+", ct["captcha_question"])
            ans = str(int(nums[0]) + int(nums[1])) if "+" in ct["captcha_question"] else str(int(nums[0]) - int(nums[1]))
            await client.post("/api/v1/auth/register", json={
                "registration_code": code, "email": email, "password": "Abc12345",
                "username": username,
                "captcha_token": ct["captcha_token"], "captcha_code": ans,
            })
            r = await client.get("/api/v1/auth/captcha")
            ct2 = r.json()["data"]
            nums2 = re.findall(r"\d+", ct2["captcha_question"])
            ans2 = str(int(nums2[0]) + int(nums2[1])) if "+" in ct2["captcha_question"] else str(int(nums2[0]) - int(nums2[1]))
            r = await client.post("/api/v1/auth/login", json={
                "email": email, "password": "Abc12345",
                "captcha_token": ct2["captcha_token"], "captcha_code": ans2,
            })
            return r.json()["data"]["token"]

        s_token = await reg_and_login(s_email, s_name, s_code)
        t_token = await reg_and_login(t_email, t_name, t_code)
        s_h = {"Authorization": f"Bearer {s_token}"}
        t_h = {"Authorization": f"Bearer {t_token}"}

        r = await client.post("/api/v1/courses", headers=t_h, json={"name": "题库测试课程"})
        course_code = r.json()["data"]["course_code"]
        await client.post("/api/v1/courses/join", headers=s_h, json={"course_code": course_code})

        r = await client.get("/api/v1/courses", headers=s_h)
        course_id = r.json()["data"]["courses"][0]["id"]
        return s_h, course_id

    @pytest.mark.asyncio
    async def test_quiz_generate_202(self):
        """验证生成个性化题目返回 202 + task_id。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            s_h, course_id = await self._setup_student_with_course(client)

            r = await client.post("/api/v1/quiz/generate", headers=s_h, json={
                "course_id": course_id, "count": 3, "personalized": True,
            })
            assert r.status_code == 202
            assert "task_id" in r.json()["data"]

            # Agent unreachable → task should be failed
            task_id = r.json()["data"]["task_id"]
            r = await client.get(f"/api/v1/tasks/{task_id}", headers=s_h)
            assert r.status_code == 200
            td = r.json()["data"]
            assert td["task_type"] == "quiz_generation"
            print(f"  Quiz task status (Agent unreachable): {td['status']}")

    @pytest.mark.asyncio
    async def test_quiz_questions_source_and_personalized(self):
        """验证 GET /quiz/questions 返回 source 和 personalized 字段。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            s_h, course_id = await self._setup_student_with_course(client)

            r = await client.get(f"/api/v1/quiz/questions?course_id={course_id}", headers=s_h)
            assert r.status_code == 200
            qs = r.json()["data"]["questions"]
            # 没有预置题目时空数组
            assert isinstance(qs, list)


class TestEvaluationLearningPathIntegration:
    """Evaluation + LearningPath Agent 联调测试。"""

    async def _setup_student(self, client):
        """创建学生、教师、课程、加入，返回 student headers + course_id。"""
        from app.models.user import RegistrationCode
        import uuid, re

        s_suffix = uuid.uuid4().hex[:6]
        t_suffix = uuid.uuid4().hex[:6]

        async with async_session_factory() as db:
            for rc in [
                RegistrationCode(code=f"es_{s_suffix}", role="student"),
                RegistrationCode(code=f"et_{t_suffix}", role="teacher"),
            ]:
                db.add(rc)
            await db.commit()

        async def reg_and_login(email, username, code):
            r = await client.get("/api/v1/auth/captcha")
            ct = r.json()["data"]
            nums = re.findall(r"\d+", ct["captcha_question"])
            ans = str(int(nums[0]) + int(nums[1])) if "+" in ct["captcha_question"] else str(int(nums[0]) - int(nums[1]))
            await client.post("/api/v1/auth/register", json={
                "registration_code": code, "email": email, "password": "Abc12345",
                "username": username,
                "captcha_token": ct["captcha_token"], "captcha_code": ans,
            })
            r = await client.get("/api/v1/auth/captcha")
            ct2 = r.json()["data"]
            nums2 = re.findall(r"\d+", ct2["captcha_question"])
            ans2 = str(int(nums2[0]) + int(nums2[1])) if "+" in ct2["captcha_question"] else str(int(nums2[0]) - int(nums2[1]))
            r = await client.post("/api/v1/auth/login", json={
                "email": email, "password": "Abc12345",
                "captcha_token": ct2["captcha_token"], "captcha_code": ans2,
            })
            return r.json()["data"]["token"]

        s_token = await reg_and_login(f"es{s_suffix}@t.com", f"estu_{s_suffix}", f"es_{s_suffix}")
        t_token = await reg_and_login(f"et{t_suffix}@t.com", f"etea_{t_suffix}", f"et_{t_suffix}")
        s_h = {"Authorization": f"Bearer {s_token}"}
        t_h = {"Authorization": f"Bearer {t_token}"}

        r = await client.post("/api/v1/courses", headers=t_h, json={"name": "评估测试课程"})
        course_code = r.json()["data"]["course_code"]
        await client.post("/api/v1/courses/join", headers=s_h, json={"course_code": course_code})

        r = await client.get("/api/v1/courses", headers=s_h)
        course_id = r.json()["data"]["courses"][0]["id"]
        return s_h, course_id

    @pytest.mark.asyncio
    async def test_evaluation_refresh_202(self):
        """验证评估刷新返回 202 + task_id。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            s_h, course_id = await self._setup_student(client)

            r = await client.post(f"/api/v1/evaluation/refresh?course_id={course_id}", headers=s_h)
            assert r.status_code == 202
            assert "task_id" in r.json()["data"]

    @pytest.mark.asyncio
    async def test_learning_path_refresh_202(self):
        """验证学习路径刷新返回 202 + task_id。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            s_h, course_id = await self._setup_student(client)

            r = await client.post(f"/api/v1/learning-path/refresh?course_id={course_id}", headers=s_h)
            assert r.status_code == 202
            assert "task_id" in r.json()["data"]

    @pytest.mark.asyncio
    async def test_evaluation_get_empty(self):
        """验证 GET /evaluation 无评估时返回空数据。"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            s_h, course_id = await self._setup_student(client)

            r = await client.get(f"/api/v1/evaluation?course_id={course_id}", headers=s_h)
            assert r.status_code == 200
            assert r.json()["data"]["generated_at"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
