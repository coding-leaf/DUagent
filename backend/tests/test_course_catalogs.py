import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import re
import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.session import async_session_factory, engine, init_db
from app.main import app
from app.models.catalog import CourseCatalog, CourseCatalogMaterial, CourseOffering
from app.models.user import RegistrationCode
from app.schemas.catalog import CourseCatalogCreateRequest, CourseOfferingCreateRequest


def test_catalog_models_and_schemas_importable():
    catalog = CourseCatalog(
        title="数据结构",
        description="共享数据结构课程资源库",
        status="draft",
    )
    material = CourseCatalogMaterial(
        catalog_id="cat001",
        filename="ds.pdf",
        source_type="pdf",
        status="uploaded",
    )
    offering = CourseOffering(
        name="2026 春 数据结构 1 班",
        catalog_id="cat001",
        teacher_id="teacher001",
        class_code="ABC12345",
    )

    req = CourseCatalogCreateRequest(title="数据结构", description="基础课程")
    class_req = CourseOfferingCreateRequest(
        name="2026 春 数据结构 1 班",
        catalog_id="cat001",
        description="教学班",
    )

    assert catalog.title == "数据结构"
    assert material.source_type == "pdf"
    assert offering.catalog_id == "cat001"
    assert req.title == "数据结构"
    assert class_req.catalog_id == "cat001"


def _captcha_answer(question: str) -> str:
    nums = re.findall(r"\d+", question)
    if "+" in question:
        return str(int(nums[0]) + int(nums[1]))
    return str(int(nums[0]) - int(nums[1]))


async def _register_and_login(client: AsyncClient, role: str):
    code = f"{role}_{uuid.uuid4().hex[:8]}"
    async with async_session_factory() as db:
        db.add(RegistrationCode(code=code, role=role))
        await db.commit()

    email = f"{role}_{uuid.uuid4().hex[:8]}@test.com"
    username = f"{role}_{uuid.uuid4().hex[:8]}"
    captcha = await client.get("/api/v1/auth/captcha")
    captcha_data = captcha.json()["data"]
    register = await client.post("/api/v1/auth/register", json={
        "registration_code": code,
        "email": email,
        "password": "Abc12345",
        "username": username,
        "captcha_token": captcha_data["captcha_token"],
        "captcha_code": _captcha_answer(captcha_data["captcha_question"]),
    })
    assert register.status_code == 201, register.text

    captcha = await client.get("/api/v1/auth/captcha")
    captcha_data = captcha.json()["data"]
    login = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "Abc12345",
        "captcha_token": captcha_data["captcha_token"],
        "captcha_code": _captcha_answer(captcha_data["captcha_question"]),
    })
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['data']['token']}"}


async def _api_test_admin_catalog_crud():
    await init_db()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")
            teacher_headers = await _register_and_login(client, "teacher")

            create = await client.post("/api/v1/admin/course-catalogs", json={
                "title": "数据结构",
                "description": "平台共享数据结构资源库",
            }, headers=admin_headers)
            assert create.status_code == 201, create.text
            data = create.json()["data"]
            assert data["title"] == "数据结构"
            assert data["status"] == "draft"
            catalog_id = data["id"]

            listing = await client.get("/api/v1/admin/course-catalogs", headers=admin_headers)
            assert listing.status_code == 200, listing.text
            assert any(item["id"] == catalog_id for item in listing.json()["data"]["catalogs"])

            detail = await client.get(f"/api/v1/admin/course-catalogs/{catalog_id}", headers=admin_headers)
            assert detail.status_code == 200, detail.text
            assert detail.json()["data"]["id"] == catalog_id

            forbidden = await client.post("/api/v1/admin/course-catalogs", json={
                "title": "非管理员创建",
            }, headers=teacher_headers)
            assert forbidden.status_code == 403, forbidden.text
    finally:
        await engine.dispose()


def test_admin_catalog_crud():
    asyncio.run(_api_test_admin_catalog_crud())


async def _api_test_catalog_material_and_status():
    await init_db()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            admin_headers = await _register_and_login(client, "admin")

            create = await client.post("/api/v1/admin/course-catalogs", json={
                "title": "Python 程序设计",
                "description": "共享 Python 资源库",
            }, headers=admin_headers)
            catalog_id = create.json()["data"]["id"]

            material = await client.post(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials",
                json={
                    "filename": "python-intro.pdf",
                    "source_type": "pdf",
                    "storage_uri": "local://python-intro.pdf",
                },
                headers=admin_headers,
            )
            assert material.status_code == 201, material.text
            assert material.json()["data"]["filename"] == "python-intro.pdf"

            materials = await client.get(
                f"/api/v1/admin/course-catalogs/{catalog_id}/materials",
                headers=admin_headers,
            )
            assert materials.status_code == 200, materials.text
            assert len(materials.json()["data"]["materials"]) == 1

            status_res = await client.get(
                f"/api/v1/admin/course-catalogs/{catalog_id}/knowledge-status",
                headers=admin_headers,
            )
            assert status_res.status_code == 200, status_res.text
            status_data = status_res.json()["data"]
            assert status_data["catalog_id"] == catalog_id
            assert status_data["status"] == "draft"
            assert status_data["material_count"] == 1
    finally:
        await engine.dispose()


def test_catalog_material_and_status():
    asyncio.run(_api_test_catalog_material_and_status())
