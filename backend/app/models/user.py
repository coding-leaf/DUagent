import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Float, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:16]


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    real_name: Mapped[str] = mapped_column(String(50), default="")
    student_id: Mapped[str] = mapped_column(String(30), default="")
    role: Mapped[str] = mapped_column(String(20), default="student")  # student / teacher / admin
    major: Mapped[str] = mapped_column(String(100), default="")
    grade: Mapped[str] = mapped_column(String(20), default="")
    guidance_level: Mapped[str] = mapped_column(String(5), default="L2")  # L1 / L2 / L3
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    enrollments = relationship("CourseEnrollment", back_populates="student", lazy="selectin")
    taught_courses = relationship("Course", back_populates="teacher", lazy="selectin")


class RegistrationCode(Base):
    __tablename__ = "registration_codes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_by: Mapped[str] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
