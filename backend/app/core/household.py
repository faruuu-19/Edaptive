"""The top of the identity hierarchy: household -> parent -> students.

Shared tables (owned by Track C). Any module may reference a household or student profile;
only the profiles module changes profiles, and only the auth module handles credentials.
Children's data is kept minimal: a first name or nickname, a grade and a picker icon.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, Text, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base


class Household(Base):
    __tablename__ = "household"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudentProfile(Base):
    __tablename__ = "student_profile"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("household.id", ondelete="RESTRICT")
    )
    display_name: Mapped[str] = mapped_column(Text)
    grade: Mapped[int] = mapped_column(SmallInteger)
    avatar_key: Mapped[str] = mapped_column(Text, server_default="default")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("char_length(display_name) BETWEEN 1 AND 30", name="display_name_length"),
        CheckConstraint("grade BETWEEN 1 AND 5", name="grade_range"),
    )


def get_household(db: Session) -> Household | None:
    """Edaptive runs on one family's machine, so there is at most one household."""
    return db.scalars(select(Household).limit(1)).first()


def get_active_profile(db: Session, household_id: uuid.UUID, student_id: uuid.UUID) -> StudentProfile | None:
    return db.scalars(
        select(StudentProfile).where(
            StudentProfile.id == student_id,
            StudentProfile.household_id == household_id,
            StudentProfile.archived_at.is_(None),
        )
    ).first()
