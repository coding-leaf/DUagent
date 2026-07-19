from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.user import UpdateUserRequest

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _user_info(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "real_name": u.real_name,
        "student_id": u.student_id,
        "role": u.role,
        "major": u.major,
        "grade": u.grade,
        "guidance_level": u.guidance_level,
        "created_at": u.create_time.isoformat() if u.create_time else "",
    }


@router.get("/me")
async def get_my_info(current_user: User = Depends(get_current_user)):
    return {"code": 200, "message": "success", "data": _user_info(current_user)}


@router.put("/me")
async def update_my_info(
    req: UpdateUserRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if req.real_name is not None:
        current_user.real_name = req.real_name
    if req.student_id is not None:
        current_user.student_id = req.student_id
    if req.major is not None:
        current_user.major = req.major
    if req.grade is not None:
        current_user.grade = req.grade
    if req.guidance_level is not None:
        if req.guidance_level not in ("L1", "L2", "L3"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": 40001, "message": "引导粒度必须为 L1/L2/L3", "data": None},
            )
        current_user.guidance_level = req.guidance_level
    await db.flush()
    await db.refresh(current_user)
    return {"code": 200, "message": "success", "data": _user_info(current_user)}
