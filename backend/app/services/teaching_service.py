"""Teacher-facing authorization facade and class/student read services."""

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from app.models.course import Course, CourseEnrollment
from app.models.others import LearningPath
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.user import User
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
        """Aggregate class evidence from active enrollments and latest paths."""
        await self.verify_teacher(class_id, current_user)
        active_enrollments = (
            select(CourseEnrollment.student_id)
            .join(User, User.id == CourseEnrollment.student_id)
            .where(
                CourseEnrollment.course_id == class_id,
                CourseEnrollment.is_deleted.is_(False),
                User.is_deleted.is_(False),
            )
        )
        enrollment_count = await self.db.execute(
            select(func.count(CourseEnrollment.id))
            .join(User, User.id == CourseEnrollment.student_id)
            .where(
                CourseEnrollment.course_id == class_id,
                CourseEnrollment.is_deleted.is_(False),
                User.is_deleted.is_(False),
            )
        )
        if not enrollment_count.scalar():
            return {
                "avg_quiz_score": None,
                "total_quiz_attempts": 0,
                "weak_points_top": [],
                "path_node_progress": {
                    "completed": 0,
                    "in_progress": 0,
                    "recommended": 0,
                    "pending": 0,
                    "total_nodes": 0,
                },
            }

        quiz_result = await self.db.execute(
            select(
                func.avg(QuizSession.score).label("avg_score"),
                func.count(QuizSession.id).label("total_attempts"),
            ).where(
                QuizSession.course_id == class_id,
                QuizSession.user_id.in_(active_enrollments),
                QuizSession.is_deleted.is_(False),
            )
        )
        quiz_row = quiz_result.one()

        error_count = func.sum(
            case((QuizAnswer.is_correct.is_(False), 1), else_=0)
        )
        total_attempts = func.count(QuizAnswer.id)
        weak_result = await self.db.execute(
            select(
                QuizQuestion.knowledge_point,
                total_attempts.label("total_attempts"),
                error_count.label("error_count"),
            )
            .join(QuizAnswer, QuizAnswer.question_id == QuizQuestion.id)
            .join(QuizSession, QuizSession.id == QuizAnswer.quiz_id)
            .where(
                QuizSession.course_id == class_id,
                QuizSession.user_id.in_(active_enrollments),
                QuizSession.is_deleted.is_(False),
                QuizAnswer.is_deleted.is_(False),
                QuizQuestion.is_deleted.is_(False),
                QuizQuestion.knowledge_point != "",
            )
            .group_by(QuizQuestion.knowledge_point)
            .having(error_count > 0)
            .order_by(
                (error_count / total_attempts).desc(),
                error_count.desc(),
            )
            .limit(5)
        )
        weak_points_top = []
        for row in weak_result:
            attempts = row.total_attempts or 0
            errors = row.error_count or 0
            weak_points_top.append(
                {
                    "knowledge_point": row.knowledge_point,
                    "error_count": errors,
                    "total_attempts": attempts,
                    "error_rate": round(errors / attempts, 2) if attempts else 0,
                }
            )

        ranked_paths = (
            select(
                LearningPath.nodes.label("nodes"),
                func.row_number()
                .over(
                    partition_by=LearningPath.user_id,
                    order_by=(
                        LearningPath.generated_at.desc(),
                        LearningPath.create_time.desc(),
                        LearningPath.id.desc(),
                    ),
                )
                .label("row_num"),
            )
            .where(
                LearningPath.course_id == class_id,
                LearningPath.user_id.in_(active_enrollments),
                LearningPath.is_deleted.is_(False),
            )
            .subquery()
        )
        path_result = await self.db.execute(
            select(ranked_paths.c.nodes).where(ranked_paths.c.row_num == 1)
        )
        known_statuses = ("completed", "in_progress", "recommended", "pending")
        progress = {item: 0 for item in known_statuses}
        for nodes in path_result.scalars():
            if not isinstance(nodes, list):
                continue
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                node_status = node.get("status")
                if node_status in progress:
                    progress[node_status] += 1

        return {
            "avg_quiz_score": (
                round(float(quiz_row.avg_score), 1)
                if quiz_row.avg_score is not None
                else None
            ),
            "total_quiz_attempts": quiz_row.total_attempts or 0,
            "weak_points_top": weak_points_top,
            "path_node_progress": {
                **progress,
                "total_nodes": sum(progress.values()),
            },
        }
