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
    """我的课程列表"""
    course_list = []

    if current_user.role == "teacher":
        result = await db.execute(select(Course).where(Course.teacher_id == current_user.id))
        courses = result.scalars().all()
    else:
        result = await db.execute(
            select(CourseEnrollment).where(CourseEnrollment.student_id == current_user.id)
        )
        enrollments = result.scalars().all()
        course_ids = [e.course_id for e in enrollments]
        if course_ids:
            result = await db.execute(select(Course).where(Course.id.in_(course_ids)))
        else:
            result = None
        courses = result.scalars().all() if result else []

    for c in courses:
        teacher_name = ""
        tr = await db.execute(select(User).where(User.id == c.teacher_id))
        t = tr.scalar_one_or_none()
        if t:
            teacher_name = t.real_name or t.username

        count_r = await db.execute(
            select(func.count(CourseEnrollment.id)).where(CourseEnrollment.course_id == c.id)
        )
        student_count = count_r.scalar() or 0

        course_list.append({
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "course_code": c.course_code,
            "teacher_name": teacher_name,
            "student_count": student_count,
            "created_at": c.created_at.isoformat() if c.created_at else "",
        })

    return {"code": 200, "message": "success", "data": {"courses": course_list}}


@router.post("", status_code=201)
async def create_course(
    req: CourseCreateRequest,
    current_user: User = Depends(require_role("teacher")),
    db: AsyncSession = Depends(get_db),
):
    """创建课程/开班"""
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
        "code": 200,
        "message": "课程创建成功",
        "data": {
            "id": course.id,
            "name": course.name,
            "course_code": course.course_code,
        },
    }


@router.post("/join")
async def join_course(
    req: CourseJoinRequest,
    current_user: User = Depends(require_role("student")),
    db: AsyncSession = Depends(get_db),
):
    """加入课程"""
    result = await db.execute(select(Course).where(Course.course_code == req.course_code))
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "课程码不存在", "data": None},
        )

    # Check already enrolled
    check = await db.execute(
        select(CourseEnrollment).where(
            CourseEnrollment.student_id == current_user.id,
            CourseEnrollment.course_id == course.id,
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

    teacher_name = ""
    tr = await db.execute(select(User).where(User.id == course.teacher_id))
    t = tr.scalar_one_or_none()
    if t:
        teacher_name = t.real_name or t.username

    return {
        "code": 200,
        "message": "加入成功",
        "data": {
            "id": course.id,
            "name": course.name,
            "teacher_name": teacher_name,
        },
    }
