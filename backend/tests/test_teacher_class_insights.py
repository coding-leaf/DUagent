"""Integration tests for GET /api/v1/teaching/classes/{class_id}/insights.

Covers: 404 course not found, 403 teacher not owner, empty class,
quiz aggregation, weak_points_top, path_node_progress, soft-delete filtering.

Run: python -m pytest tests/test_teacher_class_insights.py -v -s
"""
import asyncio
import os
import pytest
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

database_url = os.environ.get("TEST_DATABASE_URL")
if not database_url or not database_url.startswith("mysql+aiomysql://"):
    raise RuntimeError("TEST_DATABASE_URL must point to an isolated MySQL database")
os.environ["DATABASE_URL"] = database_url

from app.db.session import async_session_factory, engine, init_db
from httpx import AsyncClient, ASGITransport


async def _init_schema():
    await init_db()
    await engine.dispose()


asyncio.run(_init_schema())

from app.main import app
from app.models.user import RegistrationCode
from app.models.course import CourseEnrollment
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.others import LearningPath


async def _captcha_answer(client):
    r = await client.get("/api/v1/auth/captcha")
    d = r.json()["data"]
    nums = re.findall(r"\d+", d["captcha_question"])
    ans = (
        str(int(nums[0]) + int(nums[1]))
        if "+" in d["captcha_question"]
        else str(int(nums[0]) - int(nums[1]))
    )
    return d["captcha_token"], ans


async def _register_and_login(client, code, email, username):
    ct_token, ct_ans = await _captcha_answer(client)
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "registration_code": code,
            "email": email,
            "password": "Abc12345",
            "username": username,
            "captcha_token": ct_token,
            "captcha_code": ct_ans,
        },
    )
    assert r.status_code == 201, f"Register failed: {r.status_code} {r.json()}"
    user_id = r.json()["data"]["user_id"]
    ct_token, ct_ans = await _captcha_answer(client)
    r = await client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "Abc12345",
            "captcha_token": ct_token,
            "captcha_code": ct_ans,
        },
    )
    assert "token" in r.json().get("data", {}), f"Login failed: {r.json()}"
    return {"Authorization": f"Bearer {r.json()['data']['token']}"}, user_id


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.mark.asyncio(loop_scope="module")
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
        # ===== Seed users =====
        codes = [
            RegistrationCode(code=f"stu1_{_uid()}", role="student"),
            RegistrationCode(code=f"stu2_{_uid()}", role="student"),
            RegistrationCode(code=f"tea1_{_uid()}", role="teacher"),
            RegistrationCode(code=f"tea2_{_uid()}", role="teacher"),
        ]
        async with async_session_factory() as db:
            db.add_all(codes)
            await db.commit()

        stu1_headers, stu1_id = await _register_and_login(
            client, codes[0].code, f"s1_{_uid()}@t.com", f"s1_{_uid()}"
        )
        stu2_headers, stu2_id = await _register_and_login(
            client, codes[1].code, f"s2_{_uid()}@t.com", f"s2_{_uid()}"
        )
        tea1_headers, tea1_id = await _register_and_login(
            client, codes[2].code, f"t1_{_uid()}@t.com", f"t1_{_uid()}"
        )
        tea2_headers, tea2_id = await _register_and_login(
            client, codes[3].code, f"t2_{_uid()}@t.com", f"t2_{_uid()}"
        )

        # ===== Create course by tea1, enroll stu1 and stu2 =====
        r = await client.post(
            "/api/v1/courses", json={"name": "Insights Test"}, headers=tea1_headers
        )
        assert r.status_code == 201
        course_id = r.json()["data"]["id"]
        course_code = r.json()["data"].get("course_code", "")

        await client.post(
            "/api/v1/courses/join",
            json={"course_code": course_code},
            headers=stu1_headers,
        )
        await client.post(
            "/api/v1/courses/join",
            json={"course_code": course_code},
            headers=stu2_headers,
        )

        URL = f"/api/v1/teaching/classes/{course_id}/insights"

        # ===== 1. 404 — course does not exist =====
        print("\n-- 1. 404 course not found --")
        r = await client.get(
            "/api/v1/teaching/classes/nonexistent_id/insights",
            headers=tea1_headers,
        )
        chk("404 course not found", r.status_code == 404)

        # ===== 2. 403 — tea2 is teacher but not course owner =====
        print("\n-- 2. 403 teacher not owner --")
        r = await client.get(URL, headers=tea2_headers)
        chk("403 teacher not owner", r.status_code == 403)

        # ===== 3. No quiz data — avg_quiz_score is null =====
        print("\n-- 3. No quiz data --")
        r = await client.get(URL, headers=tea1_headers)
        chk("200 no quiz data", r.status_code == 200)
        data = r.json()["data"]
        chk("avg_quiz_score is null", data["avg_quiz_score"] is None)
        chk("total_quiz_attempts is 0", data["total_quiz_attempts"] == 0)
        chk("weak_points_top is empty", data["weak_points_top"] == [])
        chk(
            "path_node_progress all zeros",
            data["path_node_progress"]["completed"] == 0
            and data["path_node_progress"]["in_progress"] == 0
            and data["path_node_progress"]["recommended"] == 0
            and data["path_node_progress"]["pending"] == 0
            and data["path_node_progress"]["total_nodes"] == 0,
        )

        # ===== 4. Seed quiz data for both students =====
        print("\n-- 4. Quiz aggregation --")
        async with async_session_factory() as db:
            qs1 = QuizSession(
                user_id=stu1_id,
                course_id=course_id,
                chapter="ch1",
                score=60,
                correct_count=3,
                total_count=5,
                time_spent=120,
            )
            qs2 = QuizSession(
                user_id=stu2_id,
                course_id=course_id,
                chapter="ch1",
                score=80,
                correct_count=4,
                total_count=5,
                time_spent=90,
            )
            db.add_all([qs1, qs2])
            await db.flush()

            q1 = QuizQuestion(
                course_id=course_id,
                chapter="ch1",
                knowledge_point="AVL树旋转",
                type="single_choice",
                content="Q1?",
                options=["A", "B", "C", "D"],
                correct_answer="A",
            )
            q2 = QuizQuestion(
                course_id=course_id,
                chapter="ch1",
                knowledge_point="AVL树旋转",
                type="single_choice",
                content="Q2?",
                options=["A", "B", "C", "D"],
                correct_answer="A",
            )
            q3 = QuizQuestion(
                course_id=course_id,
                chapter="ch1",
                knowledge_point="散列冲突",
                type="single_choice",
                content="Q3?",
                options=["A", "B", "C", "D"],
                correct_answer="A",
            )
            q4 = QuizQuestion(
                course_id=course_id,
                chapter="ch1",
                knowledge_point="",
                type="single_choice",
                content="Empty KP",
                options=["A", "B", "C", "D"],
                correct_answer="A",
            )
            db.add_all([q1, q2, q3, q4])
            await db.flush()

            answers = [
                # stu1: q1 wrong, q2 wrong, q3 wrong, q4 wrong (empty KP)
                QuizAnswer(quiz_id=qs1.id, question_id=q1.id, user_answer="B", is_correct=False, correct_answer="A"),
                QuizAnswer(quiz_id=qs1.id, question_id=q2.id, user_answer="B", is_correct=False, correct_answer="A"),
                QuizAnswer(quiz_id=qs1.id, question_id=q3.id, user_answer="B", is_correct=False, correct_answer="A"),
                QuizAnswer(quiz_id=qs1.id, question_id=q4.id, user_answer="B", is_correct=False, correct_answer="A"),
                # stu2: q1 correct, q2 wrong, q3 correct
                QuizAnswer(quiz_id=qs2.id, question_id=q1.id, user_answer="A", is_correct=True, correct_answer="A"),
                QuizAnswer(quiz_id=qs2.id, question_id=q2.id, user_answer="B", is_correct=False, correct_answer="A"),
                QuizAnswer(quiz_id=qs2.id, question_id=q3.id, user_answer="A", is_correct=True, correct_answer="A"),
            ]
            db.add_all(answers)
            await db.commit()

        r = await client.get(URL, headers=tea1_headers)
        chk("200 with quiz data", r.status_code == 200)
        data = r.json()["data"]

        chk("avg_quiz_score is 70.0", data["avg_quiz_score"] == 70.0)
        chk("total_quiz_attempts is 2", data["total_quiz_attempts"] == 2)

        # ===== 5. weak_points_top =====
        print("\n-- 5. weak_points_top --")
        wp = data["weak_points_top"]
        chk("weak_points_top non-empty", len(wp) > 0)
        chk("weak_points_top max 5", len(wp) <= 5)

        kp_names = [w["knowledge_point"] for w in wp]
        chk("empty KP filtered", "" not in kp_names)

        avl = [w for w in wp if w["knowledge_point"] == "AVL树旋转"]
        chk("AVL present", len(avl) == 1)
        if avl:
            # AVL: stu1 q1 wrong + q2 wrong, stu2 q1 correct + q2 wrong => error=3, total=4
            chk("AVL error_count=3", avl[0]["error_count"] == 3)
            chk("AVL total_attempts=4", avl[0]["total_attempts"] == 4)
            chk("AVL error_rate=0.75", avl[0]["error_rate"] == 0.75)

        hash_wp = [w for w in wp if w["knowledge_point"] == "散列冲突"]
        chk("散列冲突 present", len(hash_wp) == 1)
        if hash_wp:
            # 散列冲突: stu1 wrong, stu2 correct => error=1, total=2
            chk("散列 error_count=1", hash_wp[0]["error_count"] == 1)
            chk("散列 total_attempts=2", hash_wp[0]["total_attempts"] == 2)
            chk("散列 error_rate=0.5", hash_wp[0]["error_rate"] == 0.5)

        # Verify sorted by error_rate DESC
        if len(wp) >= 2:
            chk(
                "sorted by error_rate DESC",
                wp[0]["error_rate"] >= wp[1]["error_rate"],
            )

        # ===== 6. path_node_progress =====
        print("\n-- 6. path_node_progress --")
        async with async_session_factory() as db:
            lp1 = LearningPath(
                user_id=stu1_id,
                course_id=course_id,
                nodes=[
                    {"id": "n1", "status": "completed"},
                    {"id": "n2", "status": "completed"},
                    {"id": "n3", "status": "in_progress"},
                    {"id": "n4", "status": "pending"},
                    {"id": "n5", "status": "unknown_status"},
                ],
            )
            lp2 = LearningPath(
                user_id=stu2_id,
                course_id=course_id,
                nodes=[
                    {"id": "n1", "status": "completed"},
                    {"id": "n2", "status": "recommended"},
                    {"id": "n3", "status": "recommended"},
                    {"id": "n4", "status": "pending"},
                ],
            )
            db.add_all([lp1, lp2])
            await db.commit()

        r = await client.get(URL, headers=tea1_headers)
        chk("200 with path data", r.status_code == 200)
        pnp = r.json()["data"]["path_node_progress"]
        # stu1: 2 completed, 1 in_progress, 0 recommended, 1 pending (unknown ignored)
        # stu2: 1 completed, 0 in_progress, 2 recommended, 1 pending
        # Total: 3 completed, 1 in_progress, 2 recommended, 2 pending
        chk("completed=3", pnp["completed"] == 3)
        chk("in_progress=1", pnp["in_progress"] == 1)
        chk("recommended=2", pnp["recommended"] == 2)
        chk("pending=2", pnp["pending"] == 2)
        chk("total_nodes=8", pnp["total_nodes"] == 8)

        # ===== 7. Soft-deleted enrollment excluded =====
        print("\n-- 7. Soft-deleted enrollment --")
        async with async_session_factory() as db:
            from sqlalchemy import select, update

            await db.execute(
                update(CourseEnrollment)
                .where(
                    CourseEnrollment.student_id == stu2_id,
                    CourseEnrollment.course_id == course_id,
                )
                .values(is_deleted=True)
            )
            await db.commit()

        r = await client.get(URL, headers=tea1_headers)
        chk("200 after soft-delete enrollment", r.status_code == 200)
        data_after = r.json()["data"]
        # Only stu1 remains: score=60, attempts=1
        chk("avg_quiz_score=60 after unenroll", data_after["avg_quiz_score"] == 60.0)
        chk("total_quiz_attempts=1 after unenroll", data_after["total_quiz_attempts"] == 1)
        # path: only stu1: 2 completed, 1 in_progress, 0 recommended, 1 pending
        pnp2 = data_after["path_node_progress"]
        chk("completed=2 after unenroll", pnp2["completed"] == 2)
        chk("recommended=0 after unenroll", pnp2["recommended"] == 0)
        chk("total_nodes=4 after unenroll", pnp2["total_nodes"] == 4)

        # ===== 8. Empty class (unenroll stu1 too) =====
        print("\n-- 8. Empty class --")
        async with async_session_factory() as db:
            await db.execute(
                update(CourseEnrollment)
                .where(
                    CourseEnrollment.student_id == stu1_id,
                    CourseEnrollment.course_id == course_id,
                )
                .values(is_deleted=True)
            )
            await db.commit()

        r = await client.get(URL, headers=tea1_headers)
        chk("200 empty class", r.status_code == 200)
        empty = r.json()["data"]
        chk("empty avg_quiz_score null", empty["avg_quiz_score"] is None)
        chk("empty total_quiz_attempts 0", empty["total_quiz_attempts"] == 0)
        chk("empty weak_points_top []", empty["weak_points_top"] == [])
        chk("empty path total_nodes 0", empty["path_node_progress"]["total_nodes"] == 0)

    print(f"\n{'='*50}")
    print(f"  Total: {ok} OK, {fail} FAIL")
    assert fail == 0, f"{fail} check(s) FAIL"
    return True


if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
