from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class InterviewSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "interview_sessions"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    resume_id: Mapped[UUID | None] = mapped_column(ForeignKey("resumes.id", ondelete="SET NULL"))
    role: Mapped[str] = mapped_column(String(160), nullable=False)
    job_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    interview_type: Mapped[str] = mapped_column(String(30), nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    turns: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    elapsed_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    running_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    model: Mapped[str] = mapped_column(String(120), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('active', 'paused', 'completed')", name="ck_interview_status"),
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_interview_difficulty"),
        CheckConstraint("question_count BETWEEN 1 AND 20", name="ck_interview_count"),
        CheckConstraint("duration_minutes BETWEEN 5 AND 90", name="ck_interview_duration"),
        CheckConstraint("elapsed_seconds >= 0", name="ck_interview_elapsed"),
        Index("ix_interview_user_created", "user_id", "created_at"),
    )
