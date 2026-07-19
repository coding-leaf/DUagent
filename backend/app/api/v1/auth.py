import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import (
    create_token,
    generate_captcha,
    hash_password,
    verify_captcha,
    verify_password,
)
from app.models.user import RegistrationCode, User
from app.schemas.auth import LoginRequest, RegisterRequest

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

PERMANENT_REGISTRATION_CODES = {
    "student": "student",
    "teacher": "teacher",
}


@router.get("/captcha")
async def get_captcha():
    data = generate_captcha()
    return {"code": 200, "message": "success", "data": data}


@router.post("/register", status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if not re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,32}$", req.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40001, "message": "密码需包含大小写字母和数字，8-32位", "data": None},
        )

    if req.guidance_level not in ("L1", "L2", "L3"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40001, "message": "引导粒度必须为 L1/L2/L3", "data": None},
        )

    if not verify_captcha(req.captcha_token, req.captcha_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40002, "message": "验证码错误或过期", "data": None},
        )

    result = await db.execute(
        select(RegistrationCode).where(
            RegistrationCode.code == req.registration_code,
            RegistrationCode.is_deleted == False,
        )
    )
    reg_code = result.scalar_one_or_none()
    role = reg_code.role if reg_code else PERMANENT_REGISTRATION_CODES.get(req.registration_code)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40001, "message": "注册码无效", "data": None},
        )

    result = await db.execute(
        select(User).where(User.email == req.email, User.is_deleted == False)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40900, "message": "邮箱已被注册", "data": None},
        )

    result = await db.execute(
        select(User).where(User.username == req.username, User.is_deleted == False)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40901, "message": "用户名已被占用", "data": None},
        )

    user = User(
        username=req.username,
        email=req.email,
        password_hash=hash_password(req.password),
        real_name=req.real_name,
        student_id=req.student_id,
        role=role,
        major=req.major,
        grade=req.grade,
        guidance_level=req.guidance_level,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return {
        "code": 201,
        "message": "created",
        "data": {"user_id": user.id, "email": user.email, "username": user.username},
    }


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    if not verify_captcha(req.captcha_token, req.captcha_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40002, "message": "验证码错误或过期", "data": None},
        )

    result = await db.execute(
        select(User).where(User.email == req.email, User.is_deleted == False)
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 40100, "message": "邮箱或密码错误", "data": None},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 40100, "message": "账号已被禁用", "data": None},
        )

    token = create_token(user.id, user.role)

    return {
        "code": 200,
        "message": "success",
        "data": {
            "token": token,
            "expires_in": 604800,
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "role": user.role,
            },
        },
    }
