import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, Text, func, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:16]


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    chapter: Mapped[str] = mapped_column(String(100), default="")
    knowledge_point: Mapped[str] = mapped_column(String(100), default="")
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(500), default="")
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    create_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    update_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    update_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class AsyncTask(Base):
    __tablename__ = "async_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    task_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="processing")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"), nullable=True)
    course_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("courses.id"), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    error_message: Mapped[str] = mapped_column(String(500), default="")
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    create_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    update_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    update_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=False)
    progress_table: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    mastery_table: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resource_usage_table: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    create_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    update_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    update_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=False)
    modal_preference: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    guidance_level_current: Mapped[str] = mapped_column(String(5), default="L2")
    guidance_level_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    knowledge_mastered: Mapped[int] = mapped_column(Integer, default=0)
    knowledge_weak: Mapped[int] = mapped_column(Integer, default=0)
    knowledge_coordinates: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cognitive_blindspots: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    drive_intent: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    discipline_badge: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    create_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    update_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    update_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LearningPath(Base):
    __tablename__ = "learning_paths"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=False)
    nodes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    edges: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    current_node_id: Mapped[str] = mapped_column(String(32), default="")
    current_node_name: Mapped[str] = mapped_column(String(100), default="")
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    create_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    update_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    update_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CourseKnowledgeGraph(Base):
    """课程静态知识图谱 — Backend 调用 Agent /learning-path/generate 时传入 knowledge_graph.nodes/edges。"""
    __tablename__ = "course_knowledge_graphs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    course_id: Mapped[str] = mapped_column(String(32), ForeignKey("courses.id"), nullable=False)
    nodes: Mapped[dict] = mapped_column(JSON, nullable=False)
    edges: Mapped[dict] = mapped_column(JSON, nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    create_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    update_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    update_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    agent_type: Mapped[str] = mapped_column(String(20), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(200), default="")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(10), default="success")
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    security_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    create_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    update_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    update_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str] = mapped_column(String(300), default="")
    ip_address: Mapped[str] = mapped_column(String(45), default="")
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    create_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    update_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    update_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
