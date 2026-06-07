import os
import re
import sys
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test_auth_register_contract.db",
)

from app.db.session import async_session_factory, init_db
from app.main import app
from app.models.user import RegistrationCode, User


async def _captcha_answer(client):
    r = await client.get("/api/v1/auth/captcha")
    data = r.json()["data"]
    nums = re.findall(r"\d+", data["captcha_question"])
    answer = (
        str(int(nums[0]) + int(nums[1]))
        if "+" in data["captcha_question"]
        else str(int(nums[0]) - int(nums[1]))
    )
    return data["captcha_token"], answer


def _error_message(body: dict) -> str:
    detail = body.get("detail")
    if isinstance(body.get("message"), str):
        return body["message"]
    if isinstance(detail, dict) and isinstance(detail.get("message"), str):
        return detail["message"]
    if isinstance(detail, str):
        return detail
    return ""


@pytest.mark.asyncio
async def test_register_saves_profile_fields_and_reuses_registration_code():
    await init_db()
    suffix = uuid.uuid4().hex[:8]
    code = f"reg_{suffix}"

    async with async_session_factory() as db:
        db.add(RegistrationCode(code=code, role="student"))
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        captcha_token, captcha_code = await _captcha_answer(client)
        r = await client.post("/api/v1/auth/register", json={
            "registration_code": code,
            "email": f"student_{suffix}@example.com",
            "password": "Abc12345",
            "username": f"stu_{suffix}",
            "real_name": "张三",
            "student_id": f"2026{suffix}",
            "major": "计算机科学",
            "grade": "大一 (Freshman)",
            "guidance_level": "L1",
            "captcha_token": captcha_token,
            "captcha_code": captcha_code,
        })

    assert r.status_code == 201, r.json()
    user_id = r.json()["data"]["user_id"]

    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
        reg_code = (
            await db.execute(select(RegistrationCode).where(RegistrationCode.code == code))
        ).scalar_one()

    assert user.real_name == "张三"
    assert user.student_id == f"2026{suffix}"
    assert user.major == "计算机科学"
    assert user.grade == "大一 (Freshman)"
    assert user.guidance_level == "L1"
    assert reg_code.is_used is False
    assert reg_code.used_by is None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        captcha_token, captcha_code = await _captcha_answer(client)
        r = await client.post("/api/v1/auth/register", json={
            "registration_code": code,
            "email": f"student_reuse_{suffix}@example.com",
            "password": "Abc12345",
            "username": f"reuse_{suffix}",
            "captcha_token": captcha_token,
            "captcha_code": captcha_code,
        })

    assert r.status_code == 201, r.json()


@pytest.mark.asyncio
async def test_register_accepts_builtin_teacher_code_without_db_seed():
    await init_db()
    suffix = uuid.uuid4().hex[:8]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        captcha_token, captcha_code = await _captcha_answer(client)
        r = await client.post("/api/v1/auth/register", json={
            "registration_code": "teacher",
            "email": f"teacher_builtin_{suffix}@example.com",
            "password": "Abc12345",
            "username": f"tea_{suffix}",
            "captcha_token": captcha_token,
            "captcha_code": captcha_code,
        })

    assert r.status_code == 201, r.json()
    user_id = r.json()["data"]["user_id"]

    async with async_session_factory() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()

    assert user.role == "teacher"


@pytest.mark.asyncio
async def test_register_rejects_invalid_guidance_level_with_400():
    await init_db()
    suffix = uuid.uuid4().hex[:8]
    code = f"bad_guide_{suffix}"

    async with async_session_factory() as db:
        db.add(RegistrationCode(code=code, role="student"))
        await db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        captcha_token, captcha_code = await _captcha_answer(client)
        r = await client.post("/api/v1/auth/register", json={
            "registration_code": code,
            "email": f"bad_guide_{suffix}@example.com",
            "password": "Abc12345",
            "username": f"bad_{suffix}",
            "guidance_level": "L4",
            "captcha_token": captcha_token,
            "captcha_code": captcha_code,
        })

    assert r.status_code == 400
    assert "L1/L2/L3" in _error_message(r.json())
