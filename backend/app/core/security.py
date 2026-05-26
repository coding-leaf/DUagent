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


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(user_id: str, role: str) -> str:
    """v1: Single JWT token, 7-day expiry."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "role": role,
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
