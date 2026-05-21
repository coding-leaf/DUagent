import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:16]


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)  # document / mindmap / exercise / reading / code / slides
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    chapter: Mapped[str] = mapped_column(String(100), default="")
    url: Mapped[str] = mapped_column(String(500), default="")
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class AsyncTask(Base):
    __tablename__ = "async_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    task_type: Mapped[str] = mapped_column(String(30), nullable=False)  # evaluation / profile / learning_path / resource / memory_compress
    status: Mapped[str] = mapped_column(String(20), default="processing")  # processing / completed / failed
    progress: Mapped[int] = mapped_column(Integer, default=0)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=True)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=True)
    result: Mapped[dict] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=False)
    progress_table: Mapped[dict] = mapped_column(JSON, default=dict)
    mastery_table: Mapped[dict] = mapped_column(JSON, default=dict)
    resource_usage_table: Mapped[dict] = mapped_column(JSON, default=dict)
    summary_text: Mapped[str] = mapped_column(Text, default="")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=False)
    modal_preference: Mapped[dict] = mapped_column(JSON, default=dict)
    guidance_level_current: Mapped[str] = mapped_column(String(5), default="L2")
    guidance_level_updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    knowledge_coordinates: Mapped[list] = mapped_column(JSON, default=list)
    cognitive_blindspots: Mapped[list] = mapped_column(JSON, default=list)
    drive_intent: Mapped[dict] = mapped_column(JSON, default=dict)
    discipline_badge: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class LearningPath(Base):
    __tablename__ = "learning_paths"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=False)
    nodes: Mapped[list] = mapped_column(JSON, default=list)
    edges: Mapped[list] = mapped_column(JSON, default=list)
    current_node_id: Mapped[str] = mapped_column(String(32), default="")
    current_node_name: Mapped[str] = mapped_column(String(100), default="")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    agent_type: Mapped[str] = mapped_column(String(20), nullable=False)  # tutoring / evaluation / profile / resource
    endpoint: Mapped[str] = mapped_column(String(200), default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(10), default="success")  # success / error
    error_message: Mapped[str] = mapped_column(String(500), default="")
    security_blocked: Mapped[bool] = mapped_column(default=False)


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)  # login / logout / operation / system_error / security
    user_id: Mapped[str] = mapped_column(String(32), nullable=True)
    description: Mapped[str] = mapped_column(String(300), default="")
    ip_address: Mapped[str] = mapped_column(String(45), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
