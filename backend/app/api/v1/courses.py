import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, require_role
from app.models.course import Course, CourseEnrollment
from app.models.user import User
from app.schemas.course import CourseCreateRequest, CourseJoinRequest

router = APIRouter(prefix="/api/v1/courses", tags=["courses"])


def _gen_course_code() -> str:
    return uuid.uuid4().hex[:8].upper()


@router.get("")
async def list_courses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == "teacher":
        result = await db.execute(
            select(Course).where(Course.teacher_id == current_user.id, Course.is_deleted == False)
        )
        courses = result.scalars().all()
    else:
        result = await db.execute(
            select(CourseEnrollment).where(
                CourseEnrollment.student_id == current_user.id,
                CourseEnrollment.is_deleted == False,
            )
        )
        enrollments = result.scalars().all()
        course_ids = [e.course_id for e in enrollments]
        if course_ids:
            result = await db.execute(
                select(Course).where(Course.id.in_(course_ids), Course.is_deleted == False)
            )
        else:
            result = None
        courses = result.scalars().all() if result else []

    course_list = []
    for c in courses:
        tr = await db.execute(select(User).where(User.id == c.teacher_id))
        t = tr.scalar_one_or_none()
        teacher_name = (t.real_name or t.username) if t else ""

        count_r = await db.execute(
            select(func.count(CourseEnrollment.id)).where(
                CourseEnrollment.course_id == c.id, CourseEnrollment.is_deleted == False
            )
        )
        student_count = count_r.scalar() or 0

        course_list.append({
            "id": c.id,
            "name": c.name,
            "description": c.description or "",
            "course_code": c.course_code,
            "teacher_name": teacher_name,
            "student_count": student_count,
            "created_at": c.create_time.isoformat() if c.create_time else "",
        })

    return {"code": 200, "message": "success", "data": {"courses": course_list}}


@router.post("", status_code=201)
async def create_course(
    req: CourseCreateRequest,
    current_user: User = Depends(require_role("teacher")),
    db: AsyncSession = Depends(get_db),
):
    course = Course(
        name=req.name,
        description=req.description or "",
        course_code=_gen_course_code(),
        teacher_id=current_user.id,
    )
    db.add(course)
    await db.flush()
    await db.refresh(course)

    return {
        "code": 201,
        "message": "created",
        "data": {"id": course.id, "name": course.name, "course_code": course.course_code},
    }


@router.post("/join")
async def join_course(
    req: CourseJoinRequest,
    current_user: User = Depends(require_role("student")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Course).where(Course.course_code == req.course_code, Course.is_deleted == False)
    )
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "课程码不存在", "data": None},
        )

    check = await db.execute(
        select(CourseEnrollment).where(
            CourseEnrollment.student_id == current_user.id,
            CourseEnrollment.course_id == course.id,
            CourseEnrollment.is_deleted == False,
        )
    )
    if check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 40902, "message": "已加入该课程", "data": None},
        )

    enrollment = CourseEnrollment(student_id=current_user.id, course_id=course.id)
    db.add(enrollment)
    await db.flush()

    tr = await db.execute(select(User).where(User.id == course.teacher_id))
    t = tr.scalar_one_or_none()
    teacher_name = (t.real_name or t.username) if t else ""

    return {
        "code": 200,
        "message": "success",
        "data": {"id": course.id, "name": course.name, "teacher_name": teacher_name},
    }
