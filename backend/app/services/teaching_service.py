"""Teacher-facing authorization facade and class/student read services."""

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from app.models.course import Course, CourseEnrollment
from app.models.user import User
from app.services.class_insights_query import ClassInsightsQuery
from app.services.student_report_query import StudentReportQuery


class TeachingService:
    """Authorize teacher reads and delegate focused report queries."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def verify_teacher(self, class_id: str, current_user: User) -> Course:
        """Return an owned course or raise the existing HTTP error contract."""
        result = await self.db.execute(
            select(Course)
            .options(noload(Course.enrollments))
            .where(
                Course.id == class_id,
                Course.is_deleted.is_(False),
            )
        )
        course = result.scalar_one_or_none()
        if course is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 40400, "message": "课程不存在", "data": None},
            )
        if course.teacher_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": 40300, "message": "无权访问此班级", "data": None},
            )
        return course

    async def _require_enrolled_student(
        self,
        class_id: str,
        student_id: str,
    ) -> User:
        """Return an active enrolled user without leaking outsider existence."""
        result = await self.db.execute(
            select(User)
            .join(CourseEnrollment, CourseEnrollment.student_id == User.id)
            .where(
                User.id == student_id,
                User.is_deleted.is_(False),
                CourseEnrollment.course_id == class_id,
                CourseEnrollment.is_deleted.is_(False),
            )
            .limit(1)
        )
        student = result.scalar_one_or_none()
        if student is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 40400, "message": "学生未入班", "data": None},
            )
        return student

    async def get_student_info(
        self,
        class_id: str,
        student_id: str,
        current_user: User,
    ) -> dict:
        """Return account details for an active student in an owned class."""
        await self.verify_teacher(class_id, current_user)
        user = await self._require_enrolled_student(class_id, student_id)
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "real_name": user.real_name,
            "student_id": user.student_id,
            "role": user.role,
            "major": user.major,
            "grade": user.grade,
            "guidance_level": user.guidance_level,
            "created_at": user.create_time.isoformat() if user.create_time else "",
        }

    async def list_students(
        self,
        class_id: str,
        current_user: User,
        page: int,
        page_size: int,
    ) -> dict:
        """Return a stable page of active enrollments without per-row queries."""
        await self.verify_teacher(class_id, current_user)
        active_filters = (
            CourseEnrollment.course_id == class_id,
            CourseEnrollment.is_deleted.is_(False),
            User.is_deleted.is_(False),
        )
        count_result = await self.db.execute(
            select(func.count(CourseEnrollment.id))
            .join(User, User.id == CourseEnrollment.student_id)
            .where(*active_filters)
        )
        rows = await self.db.execute(
            select(
                CourseEnrollment.create_time.label("joined_at"),
                User.id,
                User.username,
                User.real_name,
                User.student_id,
                User.major,
                User.grade,
            )
            .join(User, User.id == CourseEnrollment.student_id)
            .where(*active_filters)
            .order_by(
                CourseEnrollment.create_time.asc(),
                CourseEnrollment.id.asc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        students = [
            {
                "id": row.id,
                "username": row.username,
                "real_name": row.real_name,
                "student_id": row.student_id,
                "major": row.major,
                "grade": row.grade,
                "joined_at": row.joined_at.isoformat() if row.joined_at else "",
            }
            for row in rows
        ]
        return {
            "students": students,
            "total": count_result.scalar() or 0,
            "page": page,
            "page_size": page_size,
        }

    async def get_student_learning(
        self,
        class_id: str,
        student_id: str,
        current_user: User,
    ) -> dict:
        """Authorize and delegate a student learning report query."""
        await self.verify_teacher(class_id, current_user)
        student = await self._require_enrolled_student(class_id, student_id)
        return await StudentReportQuery(self.db).execute(class_id, student)

    async def get_class_insights(
        self,
        class_id: str,
        current_user: User,
    ) -> dict:
        """Authorize and delegate a class insights query."""
        await self.verify_teacher(class_id, current_user)
        return await ClassInsightsQuery(self.db).execute(class_id)
