import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:16]


class CodeProblem(Base):
    __tablename__ = "code_problems"
    __table_args__ = (
        Index("idx_code_problems_owner_course", "owner_user_id", "course_id", "is_deleted"),
        Index("idx_code_problems_conversation", "conversation_id", "is_deleted"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"), nullable=True)
    origin: Mapped[str] = mapped_column(String(30), nullable=False, default="ai_chat")
    conversation_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("conversations.id"), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    chapter: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    knowledge_point: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    difficulty: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    starter_code: Mapped[str] = mapped_column(Text, nullable=False)
    reference_solution: Mapped[str] = mapped_column(Text, nullable=False)
    validation_report: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="validated")
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    create_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    update_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    update_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CodeProblemTestCase(Base):
    __tablename__ = "code_problem_test_cases"
    __table_args__ = (
        Index("idx_code_problem_cases_problem_order", "problem_id", "ordinal"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    problem_id: Mapped[str] = mapped_column(String(32), ForeignKey("code_problems.id"), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    stdin: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
