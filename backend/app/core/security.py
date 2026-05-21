import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory captcha store (use Redis in production)
_captcha_store: dict[str, dict] = {}
# In-memory reset code store
_reset_code_store: dict[str, dict] = {}
# In-memory refresh token blacklist
_refresh_token_blacklist: set[str] = set()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "role": role,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def invalidate_refresh_token(token: str) -> None:
    _refresh_token_blacklist.add(token)


def is_refresh_token_invalid(token: str) -> bool:
    return token in _refresh_token_blacklist


def generate_captcha() -> dict:
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    op = random.choice(["+", "-"])
    if op == "-" and a < b:
        a, b = b, a
    question = f"{a} {op} {b} = ?"
    answer = str(a + b if op == "+" else a - b)
    token = f"captcha_{uuid.uuid4().hex}"
    _captcha_store[token] = {
        "answer": answer,
        "expires_at": time.time() + settings.CAPTCHA_EXPIRE_SECONDS,
    }
    return {"captcha_token": token, "captcha_question": question}


def verify_captcha(token: str, code: str) -> bool:
    entry = _captcha_store.pop(token, None)
    if entry is None:
        return False
    if time.time() > entry["expires_at"]:
        return False
    return entry["answer"] == code.strip()


def generate_reset_code(email: str) -> str:
    code = f"{random.randint(100000, 999999)}"
    _reset_code_store[email] = {
        "code": code,
        "expires_at": time.time() + settings.CAPTCHA_EXPIRE_SECONDS,
    }
    return code


def verify_reset_code(email: str, code: str) -> bool:
    entry = _reset_code_store.pop(email, None)
    if entry is None:
        return False
    if time.time() > entry["expires_at"]:
        return False
    return entry["code"] == code.strip()
