"""Teacher-facing read services for class and student reports."""

import math

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from app.models.course import Course, CourseEnrollment
from app.models.others import Evaluation, LearningPath, UserProfile
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.user import User


def _overall_score(mastery_table: object) -> float | None:
    """Return the mean of valid mastery average scores."""
    if not isinstance(mastery_table, dict):
        return None
    rows = mastery_table.get("rows")
    if not isinstance(rows, list):
        return None

    scores: list[float] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_score = row.get("average_score")
        if isinstance(raw_score, bool):
            continue
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            continue
        if math.isfinite(score) and 0 <= score <= 100:
            scores.append(score)

    return round(sum(scores) / len(scores), 1) if scores else None


def _ranked_modal_preferences(preferences: object) -> list[str]:
    """Return modality keys ordered by numeric preference weight."""
    if not isinstance(preferences, dict):
        return []

    def sort_key(item: tuple[object, object]) -> tuple[int, float, str]:
        name, raw_weight = item
        if isinstance(raw_weight, bool):
            return (1, 0, str(name))
        try:
            weight = float(raw_weight)
        except (TypeError, ValueError):
            return (1, 0, str(name))
        if not math.isfinite(weight):
            return (1, 0, str(name))
        return (0, -weight, str(name))

    return [str(name) for name, _weight in sorted(preferences.items(), key=sort_key)]


class TeachingService:
    """Coordinate teacher authorization and read-only teaching queries."""

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

    async def _latest_evaluation(
        self,
        user_id: str,
        course_id: str,
    ) -> Evaluation | None:
        result = await self.db.execute(
            select(Evaluation)
            .where(
                Evaluation.user_id == user_id,
                Evaluation.course_id == course_id,
                Evaluation.is_deleted.is_(False),
            )
            .order_by(
                Evaluation.generated_at.desc(),
                Evaluation.create_time.desc(),
                Evaluation.id.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _latest_profile(
        self,
        user_id: str,
        course_id: str,
    ) -> UserProfile | None:
        result = await self.db.execute(
            select(UserProfile)
            .where(
                UserProfile.user_id == user_id,
                UserProfile.course_id == course_id,
                UserProfile.is_deleted.is_(False),
            )
            .order_by(
                UserProfile.generated_at.desc(),
                UserProfile.create_time.desc(),
                UserProfile.id.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _latest_learning_path(
        self,
        user_id: str,
        course_id: str,
    ) -> LearningPath | None:
        result = await self.db.execute(
            select(LearningPath)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.course_id == course_id,
                LearningPath.is_deleted.is_(False),
            )
            .order_by(
                LearningPath.generated_at.desc(),
                LearningPath.create_time.desc(),
                LearningPath.id.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_student_learning(
        self,
        class_id: str,
        student_id: str,
        current_user: User,
    ) -> dict:
        """Aggregate the latest real learning evidence for an enrolled student."""
        await self.verify_teacher(class_id, current_user)
        student = await self._require_enrolled_student(class_id, student_id)

        evaluation = await self._latest_evaluation(student_id, class_id)
        evaluation_summary = None
        if evaluation is not None:
            evaluation_summary = {
                "overall_score": _overall_score(evaluation.mastery_table),
                "generated_at": (
                    evaluation.generated_at.isoformat()
                    if evaluation.generated_at
                    else None
                ),
                "summary_text": evaluation.summary_text or None,
            }

        profile = await self._latest_profile(student_id, class_id)
        profile_summary = None
        if profile is not None:
            coordinates = (
                profile.knowledge_coordinates
                if isinstance(profile.knowledge_coordinates, list)
                else []
            )
            profile_summary = {
                "knowledge_mastered": sum(
                    row.get("status") == "mastered"
                    for row in coordinates
                    if isinstance(row, dict)
                ),
                "knowledge_weak": sum(
                    row.get("status") == "weak"
                    for row in coordinates
                    if isinstance(row, dict)
                ),
                "modal_preference": _ranked_modal_preferences(
                    profile.modal_preference
                ),
                "knowledge_coordinates": coordinates,
            }

        learning_path = await self._latest_learning_path(student_id, class_id)
        path_progress = None
        if learning_path is not None and isinstance(learning_path.nodes, list):
            path_progress = {
                "current_node": learning_path.current_node_name,
                "completed_nodes": sum(
                    isinstance(node, dict) and node.get("status") == "completed"
                    for node in learning_path.nodes
                ),
                "total_nodes": len(learning_path.nodes),
            }

        mastery_result = await self.db.execute(
            select(
                QuizQuestion.knowledge_point,
                func.count(QuizAnswer.id).label("total"),
                func.sum(
                    case((QuizAnswer.is_correct.is_(True), 1), else_=0)
                ).label("correct"),
            )
            .join(QuizAnswer, QuizAnswer.question_id == QuizQuestion.id)
            .join(QuizSession, QuizSession.id == QuizAnswer.quiz_id)
            .where(
                QuizSession.user_id == student_id,
                QuizSession.course_id == class_id,
                QuizSession.is_deleted.is_(False),
                QuizAnswer.is_deleted.is_(False),
                QuizQuestion.is_deleted.is_(False),
                QuizQuestion.knowledge_point != "",
            )
            .group_by(QuizQuestion.knowledge_point)
        )
        mastery_breakdown = []
        for row in mastery_result:
            total = row.total or 0
            correct = row.correct or 0
            mastery_breakdown.append(
                {
                    "knowledge_point": row.knowledge_point,
                    "accuracy": round(correct / total * 100, 1) if total else 0,
                }
            )

        quiz_result = await self.db.execute(
            select(
                func.count(QuizSession.id).label("total_attempts"),
                func.avg(QuizSession.score).label("avg_score"),
                func.avg(QuizSession.time_spent).label("avg_time"),
            ).where(
                QuizSession.user_id == student_id,
                QuizSession.course_id == class_id,
                QuizSession.is_deleted.is_(False),
            )
        )
        quiz_row = quiz_result.one()
        quiz_stats = None
        if quiz_row.total_attempts:
            quiz_stats = {
                "total_attempts": quiz_row.total_attempts,
                "avg_score": round(float(quiz_row.avg_score), 1),
                "avg_time_spent": int(float(quiz_row.avg_time)),
                "mastery_breakdown": mastery_breakdown,
            }

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
                QuizSession.user_id == student_id,
                QuizSession.course_id == class_id,
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
        weak_points = []
        for row in weak_result:
            attempts = row.total_attempts or 0
            errors = row.error_count or 0
            weak_points.append(
                {
                    "knowledge_point": row.knowledge_point,
                    "error_count": errors,
                    "total_attempts": attempts,
                    "error_rate": round(errors / attempts, 2) if attempts else 0,
                }
            )

        recent_result = await self.db.execute(
            select(QuizSession)
            .where(
                QuizSession.user_id == student_id,
                QuizSession.course_id == class_id,
                QuizSession.is_deleted.is_(False),
            )
            .order_by(QuizSession.create_time.desc(), QuizSession.id.desc())
            .limit(5)
        )
        recent_activity = [
            {
                "quiz_id": session.id,
                "chapter": session.chapter or "",
                "score": session.score,
                "correct_count": session.correct_count,
                "total_count": session.total_count,
                "time_spent": session.time_spent,
                "created_at": (
                    session.create_time.isoformat() if session.create_time else ""
                ),
            }
            for session in recent_result.scalars().all()
        ]

        return {
            "student": {
                "id": student.id,
                "real_name": student.real_name,
                "student_id": student.student_id,
            },
            "evaluation_summary": evaluation_summary,
            "profile_summary": profile_summary,
            "path_progress": path_progress,
            "quiz_stats": quiz_stats,
            "weak_points": weak_points,
            "recent_activity": recent_activity,
        }

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
