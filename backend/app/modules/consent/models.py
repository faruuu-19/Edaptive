"""Consent decisions, one row per decision. No audio or camera input is implemented."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ConsentDecision(Base):
    __tablename__ = "consent"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_profile.id", ondelete="CASCADE")
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("household.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(Text)
    granted: Mapped[bool] = mapped_column(Boolean)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_by: Mapped[str] = mapped_column(Text, default="parent")
    policy_version: Mapped[str] = mapped_column(Text, default="no-input-v1")

    __table_args__ = (
        CheckConstraint("kind IN ('camera', 'microphone')", name="consent_kind"),
        Index("consent_student_kind_latest", "student_id", "kind", "id"),
    )
