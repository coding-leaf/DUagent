"""Integration tests for GET /api/v1/resources/{id}.

Covers: 401 unauthorized, 404 not found, 403 no course access,
200 document/reading content_preview, 200 all resource types content.

Requires MySQL or SQLite.

Run: python -m pytest tests/test_resource_detail.py -v
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
    "sqlite+aiosqlite:///./test_resource.db",
)

from app.db.session import async_session_factory, init_db
from httpx import AsyncClient, ASGITransport

# Ensure tables exist
asyncio.run(init_db())

from app.main import app
from app.models.user import RegistrationCode
from app.models.catalog import CourseCatalog, CourseOffering
from app.models.course import Course, CourseEnrollment
from app.models.others import Resource


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
        # =============================================
        # Seed: users, courses, resources
        # =============================================
        uname = f"stu_{uuid.uuid4().hex[:8]}"
        email = f"{uname}@test.com"
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

        stu_headers, stu_id = await _register_and_login(client, student_code, email, uname)
        stu2_headers, stu2_id = await _register_and_login(
            client, student2_code, f"stu2_{uuid.uuid4().hex[:8]}@test.com",
            f"stu2_{uuid.uuid4().hex[:8]}")
        tea_headers, tea_id = await _register_and_login(
            client, teacher_code, f"tea_{uuid.uuid4().hex[:8]}@test.com",
            f"tea_{uuid.uuid4().hex[:8]}")

        # Create course
        r = await client.post("/api/v1/courses", json={"name": "Resource Test Course"}, headers=tea_headers)
        assert r.status_code == 201, f"Create course failed: {r.status_code} {r.json()}"
        course_data = r.json()["data"]
        course_id = course_data["id"]
        course_code = course_data.get("course_code", course_data.get("code", ""))

        # Enroll student1 (not student2)
        join_r = await client.post("/api/v1/courses/join", json={"course_code": course_code}, headers=stu_headers)
        assert join_r.status_code == 200, f"Join course failed: {join_r.status_code} {join_r.json()}"

        # Create second course for student2 (to test cross-course access)
        r2 = await client.post("/api/v1/courses", json={"name": "Student2 Course"}, headers=tea_headers)
        assert r2.status_code == 201
        course2_data = r2.json()["data"]
        course2_id = course2_data["id"]
        course2_code = course2_data.get("course_code", course2_data.get("code", ""))
        join2_r = await client.post("/api/v1/courses/join", json={"course_code": course2_code}, headers=stu2_headers)
        assert join2_r.status_code == 200, f"Join course2 failed: {join2_r.status_code} {join2_r.json()}"

        catalog_id = f"catalog_shared_{uuid.uuid4().hex[:8]}"
        async with async_session_factory() as db:
            db.add(
                CourseCatalog(
                    id=catalog_id,
                    title="Shared Catalog",
                    status="ready",
                    knowledge_status="ready",
                    material_count=1,
                    chunk_count=3,
                )
            )
            db.add_all([
                    CourseOffering(
                        id=course_id,
                        name="Resource Test Course",
                        catalog_id=catalog_id,
                        teacher_id=tea_id,
                        class_code=course_code,
                    ),
                    CourseOffering(
                        id=course2_id,
                        name="Student2 Course",
                        catalog_id=catalog_id,
                        teacher_id=tea_id,
                        class_code=course2_code,
                ),
            ])
            await db.commit()

        # Insert resources directly via DB
        doc_id = f"res_doc{uuid.uuid4().hex[:8]}"
        reading_id = f"res_read{uuid.uuid4().hex[:8]}"
        code_id = f"res_code{uuid.uuid4().hex[:8]}"
        mindmap_id = f"res_mm{uuid.uuid4().hex[:8]}"
        video_id = f"res_vid{uuid.uuid4().hex[:8]}"
        shared_id = f"res_shared{uuid.uuid4().hex[:8]}"

        sample_content = "这是一段测试正文内容。" * 60  # ~600 chars

        async with async_session_factory() as db:
            resources = [
                Resource(id=doc_id, course_id=course_id, title="Doc Resource",
                         type="document", content=sample_content, chapter="ch1"),
                Resource(id=reading_id, course_id=course_id, title="Reading Resource",
                         type="reading", content="Short reading text.", chapter="ch2"),
                Resource(id=code_id, course_id=course_id, title="Code Resource",
                         type="code", content="print('hello')", chapter="ch3"),
                Resource(id=mindmap_id, course_id=course_id, title="Mindmap Resource",
                         type="mindmap", content=None, chapter="ch4"),
                Resource(id=video_id, course_id=course_id, title="Video Resource",
                         type="video", content=None, chapter="ch5"),
                Resource(id=shared_id, course_id=course_id, catalog_id=catalog_id,
                         title="Shared Catalog Resource", type="document", content="shared doc content",
                         chapter="共享章节", knowledge_point="共享知识点"),
            ]
            db.add_all(resources)
            await db.commit()

        # =============================================
        # 1. 401 — Unauthorized (no token)
        # =============================================
        print("\n-- 1. 401 unauthorized --")
        r = await client.get(f"/api/v1/resources/{doc_id}")
        chk("401 no token", r.status_code == 401)

        # =============================================
        # 2. 404 — Resource not found
        # =============================================
        print("\n-- 2. 404 not found --")
        r = await client.get(f"/api/v1/resources/nonexistent_{uuid.uuid4().hex[:16]}", headers=stu_headers)
        chk("404 nonexistent id", r.status_code == 404)

        r = await client.get("/api/v1/resources/", headers=stu_headers)
        chk("404 empty id (path mismatch)", r.status_code in (404, 405, 307))

        # =============================================
        # 3. 403 — No course access
        # =============================================
        print("\n-- 3. 403 no course access --")
        # student2 is NOT enrolled in course_id
        r = await client.get(f"/api/v1/resources/{doc_id}", headers=stu2_headers)
        chk("403 student not enrolled", r.status_code == 403)

        # student1 IS enrolled — should get 200
        r = await client.get(f"/api/v1/resources/{doc_id}", headers=stu_headers)
        chk("200 enrolled student can access", r.status_code == 200)

        # teacher who created the course can access
        r = await client.get(f"/api/v1/resources/{doc_id}", headers=tea_headers)
        chk("200 teacher can access", r.status_code == 200)

        # student2 is enrolled in another class bound to the same catalog — should also get 200
        r = await client.get(f"/api/v1/resources/{shared_id}", headers=stu2_headers)
        chk("200 shared catalog resource visible across bound classes", r.status_code == 200)

        # =============================================
        # 4. 200 — document type returns content_preview
        # =============================================
        print("\n-- 4. document content_preview --")
        r = await client.get(f"/api/v1/resources/{doc_id}", headers=stu_headers)
        chk("document -> 200", r.status_code == 200)
        data = r.json()["data"]
        chk("document -> content_preview is string",
            isinstance(data.get("content_preview"), str))
        chk("document -> content_preview truncated to 500",
            len(data["content_preview"]) == 500)
        chk("document -> content_preview is prefix of content",
            sample_content.startswith(data["content_preview"]))
        chk("document -> type field present", data.get("type") == "document")
        chk("document -> title field present", data.get("title") == "Doc Resource")

        # =============================================
        # 5. 200 — reading type returns content_preview
        # =============================================
        print("\n-- 5. reading content_preview --")
        r = await client.get(f"/api/v1/resources/{reading_id}", headers=stu_headers)
        chk("reading -> 200", r.status_code == 200)
        data = r.json()["data"]
        chk("reading -> content_preview is string",
            isinstance(data.get("content_preview"), str))
        chk("reading -> content_preview exact",
            data["content_preview"] == "Short reading text.")
        chk("reading -> type field present", data.get("type") == "reading")

        # =============================================
        # 6. 200 — code type returns content
        # =============================================
        print("\n-- 6. code content --")
        r = await client.get(f"/api/v1/resources/{code_id}", headers=stu_headers)
        chk("code -> 200", r.status_code == 200)
        data = r.json()["data"]
        chk("code -> content_preview is null",
            data.get("content_preview") is None)
        chk("code -> content is full source",
            data.get("content") == "print('hello')")
        chk("code -> type field present", data.get("type") == "code")

        # =============================================
        # 7. 200 — mindmap type returns null content_preview
        # =============================================
        print("\n-- 7. mindmap content_preview null --")
        r = await client.get(f"/api/v1/resources/{mindmap_id}", headers=stu_headers)
        chk("mindmap -> 200", r.status_code == 200)
        data = r.json()["data"]
        chk("mindmap -> content_preview is null",
            data.get("content_preview") is None)
        chk("mindmap -> type field present", data.get("type") == "mindmap")

        # =============================================
        # 8. 200 — video type returns null content_preview
        # =============================================
        print("\n-- 8. video content_preview null --")
        r = await client.get(f"/api/v1/resources/{video_id}", headers=stu_headers)
        chk("video -> 200", r.status_code == 200)
        data = r.json()["data"]
        chk("video -> content_preview is null",
            data.get("content_preview") is None)
        chk("video -> type field present", data.get("type") == "video")

        # =============================================
        # 9. Response shape check
        # =============================================
        print("\n-- 9. response shape --")
        r = await client.get(f"/api/v1/resources/{doc_id}", headers=stu_headers)
        data = r.json()["data"]
        expected_fields = {"id", "course_id", "title", "type", "description", "tags", "chapter",
                           "knowledge_point", "view_count", "created_at", "content_preview",
                           "content"}
        actual_fields = set(data.keys())
        missing = expected_fields - actual_fields
        extra = actual_fields - expected_fields
        chk(f"shape -> no missing fields (missing: {missing})", len(missing) == 0)
        chk(f"shape -> no extra fields (extra: {extra})", len(extra) == 0)

    print(f"\n{'='*50}")
    print(f"  Total: {ok} OK, {fail} FAIL")
    assert fail == 0, f"{fail} check(s) FAIL"
    return True


if __name__ == "__main__":
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
