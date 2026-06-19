"""Read model for authorized class-level teaching insights."""

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import CourseEnrollment
from app.models.others import LearningPath
from app.models.quiz import QuizAnswer, QuizQuestion, QuizSession
from app.models.user import User


class ClassInsightsQuery:
    """Build class insights inside an already-authorized course scope."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute(self, class_id: str) -> dict:
        """Aggregate active enrollment, quiz, weak-point and path evidence."""
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
