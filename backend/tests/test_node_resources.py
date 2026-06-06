"""Integration tests for GET /api/v1/learning-path/nodes/{node_id}/resources.

Covers: 403 unauthorized course access, 200 with id fields present,
weak_point_tutorials[].content truncated to 160 chars, chapter_materials[].id present.

Requires MySQL or SQLite.

Run: python -m pytest tests/test_node_resources.py -v
"""
import asyncio
import os
import pytest
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_node_resources.db",
)

from app.db.session import async_session_factory, init_db
from httpx import AsyncClient, ASGITransport

asyncio.run(init_db())

from app.main import app
from app.models.user import RegistrationCode
from app.models.course import Course, CourseEnrollment
from app.models.others import LearningPath, Resource, CourseKnowledgeGraph
from app.models.quiz import QuizQuestion


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
    ct_token, ct_ans = await _captcha_answer(client)
    r = await client.post("/api/v1/auth/login", json={
        "email": email, "password": "Abc12345",
        "captcha_token": ct_token, "captcha_code": ct_ans,
    })
    assert "token" in r.json().get("data", {}), f"Login failed: {r.json()}"
    return {"Authorization": f"Bearer {r.json()['data']['token']}"}, r.json()["data"]["user"]["id"]


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
        # ===== Seed users =====
        codes = [
            RegistrationCode(code=f"stu_{uuid.uuid4().hex[:8]}", role="student"),
            RegistrationCode(code=f"stu2_{uuid.uuid4().hex[:8]}", role="student"),
            RegistrationCode(code=f"tea_{uuid.uuid4().hex[:8]}", role="teacher"),
        ]
        async with async_session_factory() as db:
            db.add_all(codes)
            await db.commit()
            student_code = codes[0].code
            student2_code = codes[1].code
            teacher_code = codes[2].code

        stu_headers, stu_id = await _register_and_login(
            client, student_code, f"stu_{uuid.uuid4().hex[:8]}@test.com", f"stu_{uuid.uuid4().hex[:8]}")
        stu2_headers, stu2_id = await _register_and_login(
            client, student2_code, f"stu2_{uuid.uuid4().hex[:8]}@test.com", f"stu2_{uuid.uuid4().hex[:8]}")
        tea_headers, tea_id = await _register_and_login(
            client, teacher_code, f"tea_{uuid.uuid4().hex[:8]}@test.com", f"tea_{uuid.uuid4().hex[:8]}")

        # ===== Create course =====
        r = await client.post("/api/v1/courses", json={"name": "NodeRes Test"}, headers=tea_headers)
        assert r.status_code == 201, f"Create course failed: {r.status_code} {r.json()}"
        course_data = r.json()["data"]
        course_id = course_data["id"]
        course_code = course_data.get("course_code", course_data.get("code", ""))

        join_r = await client.post("/api/v1/courses/join", json={"course_code": course_code}, headers=stu_headers)
        assert join_r.status_code == 200, f"Join failed: {join_r.status_code} {join_r.json()}"

        # ===== Seed LearningPath =====
        node_id = "node_001"
        node_name = "AVL树旋转"
        long_content = "X" * 300  # 300 chars, >160

        async with async_session_factory() as db:
            lp = LearningPath(
                user_id=stu_id,
                course_id=course_id,
                nodes=[{"id": node_id, "name": node_name, "status": "in_progress", "mastery": 50, "order": 1}],
                edges=[],
                current_node_id=node_id,
                current_node_name=node_name,
            )
            db.add(lp)
            # Resource for weak_point_tutorials (matched by knowledge_point == node_name)
            db.add(Resource(id="res_wp", course_id=course_id, title="弱项讲解", type="document",
                            knowledge_point=node_name, chapter="ch1", content=long_content))
            # Resource for chapter_materials (matched by chapter from KG)
            db.add(Resource(id="res_cm", course_id=course_id, title="章节资料", type="reading",
                            knowledge_point="other", chapter="ch1", content="章节内容"))
            # Knowledge graph for chapter lookup
            db.add(CourseKnowledgeGraph(
                course_id=course_id,
                nodes=[{"id": node_id, "name": node_name, "chapter": "ch1"}],
                edges=[],
            ))
            # QuizQuestion for exercises
            db.add(QuizQuestion(course_id=course_id, chapter="ch1", knowledge_point=node_name,
                                type="single_choice", content="What is AVL?",
                                options=["A","B","C","D"], correct_answer="A"))
            await db.commit()

        # ===== 1. 403 — student not enrolled =====
        print("\n-- 1. 403 no course access --")
        r = await client.get(
            f"/api/v1/learning-path/nodes/{node_id}/resources?course_id={course_id}",
            headers=stu2_headers)
        chk("403 student not enrolled", r.status_code == 403)

        # ===== 2. 200 — id fields present =====
        print("\n-- 2. id fields present --")
        r = await client.get(
            f"/api/v1/learning-path/nodes/{node_id}/resources?course_id={course_id}",
            headers=stu_headers)
        chk("200 success", r.status_code == 200)
        data = r.json()["data"]
        chk("node_id present", data.get("node_id") == node_id)
        chk("node_name present", data.get("node_name") == node_name)

        # weak_point_tutorials
        wp = data.get("weak_point_tutorials", [])
        chk("weak_point_tutorials non-empty", len(wp) > 0)
        if len(wp) > 0:
            chk("weak_point_tutorials[0].id present", wp[0].get("id") == "res_wp")
            chk("weak_point_tutorials[0].title present", wp[0].get("title") == "弱项讲解")
            chk("weak_point_tutorials[0].content is str", isinstance(wp[0].get("content"), str))
            chk("weak_point_tutorials[0].content truncated to 160",
                len(wp[0]["content"]) == 160)
            chk("weak_point_tutorials[0].content is prefix",
                long_content.startswith(wp[0]["content"]))

        # chapter_materials
        cm = data.get("chapter_materials", [])
        chk("chapter_materials non-empty", len(cm) > 0)
        if len(cm) > 0:
            chk("chapter_materials[0].id present", bool(cm[0].get("id")))
            chk("chapter_materials[0].title present", bool(cm[0].get("title")))
            chk("chapter_materials[0].type present", bool(cm[0].get("type")))
            # both resources (weak_point and chapter_material) share the same chapter,
            # so both appear. Verify res_cm is among them.
            cm_ids = {r.get("id") for r in cm}
            chk("chapter_materials include res_cm", "res_cm" in cm_ids)
            chk("chapter_materials include res_wp", "res_wp" in cm_ids)

        # exercises
        ex = data.get("exercises", [])
        chk("exercises non-empty", len(ex) > 0)
        if len(ex) > 0:
            chk("exercises[0].id present", "id" in ex[0])
            chk("exercises[0].type present", ex[0].get("type") == "single_choice")

        # full_exercise_set
        fe = data.get("full_exercise_set", [])
        chk("full_exercise_set non-empty", len(fe) > 0)

        # ===== 3. empty node (no matching resources) =====
        print("\n-- 3. empty resources --")
        r = await client.get(
            f"/api/v1/learning-path/nodes/nonexistent_node/resources?course_id={course_id}",
            headers=stu_headers)
        chk("empty node -> 200", r.status_code == 200)
        edata = r.json()["data"]
        chk("empty weak_point_tutorials", edata.get("weak_point_tutorials") == [])
        chk("empty exercises", edata.get("exercises") == [])
        chk("empty chapter_materials", edata.get("chapter_materials") == [])

    print(f"\n{'='*50}")
    print(f"  Total: {ok} OK, {fail} FAIL")
    assert fail == 0, f"{fail} check(s) FAIL"
    return True


if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
