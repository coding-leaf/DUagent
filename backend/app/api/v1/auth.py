import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import (
    generate_captcha,
    generate_reset_code,
    hash_password,
    verify_captcha,
    verify_password,
    verify_reset_code,
    create_access_token,
    create_refresh_token,
    decode_token,
    invalidate_refresh_token,
    is_refresh_token_invalid,
)
from app.models.user import RegistrationCode, User
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SendResetCodeRequest,
)
from app.schemas.common import CaptchaResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/captcha")
async def get_captcha():
    """获取验证码"""
    data = generate_captcha()
    return {"code": 200, "message": "success", "data": data}


@router.post("/register", status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """注册"""
    # Validate password
    if not re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,32}$", req.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40001, "message": "密码需包含大小写字母和数字，8-32位", "data": None},
        )

    # Validate registration code
    result = await db.execute(
        select(RegistrationCode).where(
            RegistrationCode.code == req.registration_code,
            RegistrationCode.is_used == False,
        )
    )
    reg_code = result.scalar_one_or_none()
    if reg_code is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40001, "message": "注册码无效或已被使用", "data": None},
        )

    # Check email uniqueness
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40900, "message": "邮箱已被注册", "data": None},
        )

    # Check username uniqueness
    result = await db.execute(select(User).where(User.username == req.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40901, "message": "用户名已被占用", "data": None},
        )

    # Create user
    user = User(
        username=req.username,
        email=req.email,
        password_hash=hash_password(req.password),
        role=reg_code.role,
    )
    reg_code.is_used = True
    reg_code.used_by = user.id
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return {
        "code": 200,
        "message": "注册成功",
        "data": {"user_id": user.id, "email": user.email, "username": user.username},
    }


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """登录"""
    if not verify_captcha(req.captcha_token, req.captcha_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40002, "message": "验证码错误或过期", "data": None},
        )

    result = await db.execute(select(User).where(User.email == req.email))
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

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id, user.role)

    return {
        "code": 200,
        "message": "success",
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": 1800,
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "role": user.role,
            },
        },
    }


@router.post("/refresh")
async def refresh_token(req: RefreshTokenRequest):
    """刷新Token"""
    payload = decode_token(req.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 40101, "message": "refresh_token 无效或已过期", "data": None},
        )
    if is_refresh_token_invalid(req.refresh_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 40101, "message": "refresh_token 已被注销", "data": None},
        )

    invalidate_refresh_token(req.refresh_token)
    new_access = create_access_token(payload["sub"], payload["role"])

    return {
        "code": 200,
        "message": "success",
        "data": {
            "access_token": new_access,
            "expires_in": 1800,
        },
    }


@router.post("/send-reset-code")
async def send_reset_code(req: SendResetCodeRequest, db: AsyncSession = Depends(get_db)):
    """发送重置密码验证码"""
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if user:
        code = generate_reset_code(req.email)
        # In production: send email with code
        print(f"[DEV] Reset code for {req.email}: {code}")
    return {"code": 200, "message": "success", "data": {}}


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """重置密码"""
    if not verify_reset_code(req.email, req.reset_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 40003, "message": "验证码错误或过期", "data": None},
        )
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "用户不存在", "data": None},
        )
    user.password_hash = hash_password(req.new_password)
    await db.flush()
    return {"code": 200, "message": "密码重置成功", "data": {}}
