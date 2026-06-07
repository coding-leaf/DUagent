import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def gen_id() -> str:
    return uuid.uuid4().hex[:16]


class CourseCatalog(Base):
    __tablename__ = "course_catalogs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    knowledge_status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    material_count: Mapped[int] = mapped_column(Integer, default=0)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    update_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    materials = relationship("CourseCatalogMaterial", back_populates="catalog", lazy="selectin")
    offerings = relationship("CourseOffering", back_populates="catalog", lazy="selectin")


class CourseCatalogMaterial(Base):
    __tablename__ = "course_catalog_materials"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    catalog_id: Mapped[str] = mapped_column(String(32), ForeignKey("course_catalogs.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    storage_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="uploaded")
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    catalog = relationship("CourseCatalog", back_populates="materials")


class CourseOffering(Base):
    __tablename__ = "course_offerings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    catalog_id: Mapped[str] = mapped_column(String(32), ForeignKey("course_catalogs.id"), nullable=False)
    teacher_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    class_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    update_time: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    catalog = relationship("CourseCatalog", back_populates="offerings")
