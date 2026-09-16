"""SQLAlchemy ORM models: users, sessions, API keys, jobs, and the audit log."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


ROLES = ("admin", "supervisor", "operator", "viewer", "api_client")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="operator")
    state: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    district: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    jobs: Mapped[list["Job"]] = relationship(back_populates="owner", foreign_keys="Job.owner_id")
    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="default")
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    hashed_key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="api_keys")


class Job(Base):
    """One document-processing job. `id` matches the linecut JOBS/{id} folder on disk."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    owner_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"), nullable=True)

    source_filename: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    lang: Mapped[str] = mapped_column(String(32), nullable=False, default="en")
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False, default="auto")
    state: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    district: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    tehsil: Mapped[str] = mapped_column(String(128), nullable=False, default="")

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="processing")
    # processing | complete | failed | needs_review | verified | rejected

    lines_found: Mapped[int] = mapped_column(Integer, default=0)
    tables_found: Mapped[int] = mapped_column(Integer, default=0)
    stamps_found: Mapped[int] = mapped_column(Integer, default=0)
    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    low_confidence_count: Mapped[int] = mapped_column(Integer, default=0)
    corrections_count: Mapped[int] = mapped_column(Integer, default=0)

    validation_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    review_required: Mapped[bool] = mapped_column(Boolean, default=False)

    # Mercury's one-time "is this actually a land record" verdict, computed during
    # /segment (see llm_refiner.refine_land_record_with_llm). None = not classified
    # (llm_refine was off, or no tables were found to classify from).
    is_land_record: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=None)
    classification_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    classification_reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="")

    processing_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")

    land_record: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    validation: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    verified_by_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    owner: Mapped["User"] = relationship(back_populates="jobs", foreign_keys=[owner_id])


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    job_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("jobs.id"), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
