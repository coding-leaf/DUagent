"""MySQL integration test for quiz submit + result endpoints.

Covers: submit scoring, background diagnosis write, Agent-failure resilience,
QuizAnswer DB persistence, multi-choice scoring, edge cases (empty answers,
invalid quiz_id, illegal question_id), stats computation, score_trend ordering,
empty-session filtering, and current data-driven diagnosis shape while final
diagnosis semantics remain pending.

Agent calls mocked. Requires MySQL.

Run: python test_quiz_async.py
"""
import asyncio
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

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
from app.models.user import RegistrationCode
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.course import Course, CourseEnrollment
from sqlalchemy import select, func


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


async def _poll_diagnosis(db_session, quiz_id, timeout=10, interval=0.3):
    """Poll QuizSession until diagnosis_json is populated or timeout.

    Returns the diagnosis_json dict on success, None on timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = await db_session.execute(
            select(QuizSession).where(QuizSession.id == quiz_id)
        )
        session = result.scalar_one_or_none()
        if session and session.diagnosis_json:
            return session.diagnosis_json
        await asyncio.sleep(interval)
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
        return cond

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # =============================================
        # Seed: users, course, questions
        # =============================================
        uname = f"stu_{uuid.uuid4().hex[:8]}"
        email = f"{uname}@test.com"
        codes = [
            RegistrationCode(code=f"stu_{uuid.uuid4().hex[:8]}", role="student"),
            RegistrationCode(code=f"tea_{uuid.uuid4().hex[:8]}", role="teacher"),
        ]
        async with async_session_factory() as db:
            db.add_all(codes)
            await db.commit()
            student_code = codes[0].code
            teacher_code = codes[1].code

        stu_headers, stu_id = await _register_and_login(client, student_code, email, uname)
        tea_headers, tea_id = await _register_and_login(
            client, teacher_code, f"tea_{uuid.uuid4().hex[:8]}@test.com",
            f"tea_{uuid.uuid4().hex[:8]}")

        r = await client.post("/api/v1/courses", json={"name": "Quiz Course"}, headers=tea_headers)
        assert r.status_code == 201
        course_id = r.json()["data"]["id"]

        # Seed 3 single_choice + 1 multi_choice questions
        q_ids = []
        mc_q_id = None
        async with async_session_factory() as db:
            for i in range(3):
                q = QuizQuestion(
                    course_id=course_id,
                    chapter="ch1",
                    knowledge_point=f"kp{i}",
                    type="single_choice",
                    content=f"Question {i}?",
                    options=["A", "B", "C", "D"],
                    correct_answer="A",
                    explanation=f"Explanation {i}",
                )
                db.add(q)
                await db.flush()
                q_ids.append(q.id)
            mc_q = QuizQuestion(
                course_id=course_id,
                chapter="ch1",
                knowledge_point="kp_multi",
                type="multi_choice",
                content="Multi-choice question?",
                options=["A", "B", "C", "D"],
                correct_answer="['A','C']",
                explanation="Multi explanation",
            )
            db.add(mc_q)
            await db.flush()
            mc_q_id = mc_q.id
            await db.commit()

        await client.post("/api/v1/courses/join", json={"course_id": course_id},
                          headers=stu_headers)

        r = await client.get(f"/api/v1/quiz/questions?course_id={course_id}&limit=1", headers=stu_headers)
        chk("questions -> 200", r.status_code == 200)
        fetched_questions = r.json()["data"]["questions"]
        assert fetched_questions
        assert fetched_questions[0]["chapter"] == "ch1"
        assert fetched_questions[0]["knowledge_point"].startswith("kp")
        assert "difficulty" in fetched_questions[0]

        # Create first QuizSession
        async with async_session_factory() as db:
            quiz = QuizSession(user_id=stu_id, course_id=course_id, chapter="ch1")
            db.add(quiz)
            await db.commit()
            quiz_id = quiz.id

        # =============================================
        # 1. submit returns scoring results
        # =============================================
        print("\n-- 1. submit scoring --")
        with patch("app.api.v1.quiz.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = {"diagnosis": {"summary": "good", "weak_points": [], "suggestions": []}}
            r = await client.post("/api/v1/quiz/submit", json={
                "quiz_id": quiz_id,
                "answers": [
                    {"question_id": q_ids[0], "answer": "A"},  # correct
                    {"question_id": q_ids[1], "answer": "B"},  # wrong
                    {"question_id": q_ids[2], "answer": "A"},  # correct
                ],
                "time_spent": 120,
            }, headers=stu_headers)
            chk("submit -> 200", r.status_code == 200)
            data = r.json()["data"]
            chk("submit -> score present", "score" in data)
            chk("submit -> correct_count", data.get("correct_count") == 2)
            chk("submit -> total_count", data.get("total_count") == 3)

            await asyncio.sleep(0.5)

        # =============================================
        # 2. background diagnosis_json written
        # =============================================
        print("\n-- 2. background diagnosis write --")
        async with async_session_factory() as poll_db:
            diag = await _poll_diagnosis(poll_db, quiz_id, timeout=10)
            chk("background -> diagnosis_json written",
                diag is not None and isinstance(diag, dict))
            chk("background -> diagnosis has summary",
                diag is not None and "summary" in diag)

        # =============================================
        # 3. Agent failure -> submit still returns 200 scoring
        # =============================================
        print("\n-- 3. Agent failure resilience --")
        from app.services.agent_client import AgentServiceError

        async with async_session_factory() as db:
            quiz2 = QuizSession(user_id=stu_id, course_id=course_id, chapter="ch1")
            db.add(quiz2)
            await db.commit()
            quiz2_id = quiz2.id

        with patch("app.api.v1.quiz.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.side_effect = AgentServiceError(
                message="Agent crashed", status_code=500, agent_code=50099)
            r = await client.post("/api/v1/quiz/submit", json={
                "quiz_id": quiz2_id,
                "answers": [{"question_id": q_ids[0], "answer": "A"}],
                "time_spent": 60,
            }, headers=stu_headers)
            chk("Agent fail -> still 200", r.status_code == 200)
            data = r.json()["data"]
            chk("Agent fail -> score still returned", "score" in data)
            chk("Agent fail -> correct_count present", data.get("correct_count") == 1)
            chk("Agent fail -> background task triggered", mock_agent.called)

            await asyncio.sleep(0.5)

        async with async_session_factory() as db:
            q2_result = await db.execute(
                select(QuizSession).where(QuizSession.id == quiz2_id)
            )
            q2 = q2_result.scalar_one_or_none()
            chk("Agent fail -> diagnosis_json not written",
                q2 is not None and q2.diagnosis_json is None)

        # =============================================
        # A. QuizAnswer DB persistence
        # =============================================
        print("\n-- A. QuizAnswer DB verification --")
        async with async_session_factory() as db:
            qa_result = await db.execute(
                select(QuizAnswer).where(QuizAnswer.quiz_id == quiz_id, QuizAnswer.is_deleted == False)
            )
            answers_db = qa_result.scalars().all()
            chk("QuizAnswer -> count == 3", len(answers_db) == 3)

            answers_by_qid = {a.question_id: a for a in answers_db}
            chk("QuizAnswer -> q0 exists", q_ids[0] in answers_by_qid)
            chk("QuizAnswer -> q1 exists", q_ids[1] in answers_by_qid)
            chk("QuizAnswer -> q2 exists", q_ids[2] in answers_by_qid)
            chk("QuizAnswer -> q0 is_correct=True",
                answers_by_qid[q_ids[0]].is_correct == True)
            chk("QuizAnswer -> q1 is_correct=False",
                answers_by_qid[q_ids[1]].is_correct == False)
            chk("QuizAnswer -> q2 is_correct=True",
                answers_by_qid[q_ids[2]].is_correct == True)
            chk("QuizAnswer -> q0 user_answer='A'",
                answers_by_qid[q_ids[0]].user_answer in ("A", "['A']"))
            chk("QuizAnswer -> q1 user_answer='B'",
                answers_by_qid[q_ids[1]].user_answer in ("B", "['B']"))
            chk("QuizAnswer -> q0 correct_answer='A'",
                answers_by_qid[q_ids[0]].correct_answer == "A")

        # =============================================
        # B. Multi-choice scoring
        # =============================================
        print("\n-- B. Multi-choice scoring --")
        # B1: fully correct, same order
        async with async_session_factory() as db:
            quiz_b1 = QuizSession(user_id=stu_id, course_id=course_id, chapter="ch1")
            db.add(quiz_b1)
            await db.commit()
            quiz_b1_id = quiz_b1.id

        with patch("app.api.v1.quiz.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = {"diagnosis": {"summary": "mc test", "weak_points": [], "suggestions": []}}
            r = await client.post("/api/v1/quiz/submit", json={
                "quiz_id": quiz_b1_id,
                "answers": [{"question_id": mc_q_id, "answer": ["A", "C"]}],
                "time_spent": 30,
            }, headers=stu_headers)
            chk("MC full correct -> 200", r.status_code == 200)
            chk("MC full correct -> correct_count=1",
                r.json()["data"]["correct_count"] == 1)
            await asyncio.sleep(0.3)

        # B2: order-independent (["C", "A"] should also be correct)
        async with async_session_factory() as db:
            quiz_b2 = QuizSession(user_id=stu_id, course_id=course_id, chapter="ch1")
            db.add(quiz_b2)
            await db.commit()
            quiz_b2_id = quiz_b2.id

        with patch("app.api.v1.quiz.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = {"diagnosis": {"summary": "mc test2", "weak_points": [], "suggestions": []}}
            r = await client.post("/api/v1/quiz/submit", json={
                "quiz_id": quiz_b2_id,
                "answers": [{"question_id": mc_q_id, "answer": ["C", "A"]}],
                "time_spent": 30,
            }, headers=stu_headers)
            chk("MC reversed order -> correct_count=1",
                r.json()["data"]["correct_count"] == 1)
            await asyncio.sleep(0.3)

        # B3: incomplete (only ["A"])
        async with async_session_factory() as db:
            quiz_b3 = QuizSession(user_id=stu_id, course_id=course_id, chapter="ch1")
            db.add(quiz_b3)
            await db.commit()
            quiz_b3_id = quiz_b3.id

        with patch("app.api.v1.quiz.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = {"diagnosis": {"summary": "mc test3", "weak_points": [], "suggestions": []}}
            r = await client.post("/api/v1/quiz/submit", json={
                "quiz_id": quiz_b3_id,
                "answers": [{"question_id": mc_q_id, "answer": ["A"]}],
                "time_spent": 30,
            }, headers=stu_headers)
            chk("MC incomplete -> correct_count=0",
                r.json()["data"]["correct_count"] == 0)
            await asyncio.sleep(0.3)

        # B4: all wrong
        async with async_session_factory() as db:
            quiz_b4 = QuizSession(user_id=stu_id, course_id=course_id, chapter="ch1")
            db.add(quiz_b4)
            await db.commit()
            quiz_b4_id = quiz_b4.id

        with patch("app.api.v1.quiz.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = {"diagnosis": {"summary": "mc test4", "weak_points": [], "suggestions": []}}
            r = await client.post("/api/v1/quiz/submit", json={
                "quiz_id": quiz_b4_id,
                "answers": [{"question_id": mc_q_id, "answer": ["B", "D"]}],
                "time_spent": 30,
            }, headers=stu_headers)
            chk("MC all wrong -> correct_count=0",
                r.json()["data"]["correct_count"] == 0)
            await asyncio.sleep(0.3)

        # =============================================
        # C. Illegal question_id handling
        # =============================================
        print("\n-- C. Illegal question_id --")
        fake_qid = "nonexistent_" + uuid.uuid4().hex[:16]
        async with async_session_factory() as db:
            quiz_c = QuizSession(user_id=stu_id, course_id=course_id, chapter="ch1")
            db.add(quiz_c)
            await db.commit()
            quiz_c_id = quiz_c.id

        with patch("app.api.v1.quiz.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = {"diagnosis": {"summary": "edge", "weak_points": [], "suggestions": []}}
            r = await client.post("/api/v1/quiz/submit", json={
                "quiz_id": quiz_c_id,
                "answers": [
                    {"question_id": q_ids[0], "answer": "A"},
                    {"question_id": fake_qid, "answer": "anything"},
                ],
                "time_spent": 60,
            }, headers=stu_headers)
            chk("Illegal qid -> 200", r.status_code == 200)
            data = r.json()["data"]
            chk("Illegal qid -> correct_count=1 (fake not counted)",
                data["correct_count"] == 1)
            chk("Illegal qid -> total_count=2 (fake still counted)",
                data["total_count"] == 2)
            per_q = data.get("per_question_results", [])
            chk("Illegal qid -> per_question_results count=2",
                len(per_q) == 2)
            if len(per_q) == 2:
                chk("Illegal qid -> real answer is_correct=True",
                    per_q[0]["is_correct"] == True)
                chk("Illegal qid -> fake answer is_correct=False",
                    per_q[1]["is_correct"] == False)
                chk("Illegal qid -> fake answer correct_answer empty",
                    per_q[1]["correct_answer"] == "")
            await asyncio.sleep(0.3)
            chk("Illegal qid -> background task triggered",
                mock_agent.called)
            if mock_agent.called:
                agent_payload = mock_agent.call_args.args[1]
                agent_question_ids = {q["id"] for q in agent_payload["questions"]}
                agent_answer_ids = {a["question_id"] for a in agent_payload["answers"]}
                chk("Illegal qid -> fake excluded from Agent questions",
                    fake_qid not in agent_question_ids)
                chk("Illegal qid -> fake excluded from Agent answers",
                    fake_qid not in agent_answer_ids)
                chk("Illegal qid -> Agent payload questions/answers aligned",
                    agent_answer_ids <= agent_question_ids)

        # Verify only 1 QuizAnswer in DB (real question only)
        async with async_session_factory() as db:
            qa_count = await db.execute(
                select(func.count()).select_from(QuizAnswer).where(
                    QuizAnswer.quiz_id == quiz_c_id, QuizAnswer.is_deleted == False
                )
            )
            qa_n = qa_count.scalar()
            chk("Illegal qid -> QuizAnswer count=1 (no FK violation)",
                qa_n == 1)

        # =============================================
        # D. Empty answers list
        # =============================================
        print("\n-- D. Empty answers --")
        async with async_session_factory() as db:
            quiz_d = QuizSession(user_id=stu_id, course_id=course_id, chapter="ch1")
            db.add(quiz_d)
            await db.commit()
            quiz_d_id = quiz_d.id

        with patch("app.api.v1.quiz.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = {"diagnosis": {"summary": "empty", "weak_points": [], "suggestions": []}}
            r = await client.post("/api/v1/quiz/submit", json={
                "quiz_id": quiz_d_id,
                "answers": [],
                "time_spent": 30,
            }, headers=stu_headers)
            chk("Empty answers -> 200", r.status_code == 200)
            data = r.json()["data"]
            chk("Empty answers -> score=0", data.get("score") == 0)
            chk("Empty answers -> correct_count=0",
                data.get("correct_count") == 0)
            chk("Empty answers -> total_count=0",
                data.get("total_count") == 0)
            chk("Empty answers -> per_question_results=[]",
                data.get("per_question_results") == [])
            await asyncio.sleep(0.3)

        # Verify QuizSession row
        async with async_session_factory() as db:
            qd_result = await db.execute(
                select(QuizSession).where(QuizSession.id == quiz_d_id)
            )
            qd = qd_result.scalar_one_or_none()
            chk("Empty answers -> DB score=0",
                qd is not None and qd.score == 0)
            chk("Empty answers -> DB correct_count=0",
                qd is not None and qd.correct_count == 0)
            chk("Empty answers -> DB total_count=0",
                qd is not None and qd.total_count == 0)

        # =============================================
        # E. Invalid quiz_id -> 404
        # =============================================
        print("\n-- E. Invalid quiz_id -> 404 --")
        r = await client.post("/api/v1/quiz/submit", json={
            "quiz_id": "nonexistent_" + uuid.uuid4().hex[:16],
            "answers": [{"question_id": q_ids[0], "answer": "A"}],
            "time_spent": 60,
        }, headers=stu_headers)
        chk("Invalid quiz_id -> 404", r.status_code == 404)

        # =============================================
        # 4. result course-level aggregation
        # =============================================
        print("\n-- 4. result course-level aggregation --")
        r = await client.get(f"/api/v1/quiz/result?course_id={course_id}", headers=stu_headers)
        chk("result -> 200", r.status_code == 200)
        rdata = r.json()["data"]
        chk("result -> stats.total_attempts >= 2",
            rdata["stats"]["total_attempts"] >= 2)
        chk("result -> score_trend present",
            len(rdata["stats"]["score_trend"]) >= 2)
        chk("result -> latest_quiz present",
            rdata["latest_quiz"] is not None)
        submitted_attempts_before_empty_sessions = rdata["stats"]["total_attempts"]

        # =============================================
        # 4A. unsubmitted/empty-answer sessions do not pollute result/history
        # =============================================
        print("\n-- 4A. empty session filtering --")
        async with async_session_factory() as db:
            unsubmitted_quiz = QuizSession(
                user_id=stu_id,
                course_id=course_id,
                chapter="unsubmitted",
                score=0,
                total_count=4,
            )
            db.add(unsubmitted_quiz)
            await db.commit()
            unsubmitted_quiz_id = unsubmitted_quiz.id

        r = await client.get(f"/api/v1/quiz/result?course_id={course_id}", headers=stu_headers)
        result_after_empty_sessions = r.json()["data"]
        chk("unsubmitted session -> excluded from result attempts",
            result_after_empty_sessions["stats"]["total_attempts"] == submitted_attempts_before_empty_sessions)
        chk("unsubmitted session -> excluded from latest_quiz",
            result_after_empty_sessions["latest_quiz"]["quiz_id"] != unsubmitted_quiz_id)

        r = await client.get(f"/api/v1/quiz/history?course_id={course_id}", headers=stu_headers)
        history_after_empty_sessions = r.json()["data"]
        history_ids = {record["quiz_id"] for record in history_after_empty_sessions["records"]}
        chk("unsubmitted session -> excluded from history",
            unsubmitted_quiz_id not in history_ids)
        chk("empty-answer submit -> excluded from history",
            quiz_d_id not in history_ids)

        # =============================================
        # 5. result null when no sessions
        # =============================================
        print("\n-- 5. result null when empty --")
        r = await client.get("/api/v1/quiz/result?course_id=nonexistent", headers=stu_headers)
        chk("empty result -> 200", r.status_code == 200)
        rdata_empty = r.json()["data"]
        chk("empty result -> diagnosis is null",
            rdata_empty["diagnosis"] is None)
        chk("empty result -> total_attempts=0 (Bug 1 fixed)",
            rdata_empty["stats"]["total_attempts"] == 0)

        # =============================================
        # 6. result data-driven (no diagnosis_json dep) + shape check
        # =============================================
        print("\n-- 6. result data-driven shape --")
        r = await client.get(f"/api/v1/quiz/result?course_id={course_id}", headers=stu_headers)
        rdata = r.json()["data"]
        chk("data-driven -> diagnosis not null despite missing diagnosis_json on some sessions",
            rdata["diagnosis"] is not None)
        chk("data-driven -> diagnosis has summary",
            "summary" in rdata["diagnosis"])
        chk("data-driven -> diagnosis has weak_points",
            "weak_points" in rdata["diagnosis"])
        chk("data-driven -> diagnosis has suggestions",
            "suggestions" in rdata["diagnosis"])
        # Shape guard only. Final LLM-vs-data-driven semantics remain a tracked contract question.
        allowed_keys = {"summary", "weak_points", "suggestions"}
        actual_keys = set(rdata["diagnosis"].keys())
        extra_keys = actual_keys - allowed_keys
        chk(f"data-driven -> diagnosis shape has no extra keys (found: {extra_keys})",
            len(extra_keys) == 0)

        # =============================================
        # 6b. Agent diagnosis fusion regression guard
        # =============================================
        print("\n-- 6b. Agent diagnosis fusion --")
        diag_course_id = f"diag_fusion_{uuid.uuid4().hex[:8]}"
        async with async_session_factory() as db:
            c = Course(id=diag_course_id, name="Diag Fusion Course", course_code=diag_course_id, teacher_id=tea_id)
            db.add(c)
            db.add(CourseEnrollment(course_id=diag_course_id, student_id=stu_id))
            dq = QuizQuestion(
                course_id=diag_course_id, chapter="ch1",
                knowledge_point="kp_diag", type="single_choice",
                content="Diag Q?", options=["A", "B"], correct_answer="A",
                explanation="Diag expl",
            )
            db.add(dq)
            await db.flush()
            dq_id = dq.id
            # Session with Agent diagnosis (non-empty suggestions)
            ds_agent = QuizSession(
                user_id=stu_id, course_id=diag_course_id, chapter="ch1",
                score=50, correct_count=0, total_count=1, time_spent=30,
                diagnosis_json={
                    "summary": "agent: you missed kp_diag",
                    "weak_points": [{"name": "kp_diag", "error_pattern": "gap"}],
                    "suggestions": ["agent: review kp_diag fundamentals"],
                },
            )
            db.add(ds_agent)
            await db.flush()
            db.add(QuizAnswer(
                quiz_id=ds_agent.id, question_id=dq_id, user_answer="B",
                is_correct=False, correct_answer="A", explanation="Diag expl",
            ))
            await db.commit()
            ds_agent_id = ds_agent.id

        # (a) Agent suggestions non-empty → consumed
        r = await client.get(f"/api/v1/quiz/result?course_id={diag_course_id}", headers=stu_headers)
        rd = r.json()["data"]
        chk("agent diag -> suggestions consumed",
            "agent: review kp_diag fundamentals" in rd["diagnosis"]["suggestions"])
        chk("agent diag -> summary stays SQL (course-level, not per-session)",
            rd["diagnosis"]["summary"] != "agent: you missed kp_diag")

        # (b) Agent suggestions empty → fall back to SQL
        async with async_session_factory() as db:
            ds = await db.get(QuizSession, ds_agent_id)
            ds.diagnosis_json = {
                "summary": "agent summary", "weak_points": [], "suggestions": [],
            }
            await db.commit()
        r = await client.get(f"/api/v1/quiz/result?course_id={diag_course_id}", headers=stu_headers)
        rd = r.json()["data"]
        chk("empty suggestions -> fallback to SQL",
            "agent:" not in str(rd["diagnosis"]["suggestions"])
            and len(rd["diagnosis"]["suggestions"]) > 0)

        # (c) No diagnosis_json → full SQL fallback
        async with async_session_factory() as db:
            ds = await db.get(QuizSession, ds_agent_id)
            ds.diagnosis_json = None
            await db.commit()
        r = await client.get(f"/api/v1/quiz/result?course_id={diag_course_id}", headers=stu_headers)
        rd = r.json()["data"]
        chk("no diag -> suggestions non-empty",
            isinstance(rd["diagnosis"]["suggestions"], list)
            and len(rd["diagnosis"]["suggestions"]) > 0)
        chk("no diag -> summary is str", isinstance(rd["diagnosis"]["summary"], str))

        # (d) Whitespace-only suggestion strings → rejected, fallback to SQL
        async with async_session_factory() as db:
            ds = await db.get(QuizSession, ds_agent_id)
            ds.diagnosis_json = {
                "summary": "s", "weak_points": [],
                "suggestions": ["   ", "\t", "valid tip"],
            }
            await db.commit()
        r = await client.get(f"/api/v1/quiz/result?course_id={diag_course_id}", headers=stu_headers)
        rd = r.json()["data"]
        chk("whitespace strings -> rejected, fallback to SQL",
            "agent:" not in str(rd["diagnosis"]["suggestions"])
            and len(rd["diagnosis"]["suggestions"]) > 0)

        # (e) Latest session no diagnosis, older session has valid → consumed
        async with async_session_factory() as db:
            # Add a newer session WITHOUT diagnosis_json
            ds_new = QuizSession(
                user_id=stu_id, course_id=diag_course_id, chapter="ch1",
                score=100, correct_count=1, total_count=1, time_spent=20,
                diagnosis_json=None,  # no diagnosis
            )
            db.add(ds_new)
            await db.flush()
            db.add(QuizAnswer(
                quiz_id=ds_new.id, question_id=dq_id, user_answer="A",
                is_correct=True, correct_answer="A", explanation="Diag expl",
            ))
            # The OLDER session (ds_agent) now has valid suggestions set
            ds = await db.get(QuizSession, ds_agent_id)
            ds.diagnosis_json = {
                "summary": "old agent summary",
                "weak_points": [],
                "suggestions": ["old agent: review fundamentals", "old agent: practice more"],
            }
            await db.commit()
        r = await client.get(f"/api/v1/quiz/result?course_id={diag_course_id}", headers=stu_headers)
        rd = r.json()["data"]
        chk("latest no diag, old has valid -> consumed from old",
            "old agent: review fundamentals" in rd["diagnosis"]["suggestions"])

        # =============================================
        # F. Stats computation accuracy
        # =============================================
        print("\n-- F. Stats computation accuracy --")
        stats_course_id = f"stats_{uuid.uuid4().hex[:8]}"
        async with async_session_factory() as db:
            c = Course(id=stats_course_id, name="Stats Course", course_code=stats_course_id, teacher_id=tea_id)
            db.add(c)
            db.add(CourseEnrollment(course_id=stats_course_id, student_id=stu_id))
            await db.commit()

        async with async_session_factory() as db:
            stats_question = QuizQuestion(
                course_id=stats_course_id, chapter="ch1",
                knowledge_point="kp_stats", type="single_choice",
                content="Stats question?", options=["A", "B"],
                correct_answer="A",
            )
            db.add(stats_question)
            await db.flush()
            for score_val, time_val in [(60, 30), (80, 60), (100, 90)]:
                qs = QuizSession(
                    user_id=stu_id, course_id=stats_course_id, chapter="ch1",
                    score=score_val, correct_count=3, total_count=5,
                    time_spent=time_val,
                )
                db.add(qs)
                await db.flush()
                db.add(QuizAnswer(
                    quiz_id=qs.id, question_id=stats_question.id,
                    user_answer="A", is_correct=True, correct_answer="A",
                ))
            await db.commit()

        r = await client.get(f"/api/v1/quiz/result?course_id={stats_course_id}", headers=stu_headers)
        rdata = r.json()["data"]
        stats_f = rdata["stats"]
        chk("stats -> total_attempts exact",
            stats_f["total_attempts"] == 3)
        chk("stats -> avg_score exact",
            stats_f["avg_score"] == 80.0)
        chk("stats -> avg_time_spent exact",
            stats_f["avg_time_spent"] == 60)

        # =============================================
        # G. Score trend ordering
        # =============================================
        print("\n-- G. Score trend ordering --")
        trend_course_id = f"trend_{uuid.uuid4().hex[:8]}"
        async with async_session_factory() as db:
            c = Course(id=trend_course_id, name="Trend Course", course_code=trend_course_id, teacher_id=tea_id)
            db.add(c)
            db.add(CourseEnrollment(course_id=trend_course_id, student_id=stu_id))
            await db.commit()

        base_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
        async with async_session_factory() as db:
            trend_question = QuizQuestion(
                course_id=trend_course_id, chapter="ch1",
                knowledge_point="kp_trend", type="single_choice",
                content="Trend question?", options=["A", "B"],
                correct_answer="A",
            )
            db.add(trend_question)
            await db.flush()
            for i in range(5):
                qs = QuizSession(
                    user_id=stu_id, course_id=trend_course_id, chapter="ch1",
                    score=10 * (i + 1),
                    correct_count=3, total_count=5, time_spent=60,
                )
                qs.create_time = base_time + timedelta(minutes=i * 10)
                db.add(qs)
                await db.flush()
                db.add(QuizAnswer(
                    quiz_id=qs.id, question_id=trend_question.id,
                    user_answer="A", is_correct=True, correct_answer="A",
                ))
            await db.commit()

        r = await client.get(f"/api/v1/quiz/result?course_id={trend_course_id}",
                             headers=stu_headers)
        chk("trend -> 200", r.status_code == 200)
        rdata_g = r.json()["data"]
        trend = rdata_g["stats"]["score_trend"]
        chk("trend -> contains all 5 sessions", len(trend) == 5)
        if len(trend) >= 2:
            scores_ascending = all(
                trend[i]["score"] <= trend[i + 1]["score"]
                for i in range(len(trend) - 1)
            )
            chk("trend -> scores in ascending chronological order",
                scores_ascending)

        # =============================================
        # H. Diagnosis stability (contract-compliant structure)
        # =============================================
        print("\n-- H. Diagnosis stability --")
        diag_cid = f"diag_{uuid.uuid4().hex[:8]}"
        async with async_session_factory() as db:
            c = Course(id=diag_cid, name="Diag Course", course_code=diag_cid, teacher_id=tea_id)
            db.add(c)
            db.add(CourseEnrollment(course_id=diag_cid, student_id=stu_id))
            await db.commit()

        # Insert QuizQuestions + QuizAnswers with known knowledge_point distribution
        async with async_session_factory() as db:
            sess = QuizSession(
                user_id=stu_id, course_id=diag_cid, chapter="ch1",
                score=66.7, correct_count=2, total_count=3, time_spent=90,
            )
            db.add(sess)
            await db.flush()

            for kp_name, is_correct in [("kp_x", True), ("kp_x", False), ("kp_y", True)]:
                q = QuizQuestion(
                    course_id=diag_cid, chapter="ch1",
                    knowledge_point=kp_name, type="single_choice",
                    content=f"{kp_name} Q?", options=["A", "B", "C", "D"],
                    correct_answer="A",
                )
                db.add(q)
                await db.flush()
                ans = QuizAnswer(
                    quiz_id=sess.id, question_id=q.id,
                    user_answer="A" if is_correct else "B",
                    is_correct=is_correct, correct_answer="A",
                )
                db.add(ans)
            await db.commit()

        r = await client.get(f"/api/v1/quiz/result?course_id={diag_cid}",
                             headers=stu_headers)
        chk("diag stability -> 200", r.status_code == 200)
        rdata_h = r.json()["data"]
        chk("diag stability -> diagnosis not null",
            rdata_h["diagnosis"] is not None)
        diag_h = rdata_h["diagnosis"]
        diag_keys = set(diag_h.keys())
        allowed = {"summary", "weak_points", "suggestions"}
        extra = diag_keys - allowed
        chk(f"diag stability -> only contract fields (extra: {extra})",
            len(extra) == 0)
        chk("diag stability -> summary is non-empty string",
            isinstance(diag_h.get("summary"), str) and len(diag_h["summary"]) > 0)
        chk("diag stability -> weak_points is list",
            isinstance(diag_h.get("weak_points"), list))
        chk("diag stability -> suggestions is list",
            isinstance(diag_h.get("suggestions"), list))

    print(f"\n{'='*50}")
    print(f"  Total: {ok} OK, {fail} FAIL")
    return fail == 0


if __name__ == "__main__":
    import sys
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
