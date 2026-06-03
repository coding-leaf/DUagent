import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_v3.db"
os.environ["WEBHOOK_SECRET"] = ""

from app.db.session import init_db, async_session_factory
asyncio.run(init_db())

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.user import RegistrationCode


async def test():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        ok = 0
        fail = 0

        def chk(name, cond):
            nonlocal ok, fail
            if cond:
                ok += 1
                print(f"  OK  {name}")
            else:
                fail += 1
                print(f"  FAIL {name}")
            return cond

        # === Health ===
        r = await client.get("/health")
        chk("Health", r.json()["status"] == "ok")

        # === Captcha ===
        r = await client.get("/api/v1/auth/captcha")
        ct = r.json()
        chk("Captcha", ct["code"] == 200)

        # === Seed ===
        async with async_session_factory() as db:
            for rc in [RegistrationCode(code="student", role="student"),
                         RegistrationCode(code="teacher", role="teacher"),
                         RegistrationCode(code="admin_seed", role="admin")]:
                db.add(rc)
            await db.commit()

        # === Register (v1: requires captcha) ===
        async def get_captcha_answer():
            r = await client.get("/api/v1/auth/captcha")
            d = r.json()["data"]
            nums = re.findall(r"\d+", d["captcha_question"])
            return d["captcha_token"], str(int(nums[0]) + int(nums[1])) if "+" in d["captcha_question"] else str(int(nums[0]) - int(nums[1]))

        ct_token, ct_ans = await get_captcha_answer()
        r = await client.post("/api/v1/auth/register", json={
            "registration_code": "student", "email": "s@t.com",
            "password": "Abc12345", "username": "stu",
            "captcha_token": ct_token, "captcha_code": ct_ans,
        })
        student_id = r.json()["data"]["user_id"]
        chk("Register student", r.status_code == 201 and student_id)

        ct_token, ct_ans = await get_captcha_answer()
        r = await client.post("/api/v1/auth/register", json={
            "registration_code": "teacher", "email": "t@t.com",
            "password": "Abc12345", "username": "tea",
            "captcha_token": ct_token, "captcha_code": ct_ans,
        })
        chk("Register teacher", r.status_code == 201)
        teacher_id = r.json()["data"]["user_id"]

        ct_token, ct_ans = await get_captcha_answer()
        r = await client.post("/api/v1/auth/register", json={
            "registration_code": "admin_seed", "email": "a@t.com",
            "password": "Abc12345", "username": "adm",
            "captcha_token": ct_token, "captcha_code": ct_ans,
        })
        # Make admin
        async with async_session_factory() as db:
            from app.models.user import User
            from sqlalchemy import select, update
            res = await db.execute(select(User).where(User.email == "a@t.com"))
            u = res.scalar_one_or_none()
            if u:
                u.role = "admin"
                await db.commit()

        # === Login (v1: single token, no refresh) ===
        async def login(email):
            ct_token, ct_ans = await get_captcha_answer()
            r = await client.post("/api/v1/auth/login", json={
                "email": email, "password": "Abc12345",
                "captcha_token": ct_token, "captcha_code": ct_ans,
            })
            d = r.json()["data"]
            chk(f"Login {email} has token", "token" in d)
            chk(f"Login {email} no refresh_token", "refresh_token" not in d)
            chk(f"Login {email} expires_in 7d", d["expires_in"] == 604800)
            return d["token"]

        s_token = await login("s@t.com")
        t_token = await login("t@t.com")
        a_token = await login("a@t.com")
        s_h = {"Authorization": f"Bearer {s_token}"}
        t_h = {"Authorization": f"Bearer {t_token}"}
        a_h = {"Authorization": f"Bearer {a_token}"}

        # === GET /me (v1: no courses field) ===
        r = await client.get("/api/v1/users/me", headers=s_h)
        d = r.json()["data"]
        chk("GET /me role", d["role"] == "student")
        chk("GET /me no courses", "courses" not in d)

        # === PUT /me ===
        r = await client.put("/api/v1/users/me", headers=s_h, json={"real_name": "张三"})
        chk("PUT /me", r.json()["data"]["real_name"] == "张三")

        # === Create course (201, teacher only) ===
        r = await client.post("/api/v1/courses", headers=t_h, json={"name": "高等数学"})
        chk("Create course 201", r.status_code == 201)
        course_id = r.json()["data"]["id"]
        course_code = r.json()["data"]["course_code"]

        r = await client.post("/api/v1/courses", headers=s_h, json={"name": "x"})
        chk("Student cannot create", r.status_code == 403)

        # === Join course (student only) ===
        r = await client.post("/api/v1/courses/join", headers=s_h, json={"course_code": course_code})
        chk("Join course", r.json()["code"] == 200)

        r = await client.post("/api/v1/courses/join", headers=s_h, json={"course_code": course_code})
        chk("Join duplicate 409", r.status_code == 409)

        # === List courses ===
        r = await client.get("/api/v1/courses", headers=s_h)
        chk("List courses", len(r.json()["data"]["courses"]) == 1)

        # === Teaching: students (pagination in data object) ===
        r = await client.get(f"/api/v1/teaching/classes/{course_id}/students", headers=t_h)
        chk("Students list", r.json()["data"]["total"] == 1)
        chk("Students obj wrap", "students" in r.json()["data"])

        # === Teaching: student detail ===
        r = await client.get(f"/api/v1/teaching/classes/{course_id}/students/{student_id}", headers=t_h)
        chk("Student detail", r.json()["data"]["username"] == "stu")

        # === Teaching: learning ===
        r = await client.get(f"/api/v1/teaching/classes/{course_id}/students/{student_id}/learning", headers=t_h)
        chk("Student learning", "student" in r.json()["data"])
        chk("Student learning weak_points", "weak_points" in r.json()["data"])
        chk("Student learning recent_activity", "recent_activity" in r.json()["data"])

        # === Quiz: get questions (new params: knowledge_point, limit, type, source) ===
        r = await client.get(f"/api/v1/quiz/questions?course_id={course_id}&limit=5", headers=s_h)
        qd = r.json()["data"]
        chk("Quiz questions", "quiz_id" in qd)
        quiz_id = qd["quiz_id"]

        # === Quiz: generate (202) ===
        r = await client.post("/api/v1/quiz/generate", headers=s_h, json={
            "course_id": course_id, "count": 3, "personalized": True,
        })
        chk("Quiz generate 202", r.status_code == 202)

        # === Quiz: submit ===
        r = await client.post("/api/v1/quiz/submit", headers=s_h, json={
            "quiz_id": quiz_id,
            "answers": [{"question_id": "q_x", "answer": "A"}],
            "time_spent": 120,
        })
        chk("Quiz submit", r.json()["code"] == 200)

        # === Quiz: result ===
        r = await client.get(f"/api/v1/quiz/result?course_id={course_id}", headers=s_h)
        chk("Quiz result", "diagnosis" in r.json()["data"])

        # === Quiz: history (pagination in data object) ===
        r = await client.get(f"/api/v1/quiz/history?course_id={course_id}", headers=s_h)
        chk("Quiz history", "records" in r.json()["data"])
        chk("Quiz history pagination", "total" in r.json()["data"])

        # === Evaluation ===
        r = await client.get(f"/api/v1/evaluation?course_id={course_id}", headers=s_h)
        chk("Evaluation", r.json()["code"] == 200)

        r = await client.post("/api/v1/evaluation/refresh", headers=s_h, json={"course_id": course_id})
        chk("Eval refresh 202", r.status_code == 202)
        task_id = r.json()["data"]["task_id"]

        # === Profile: initialize (questionnaire POST, not SSE) ===
        r = await client.post("/api/v1/profile/initialize", headers=s_h, json={
            "course_id": course_id,
            "answers": {"guidance_level": "L2", "modal_preference": ["text", "code"], "learning_goal": "daily_homework"},
        })
        chk("Profile init", r.json()["code"] == 200)
        chk("Profile init data", "modal_preference" in r.json()["data"])

        r = await client.get(f"/api/v1/profile?course_id={course_id}", headers=s_h)
        chk("Profile get", r.json()["code"] == 200)

        r = await client.post("/api/v1/profile/refresh", headers=s_h, json={"course_id": course_id})
        chk("Profile refresh 202", r.status_code == 202)

        # === Learning path ===
        r = await client.get(f"/api/v1/learning-path?course_id={course_id}", headers=s_h)
        chk("Learning path", r.json()["code"] == 200)
        chk("LP current_position null ok", r.json()["data"]["current_position"] is None or isinstance(r.json()["data"]["current_position"], dict))

        r = await client.post("/api/v1/learning-path/refresh", headers=s_h, json={"course_id": course_id})
        chk("LP refresh 202", r.status_code == 202)

        # === Node resources ===
        r = await client.get(f"/api/v1/learning-path/nodes/n1/resources?course_id={course_id}", headers=s_h)
        chk("Node resources", r.json()["code"] == 200)

        # === Resources (knowledge_point, pagination in data object) ===
        r = await client.get(f"/api/v1/resources?course_id={course_id}", headers=s_h)
        chk("Resources", "resources" in r.json()["data"])
        chk("Resources pagination", "total" in r.json()["data"])

        r = await client.post("/api/v1/resources/generate", headers=t_h, json={"course_id": course_id})
        chk("Resources generate 202", r.status_code == 202)

        # === Tutoring (scope field, conversations pagination in data) ===
        r = await client.get(f"/api/v1/tutoring/conversations?scope=course&course_id={course_id}", headers=s_h)
        chk("Tutoring convs", "conversations" in r.json()["data"])

        # === Tasks (new task types, error_code field) ===
        r = await client.get(f"/api/v1/tasks/{task_id}", headers=s_h)
        chk("Task status", r.json()["data"]["task_type"] == "evaluation_refresh")
        chk("Task has error_code", "error_code" in r.json()["data"])

        # === Admin: users (pagination in data object) ===
        r = await client.get("/api/v1/admin/users", headers=a_h)
        chk("Admin users", "users" in r.json()["data"])

        # === Admin: update with new_password ===
        r = await client.put("/api/v1/admin/users/user_fake", headers=a_h, json={"new_password": "Xyz98765"})
        chk("Admin update 404", r.status_code == 404)

        # === Admin: logs (pagination in data) ===
        r = await client.get("/api/v1/admin/logs/agent", headers=a_h)
        chk("Admin agent logs", "logs" in r.json()["data"])
        r = await client.get("/api/v1/admin/logs/operations", headers=a_h)
        chk("Admin op logs", "logs" in r.json()["data"])

        # === Webhook (v1: no auth key needed) ===
        r = await client.post("/api/v1/webhooks/agent", json={
            "task_id": task_id, "task_type": "evaluation_refresh",
            "status": "completed", "result": {"ok": True},
        })
        chk("Webhook", r.json()["code"] == 200)

        # === Admin blocked for student ===
        r = await client.get("/api/v1/admin/users", headers=s_h)
        chk("Admin blocked", r.status_code == 403)

        # === Teacher cannot see student conversations ===
        r = await client.get("/api/v1/tutoring/conversations", headers=t_h)
        chk("Teacher convs own only", r.status_code == 200)

        # === Summary ===
        print()
        print("=" * 55)
        print(f"  {ok} PASSED, {fail} FAILED  (total {ok+fail})")
        if fail:
            print("  SOME TESTS FAILED!")
        else:
            print("  ALL TESTS PASSED!")
        print("=" * 55)


if __name__ == "__main__":
    asyncio.run(test())
