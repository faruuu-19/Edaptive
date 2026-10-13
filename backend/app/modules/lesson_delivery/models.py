import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Timetable(Base):
    __tablename__ = "lesson_timetable"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_profile.id", ondelete="CASCADE")
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("household.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(Text, default="active")
    state: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index(
            "one_active_lesson_timetable", "student_id", unique=True, postgresql_where=text("status='active'")
        ),
    )
