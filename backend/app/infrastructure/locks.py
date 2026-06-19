from contextlib import asynccontextmanager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

class LockAcquisitionTimeout(Exception):
    """Exception raised when MySQL named lock acquisition times out."""
    pass

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
