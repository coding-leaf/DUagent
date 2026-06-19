"""Read model for an authorized student's teaching report."""

import math

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

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


class StudentReportQuery:
    """Build a student learning report from already-authorized scope."""

    def __init__(self, db: AsyncSession):
        self.db = db

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

    async def execute(self, class_id: str, student: User) -> dict:
        """Aggregate the latest real learning evidence for one student."""
        student_id = student.id
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
