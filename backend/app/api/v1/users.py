from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.course import Course, CourseEnrollment
from app.models.user import User
from app.schemas.user import CourseItem, UpdateUserRequest

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me")
async def get_my_info(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """获取个人信息"""
    courses = []
    if current_user.role == "teacher":
        result = await db.execute(
            select(Course).where(Course.teacher_id == current_user.id)
        )
        for c in result.scalars().all():
            courses.append(CourseItem(course_id=c.id, course_name=c.name, course_code=c.course_code))
    else:
        result = await db.execute(
            select(CourseEnrollment).where(CourseEnrollment.student_id == current_user.id)
        )
        enrollments = result.scalars().all()
        for enr in enrollments:
            result2 = await db.execute(select(Course).where(Course.id == enr.course_id))
            c = result2.scalar_one_or_none()
            if c:
                courses.append(CourseItem(course_id=c.id, course_name=c.name, course_code=c.course_code))

    return {
        "code": 200,
        "message": "success",
        "data": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "real_name": current_user.real_name,
            "student_id": current_user.student_id,
            "role": current_user.role,
            "major": current_user.major,
            "grade": current_user.grade,
            "guidance_level": current_user.guidance_level,
            "courses": [c.model_dump() for c in courses],
            "created_at": current_user.created_at.isoformat() if current_user.created_at else "",
        },
    }


@router.put("/me")
async def update_my_info(
    req: UpdateUserRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改个人信息"""
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
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": 40001, "message": "引导粒度必须为 L1/L2/L3", "data": None},
            )
        current_user.guidance_level = req.guidance_level
    await db.flush()
    await db.refresh(current_user)

    return {
        "code": 200,
        "message": "success",
        "data": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "real_name": current_user.real_name,
            "student_id": current_user.student_id,
            "role": current_user.role,
            "major": current_user.major,
            "grade": current_user.grade,
            "guidance_level": current_user.guidance_level,
            "courses": [],
            "created_at": current_user.created_at.isoformat() if current_user.created_at else "",
        },
    }
