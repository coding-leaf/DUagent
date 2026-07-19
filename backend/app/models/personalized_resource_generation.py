import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _generation_id() -> str:
    return uuid.uuid4().hex[:16]


class PersonalizedResourceGeneration(Base):
    __tablename__ = "personalized_resource_generations"
    __table_args__ = (
        Index("idx_prg_user_course", "user_id", "course_id", "is_deleted"),
        Index("idx_prg_status", "status", "is_deleted"),
        Index("uk_prg_idempotency_key", "idempotency_key", unique=True),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_generation_id)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=False)
    conversation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_run_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="drafted")
    draft: Mapped[dict] = mapped_column(JSON, nullable=False)
    validation_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    review_decision: Mapped[str | None] = mapped_column(String(30), nullable=True)
    review_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    artifact_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    delivery_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    published_resource_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("resources.id"), nullable=True
    )
    published_code_problem_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("code_problems.id"), nullable=True
    )
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    update_time: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
