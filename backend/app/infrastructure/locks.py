from contextlib import asynccontextmanager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.base import DomainException

class LockAcquisitionTimeout(DomainException):
    """Exception raised when MySQL named lock acquisition times out."""
    def __init__(self, message: str = "服务繁忙，请稍后重试", code: int = 50300, status_code: int = 503):
        super().__init__(message=message, code=code, status_code=status_code)


@asynccontextmanager
async def profile_lock(db: AsyncSession, user_id: str, course_id: str):
    lock_name = f"profile_{user_id}_{course_id}"
    
    # Query MySQL Named Lock
    lock_result = await db.execute(
        text("SELECT GET_LOCK(:key, 5)"),
        params={"key": lock_name}
    )
    acquired = lock_result.scalar()
    if not acquired:
        raise LockAcquisitionTimeout(f"Lock timeout for profile of user: {user_id}, course: {course_id}")
        
    try:
        yield lock_name
    finally:
        await db.execute(
            text("SELECT RELEASE_LOCK(:key)"),
            params={"key": lock_name}
        )
