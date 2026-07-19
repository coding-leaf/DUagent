from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import CourseOffering
from app.models.course import Course, CourseEnrollment
from app.models.others import Resource
from app.models.user import User


class CourseResourceScope(BaseModel):
    class_course_id: str
    catalog_id: str | None = None


def _course_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": 40400, "message": "课程不存在", "data": None},
    )


def _course_forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": 40300, "message": "无权访问该课程", "data": None},
    )


async def ensure_course_resource_access(
    db: AsyncSession,
    current_user: User,
    course_id: str,
) -> Course:
    course_result = await db.execute(
        select(Course).where(Course.id == course_id, Course.is_deleted == False)
    )
    course = course_result.scalar_one_or_none()
    if course is None:
        raise _course_not_found()

    if current_user.role == "admin":
        return course
    if current_user.role == "teacher":
        if course.teacher_id != current_user.id:
            raise _course_forbidden()
        return course

    enrollment_result = await db.execute(
        select(CourseEnrollment).where(
            CourseEnrollment.course_id == course_id,
            CourseEnrollment.student_id == current_user.id,
            CourseEnrollment.is_deleted == False,
        )
    )
    if enrollment_result.scalar_one_or_none() is None:
        raise _course_forbidden()
    return course


async def resolve_course_resource_scope(
    db: AsyncSession,
    course_id: str,
) -> CourseResourceScope:
    offering_result = await db.execute(
        select(CourseOffering).where(
            CourseOffering.id == course_id,
            CourseOffering.is_deleted == False,
        )
    )
    offering = offering_result.scalar_one_or_none()
    return CourseResourceScope(
        class_course_id=course_id,
        catalog_id=offering.catalog_id if offering else None,
    )


def resource_scope_clause(course_id: str, catalog_id: str | None):
    legacy_clause = and_(Resource.catalog_id.is_(None), Resource.course_id == course_id)
    if catalog_id:
        return or_(Resource.catalog_id == catalog_id, legacy_clause)
    return legacy_clause


async def user_can_access_catalog_resources(
    db: AsyncSession,
    current_user: User,
    catalog_id: str,
) -> bool:
    if current_user.role == "admin":
        return True

    if current_user.role == "teacher":
        teacher_result = await db.execute(
            select(Course.id)
            .join(CourseOffering, CourseOffering.id == Course.id)
            .where(
                Course.teacher_id == current_user.id,
                Course.is_deleted == False,
                CourseOffering.catalog_id == catalog_id,
                CourseOffering.is_deleted == False,
            )
            .limit(1)
        )
        return teacher_result.scalar_one_or_none() is not None

    student_result = await db.execute(
        select(CourseEnrollment.id)
        .join(CourseOffering, CourseOffering.id == CourseEnrollment.course_id)
        .where(
            CourseEnrollment.student_id == current_user.id,
            CourseEnrollment.is_deleted == False,
            CourseOffering.catalog_id == catalog_id,
            CourseOffering.is_deleted == False,
        )
        .limit(1)
    )
    return student_result.scalar_one_or_none() is not None
