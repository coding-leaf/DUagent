import asyncio
import os
import re

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_duagent.db"

from httpx import AsyncClient, ASGITransport

from app.db.session import init_db

asyncio.run(init_db())

from app.main import app
from app.db.session import async_session_factory
from app.models.user import RegistrationCode


async def test():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        passed = 0
        failed = 0

        def check(name, condition, detail=""):
            nonlocal passed, failed
            if condition:
                passed += 1
                print(f"  PASS {name}" + (f" — {detail}" if detail else ""))
            else:
                failed += 1
                print(f"  FAIL {name}" + (f" — {detail}" if detail else ""))

        # === Health ===
        r = await client.get("/health")
        check("Health", r.json()["status"] == "ok")

        # === Captcha ===
        r = await client.get("/api/v1/auth/captcha")
        ct = r.json()
        check("Captcha", ct["code"] == 200 and "captcha_token" in ct["data"])

        # === Seed ===
        async with async_session_factory() as db:
            db.add(RegistrationCode(code="TEST-STUDENT-99", role="student"))
            db.add(RegistrationCode(code="TEST-TEACHER-88", role="teacher"))
            db.add(RegistrationCode(code="TEST-ADMIN-77", role="admin"))
            await db.commit()

        # === Register ===
        r = await client.post("/api/v1/auth/register", json={
            "registration_code": "TEST-STUDENT-99",
            "email": "student@test.com",
            "password": "Abc12345",
            "username": "teststudent",
        })
        check("Register student", r.status_code == 201 and r.json()["data"]["user_id"])
        user_id = r.json()["data"]["user_id"]

        r = await client.post("/api/v1/auth/register", json={
            "registration_code": "TEST-TEACHER-88",
            "email": "teacher@test.com",
            "password": "Abc12345",
            "username": "testteacher",
        })
        check("Register teacher", r.status_code == 201)

        # Login helper
        async def login(email, password):
            r = await client.get("/api/v1/auth/captcha")
            ct = r.json()["data"]
            nums = re.findall(r"\d+", ct["captcha_question"])
            ans = str(int(nums[0]) + int(nums[1])) if "+" in ct["captcha_question"] else str(int(nums[0]) - int(nums[1]))
            r = await client.post("/api/v1/auth/login", json={
                "email": email, "password": password,
                "captcha_token": ct["captcha_token"], "captcha_code": ans,
            })
            return r.json()["data"]["access_token"], r.json()["data"]["refresh_token"]

        s_token, s_refresh = await login("student@test.com", "Abc12345")
        s_headers = {"Authorization": f"Bearer {s_token}"}

        t_token, _ = await login("teacher@test.com", "Abc12345")
        t_headers = {"Authorization": f"Bearer {t_token}"}

        # === GET /me ===
        r = await client.get("/api/v1/users/me", headers=s_headers)
        check("GET /me", r.json()["data"]["role"] == "student")

        # === PUT /me ===
        r = await client.put("/api/v1/users/me", headers=s_headers, json={"real_name": "张三", "major": "CS"})
        check("PUT /me", r.json()["data"]["real_name"] == "张三")

        # === Create course (teacher) ===
        r = await client.post("/api/v1/courses", headers=t_headers, json={"name": "高等数学"})
        check("Create course", r.status_code == 201 and "course_code" in r.json()["data"])
        course_id = r.json()["data"]["id"]
        course_code = r.json()["data"]["course_code"]

        # === Join course (student) ===
        r = await client.post("/api/v1/courses/join", headers=s_headers, json={"course_code": course_code})
        check("Join course", r.json()["code"] == 200)

        # === List courses ===
        r = await client.get("/api/v1/courses", headers=s_headers)
        check("List courses", len(r.json()["data"]["courses"]) == 1)

        # === Teaching: students list (direct array) ===
        r = await client.get(f"/api/v1/teaching/classes/{course_id}/students", headers=t_headers)
        check("Class students (array data)", isinstance(r.json()["data"], list) and len(r.json()["data"]) == 1)
        check("Class students pagination", r.json()["total"] == 1)

        # === Teaching: student detail ===
        r = await client.get(f"/api/v1/teaching/classes/{course_id}/students/{user_id}", headers=t_headers)
        check("Student detail", r.json()["data"]["real_name"] == "张三")

        # === Teaching: student learning ===
        r = await client.get(f"/api/v1/teaching/classes/{course_id}/students/{user_id}/learning", headers=t_headers)
        check("Student learning", r.json()["code"] == 200)

        # === Quiz: get questions ===
        r = await client.get(f"/api/v1/quiz/questions?course_id={course_id}", headers=s_headers)
        check("Get questions", r.json()["data"]["total_count"] == 2)
        quiz_id = r.json()["data"]["quiz_id"]

        # === Quiz: submit ===
        r = await client.post("/api/v1/quiz/submit", headers=s_headers, json={
            "quiz_id": quiz_id,
            "answers": [
                {"question_id": "q_sample_1", "answer": "A"},
                {"question_id": "q_sample_2", "answer": ["A", "C"]},
            ],
            "time_spent": 300,
        })
        check("Submit quiz", r.json()["data"]["score"] == 100.0)

        # === Quiz: result ===
        r = await client.get(f"/api/v1/quiz/result?course_id={course_id}", headers=s_headers)
        check("Quiz result", r.json()["data"]["stats"]["total_attempts"] == 1)

        # === Quiz: history (direct array) ===
        r = await client.get(f"/api/v1/quiz/history?course_id={course_id}", headers=s_headers)
        check("Quiz history (array data)", isinstance(r.json()["data"], list))
        check("Quiz history total", r.json()["total"] == 1)

        # === Evaluation ===
        r = await client.get(f"/api/v1/evaluation?course_id={course_id}", headers=s_headers)
        check("Evaluation", r.json()["code"] == 200)

        # === Evaluation refresh (202) ===
        r = await client.post("/api/v1/evaluation/refresh", headers=s_headers, json={"course_id": course_id})
        check("Eval refresh 202", r.status_code == 202)
        task_id = r.json()["data"]["task_id"]

        # === Task status ===
        r = await client.get(f"/api/v1/tasks/{task_id}", headers=s_headers)
        check("Task status", r.json()["data"]["status"] == "completed")

        # === Profile ===
        r = await client.get(f"/api/v1/profile?course_id={course_id}", headers=s_headers)
        check("Profile", r.json()["code"] == 200)

        # === Profile refresh (202) ===
        r = await client.post("/api/v1/profile/refresh", headers=s_headers, json={"course_id": course_id})
        check("Profile refresh 202", r.status_code == 202)

        # === Learning path ===
        r = await client.get(f"/api/v1/learning-path?course_id={course_id}", headers=s_headers)
        check("Learning path", r.json()["code"] == 200)

        # === Learning path refresh (202) ===
        r = await client.post("/api/v1/learning-path/refresh", headers=s_headers, json={"course_id": course_id})
        check("LP refresh 202", r.status_code == 202)

        # === Node resources ===
        r = await client.get("/api/v1/learning-path/nodes/node1/resources", headers=s_headers)
        check("Node resources", r.json()["code"] == 200)

        # === Resources list (direct array) ===
        r = await client.get(f"/api/v1/resources?course_id={course_id}", headers=s_headers)
        check("Resources (array data)", isinstance(r.json()["data"], list))

        # === Resources generate (202) ===
        r = await client.post("/api/v1/resources/generate", headers=t_headers, json={"course_id": course_id})
        check("Resources generate 202", r.status_code == 202)

        # === Tutoring conversations (direct array) ===
        r = await client.get("/api/v1/tutoring/conversations", headers=s_headers)
        check("Conversations (array data)", isinstance(r.json()["data"], list))

        # === Refresh token (only access_token + expires_in) ===
        r = await client.post("/api/v1/auth/refresh", json={"refresh_token": s_refresh})
        d = r.json()["data"]
        check("Refresh token", "access_token" in d and "expires_in" in d)
        check("Refresh no new refresh_token", "refresh_token" not in d)

        # === Send reset code ===
        r = await client.post("/api/v1/auth/send-reset-code", json={"email": "student@test.com"})
        check("Send reset code", r.json()["code"] == 200)

        # === Admin blocked (403) ===
        r = await client.get("/api/v1/admin/users", headers=s_headers)
        check("Admin blocked", r.status_code == 403)

        # === Admin: register admin user ===
        r = await client.post("/api/v1/auth/register", json={
            "registration_code": "TEST-ADMIN-77",
            "email": "admin@test.com",
            "password": "Abc12345",
            "username": "testadmin",
        })
        check("Register admin", r.status_code == 201)

        a_token, _ = await login("admin@test.com", "Abc12345")
        a_headers = {"Authorization": f"Bearer {a_token}"}

        r = await client.get("/api/v1/admin/users", headers=a_headers)
        check("Admin users (array data)", isinstance(r.json()["data"], list))
        check("Admin users count", len(r.json()["data"]) >= 2)

        # === Admin: agent logs (direct array) ===
        r = await client.get("/api/v1/admin/logs/agent", headers=a_headers)
        check("Agent logs (array data)", isinstance(r.json()["data"], list))

        # === Admin: operation logs (direct array) ===
        r = await client.get("/api/v1/admin/logs/operations", headers=a_headers)
        check("Operation logs (array data)", isinstance(r.json()["data"], list))

        # === Webhook: with key ===
        r = await client.post("/api/v1/webhooks/agent", json={
            "task_id": task_id, "task_type": "evaluation", "status": "completed", "result": {},
        }, headers={"X-Internal-Key": "agent-internal-secret-key"})
        check("Webhook with key", r.json()["code"] == 200)

        # === Webhook: without key ===
        r = await client.post("/api/v1/webhooks/agent", json={
            "task_id": task_id, "task_type": "evaluation", "status": "completed",
        })
        check("Webhook no key blocked", r.status_code == 403)

        # === Summary ===
        print()
        print("=" * 55)
        print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed}")
        if failed == 0:
            print("ALL TESTS PASSED SUCCESSFULLY!")
        else:
            print(f"{failed} TESTS FAILED!")
        print("=" * 55)


if __name__ == "__main__":
    asyncio.run(test())
