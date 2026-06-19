"""Integration tests for GET /teaching/classes/{class_id}/students/{student_id}/learning.

Covers: 403 teacher not owning course, weak_points aggregation with HAVING filter,
empty weak_points when all correct, recent_activity max 5 items, created_at DESC ordering.

Requires MySQL or SQLite.

Run: python -m pytest tests/test_teacher_student_learning.py -v -s
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
from app.models.others import Evaluation, UserProfile
from app.models.user import RegistrationCode
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession


async def _captcha_answer(client):
    r = await client.get("/api/v1/auth/captcha")
    d = r.json()["data"]
    nums = re.findall(r"\d+", d["captcha_question"])
    ans = str(int(nums[0]) + int(nums[1])) if "+" in d["captcha_question"] else str(int(nums[0]) - int(nums[1]))
    return d["captcha_token"], ans


async def _register_and_login(client, code, email, username):
    ct_token, ct_ans = await _captcha_answer(client)
    r = await client.post("/api/v1/auth/register", json={
        "registration_code": code, "email": email, "password": "Abc12345",
        "username": username, "captcha_token": ct_token, "captcha_code": ct_ans,
    })
    assert r.status_code == 201, f"Register failed: {r.status_code} {r.json()}"
    user_id = r.json()["data"]["user_id"]
    ct_token, ct_ans = await _captcha_answer(client)
    r = await client.post("/api/v1/auth/login", json={
        "email": email, "password": "Abc12345",
        "captcha_token": ct_token, "captcha_code": ct_ans,
    })
    assert "token" in r.json().get("data", {}), f"Login failed: {r.json()}"
    return {"Authorization": f"Bearer {r.json()['data']['token']}"}, user_id


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
            RegistrationCode(code=f"stu_{uuid.uuid4().hex[:8]}", role="student"),
            RegistrationCode(code=f"tea1_{uuid.uuid4().hex[:8]}", role="teacher"),
            RegistrationCode(code=f"tea2_{uuid.uuid4().hex[:8]}", role="teacher"),
        ]
        async with async_session_factory() as db:
            db.add_all(codes)
            await db.commit()
            student_code = codes[0].code
            tea1_code = codes[1].code
            tea2_code = codes[2].code

        stu_headers, stu_id = await _register_and_login(
            client, student_code, f"stu_{uuid.uuid4().hex[:8]}@test.com", f"stu_{uuid.uuid4().hex[:8]}")
        tea1_headers, tea1_id = await _register_and_login(
            client, tea1_code, f"tea1_{uuid.uuid4().hex[:8]}@test.com", f"tea1_{uuid.uuid4().hex[:8]}")
        tea2_headers, tea2_id = await _register_and_login(
            client, tea2_code, f"tea2_{uuid.uuid4().hex[:8]}@test.com", f"tea2_{uuid.uuid4().hex[:8]}")

        # ===== Create course by tea1 =====
        r = await client.post("/api/v1/courses", json={"name": "Tchr Test"}, headers=tea1_headers)
        assert r.status_code == 201, f"Create course failed: {r.status_code} {r.json()}"
        course_data = r.json()["data"]
        course_id = course_data["id"]
        course_code = course_data.get("course_code", "")

        join_r = await client.post("/api/v1/courses/join", json={"course_code": course_code}, headers=stu_headers)
        assert join_r.status_code == 200, f"Join failed: {join_r.status_code} {join_r.json()}"

        # ===== Seed quiz data (for weak_points verification) =====
        async with async_session_factory() as db:
            qs = QuizSession(user_id=stu_id, course_id=course_id, chapter="ch1",
                             score=50, correct_count=1, total_count=2, time_spent=60)
            db.add(Evaluation(
                user_id=stu_id,
                course_id=course_id,
                mastery_table={"rows": [
                    {"average_score": 60},
                    {"average_score": "80"},
                ]},
                summary_text="真实评估摘要",
            ))
            db.add(qs)
            await db.flush()

            q1 = QuizQuestion(course_id=course_id, chapter="ch1", knowledge_point="AVL树旋转",
                              type="single_choice", content="Q1?", options=["A","B","C","D"], correct_answer="A")
            q2 = QuizQuestion(course_id=course_id, chapter="ch1", knowledge_point="AVL树旋转",
                              type="single_choice", content="Q2?", options=["A","B","C","D"], correct_answer="A")
            q3 = QuizQuestion(course_id=course_id, chapter="ch1", knowledge_point="散列冲突",
                              type="single_choice", content="Q3?", options=["A","B","C","D"], correct_answer="A")
            q4 = QuizQuestion(course_id=course_id, chapter="ch1", knowledge_point="",
                              type="single_choice", content="Empty KP", options=["A","B","C","D"], correct_answer="A")
            db.add_all([q1, q2, q3, q4])
            await db.flush()

            answers = [
                QuizAnswer(quiz_id=qs.id, question_id=q1.id, user_answer="B", is_correct=False, correct_answer="A"),
                QuizAnswer(quiz_id=qs.id, question_id=q2.id, user_answer="A", is_correct=True, correct_answer="A"),
                QuizAnswer(quiz_id=qs.id, question_id=q3.id, user_answer="B", is_correct=False, correct_answer="A"),
                QuizAnswer(quiz_id=qs.id, question_id=q4.id, user_answer="B", is_correct=False, correct_answer="A"),
            ]
            db.add_all(answers)
            await db.commit()

        # ===== 1. 403 — tea2 is teacher but not course owner =====
        print("\n-- 1. 403 teacher not course owner --")
        r = await client.get(
            f"/api/v1/teaching/classes/{course_id}/students/{stu_id}/learning",
            headers=tea2_headers)
        chk("403 teacher not owner", r.status_code == 403)

        # ===== 2. 200 — weak_points aggregation (tea1 can access) =====
        print("\n-- 2. weak_points aggregation --")
        r = await client.get(
            f"/api/v1/teaching/classes/{course_id}/students/{stu_id}/learning",
            headers=tea1_headers)
        chk("200 teacher access", r.status_code == 200)
        data = r.json()["data"]

        ev_sum = data.get("evaluation_summary")
        if ev_sum is not None:
            chk("evaluation_summary has summary_text key", "summary_text" in ev_sum)
            chk("evaluation_summary uses real overall_score", ev_sum.get("overall_score") == 70.0)

        pf_sum = data.get("profile_summary")
        if pf_sum is not None:
            chk("profile_summary has knowledge_coordinates key", "knowledge_coordinates" in pf_sum)
            kc = pf_sum.get("knowledge_coordinates") or []
            chk("knowledge_coordinates is list", isinstance(kc, list))

        qs_data = data.get("quiz_stats") or {}
        chk("quiz_stats has mastery_breakdown key", "mastery_breakdown" in qs_data)
        mb = qs_data.get("mastery_breakdown") or []
        chk("mastery_breakdown is list", isinstance(mb, list))
        avl_mb = [m for m in mb if m.get("knowledge_point") == "AVL树旋转"]
        chk("AVL树旋转 has mastery_breakdown entry", len(avl_mb) > 0)
        if len(avl_mb) > 0:
            chk("mastery_breakdown has accuracy", "accuracy" in avl_mb[0])
            chk("AVL accuracy = 50.0", avl_mb[0]["accuracy"] == 50.0)
        hash_mb = [m for m in mb if m.get("knowledge_point") == "散列冲突"]
        chk("散列冲突 has mastery_breakdown entry", len(hash_mb) > 0)
        if len(hash_mb) > 0:
            chk("散列冲突 accuracy = 0.0", hash_mb[0]["accuracy"] == 0.0)

        wp = data.get("weak_points", [])
        chk("weak_points non-empty", len(wp) > 0)
        if len(wp) > 0:
            chk("weak_points has knowledge_point", "knowledge_point" in wp[0])
            chk("weak_points has error_count", "error_count" in wp[0])
            chk("weak_points has total_attempts", "total_attempts" in wp[0])
            chk("weak_points has error_rate", "error_rate" in wp[0])
            avl = [w for w in wp if w["knowledge_point"] == "AVL树旋转"]
            chk("AVL树旋转 present", len(avl) > 0)
            if len(avl) > 0:
                chk("AVL error_count = 1", avl[0]["error_count"] == 1)
                chk("AVL total_attempts = 2", avl[0]["total_attempts"] == 2)
                chk("AVL error_rate = 0.5", avl[0]["error_rate"] == 0.5)
            hash_wp = [w for w in wp if w["knowledge_point"] == "散列冲突"]
            chk("散列冲突 present", len(hash_wp) > 0)
            empty_kp = [w for w in wp if w["knowledge_point"] == ""]
            chk("empty KP filtered", len(empty_kp) == 0)

        # ===== 3. recent_activity =====
        print("\n-- 3. recent_activity --")
        ra = data.get("recent_activity", [])
        chk("recent_activity non-empty", len(ra) > 0)
        if len(ra) > 0:
            chk("ra has quiz_id", "quiz_id" in ra[0])
            chk("ra has chapter", "chapter" in ra[0])
            chk("ra has score", "score" in ra[0])
            chk("ra has correct_count", "correct_count" in ra[0])
            chk("ra has total_count", "total_count" in ra[0])
            chk("ra has time_spent", "time_spent" in ra[0])
            chk("ra has created_at", "created_at" in ra[0])

        # ===== 4. empty weak_points when all correct =====
        print("\n-- 4. all-correct -> empty weak_points --")
        stu2_code = f"stu_{uuid.uuid4().hex[:8]}"
        async with async_session_factory() as db:
            db.add(RegistrationCode(code=stu2_code, role="student"))
            await db.commit()
        stu2_headers, stu2_id = await _register_and_login(
            client, stu2_code, f"stu2_{uuid.uuid4().hex[:8]}@test.com", f"stu2_{uuid.uuid4().hex[:8]}")
        await client.post("/api/v1/courses/join", json={"course_code": course_code}, headers=stu2_headers)

        async with async_session_factory() as db:
            qs3 = QuizSession(user_id=stu2_id, course_id=course_id, chapter="ch1",
                              score=100, correct_count=1, total_count=1, time_spent=30)
            db.add(qs3)
            await db.flush()
            q_all = QuizQuestion(course_id=course_id, chapter="ch1", knowledge_point="正确知识点",
                                 type="single_choice", content="Q?", options=["A","B"], correct_answer="A")
            db.add(q_all)
            await db.flush()
            db.add(QuizAnswer(quiz_id=qs3.id, question_id=q_all.id, user_answer="A",
                              is_correct=True, correct_answer="A"))
            await db.commit()

        r = await client.get(
            f"/api/v1/teaching/classes/{course_id}/students/{stu2_id}/learning",
            headers=tea1_headers)
        chk("all-correct -> 200", r.status_code == 200)
        st2_data = r.json()["data"]
        st2_wp = st2_data.get("weak_points", [])
        chk("all-correct -> weak_points empty", st2_wp == [])

        # ===== 4a. profile_summary keeps modal_preference when knowledge_coordinates empty =====
        print("\n-- 4a. profile_summary with empty knowledge_coordinates --")
        async with async_session_factory() as db:
            db.add(UserProfile(
                user_id=stu2_id,
                course_id=course_id,
                modal_preference={"text_analysis": 80, "code_practice": 60},
                knowledge_coordinates=[],
            ))
            await db.commit()

        r = await client.get(
            f"/api/v1/teaching/classes/{course_id}/students/{stu2_id}/learning",
            headers=tea1_headers)
        chk("empty knowledge_coordinates profile -> 200", r.status_code == 200)
        profile_summary = r.json()["data"].get("profile_summary")
        chk("profile_summary present when knowledge_coordinates empty", profile_summary is not None)
        if profile_summary is not None:
            chk("modal_preference preserved", profile_summary.get("modal_preference") == ["text_analysis", "code_practice"])
            chk("knowledge_coordinates empty list", profile_summary.get("knowledge_coordinates") == [])

        # ===== 4b. non-enrolled student -> 404 =====
        print("\n-- 4b. non-enrolled student -> 404 --")
        stu3_code = f"stu_{uuid.uuid4().hex[:8]}"
        async with async_session_factory() as db:
            db.add(RegistrationCode(code=stu3_code, role="student"))
            await db.commit()
        stu3_headers, stu3_id = await _register_and_login(
            client, stu3_code, f"stu3_{uuid.uuid4().hex[:8]}@test.com", f"stu3_{uuid.uuid4().hex[:8]}")
        # stu3 is registered but NOT enrolled
        r = await client.get(
            f"/api/v1/teaching/classes/{course_id}/students/{stu3_id}/learning",
            headers=tea1_headers)
        chk("non-enrolled student -> 404", r.status_code == 404)

        # ===== 5. recent_activity max 5 + created_at DESC ordering =====
        print("\n-- 5. recent_activity max 5 --")
        async with async_session_factory() as db:
            for i in range(7):
                qs_n = QuizSession(user_id=stu_id, course_id=course_id, chapter=f"ch{i}",
                                   score=80, correct_count=3, total_count=4, time_spent=60)
                db.add(qs_n)
            await db.commit()

        r = await client.get(
            f"/api/v1/teaching/classes/{course_id}/students/{stu_id}/learning",
            headers=tea1_headers)
        chk("more sessions -> 200", r.status_code == 200)
        ra_all = r.json()["data"].get("recent_activity", [])
        chk("recent_activity max 5", len(ra_all) == 5)
        # Verify create_time DESC ordering
        if len(ra_all) >= 2:
            dates = [ra["created_at"] for ra in ra_all]
            ordered = all(dates[i] >= dates[i + 1] for i in range(len(dates) - 1))
            chk("recent_activity ordered by created_at DESC", ordered)

    print(f"\n{'='*50}")
    print(f"  Total: {ok} OK, {fail} FAIL")
    assert fail == 0, f"{fail} check(s) FAIL"
    return True


if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
