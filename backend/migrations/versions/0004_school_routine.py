"""Persist the parent's daily start time; scheduling choices belong to the system."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "lesson_school_routine",
        sa.Column(
            "student_id",
            UUID(as_uuid=True),
            sa.ForeignKey("student_profile.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "household_id",
            UUID(as_uuid=True),
            sa.ForeignKey("household.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("start_time", sa.Text(), nullable=False),
        sa.Column("last_school_date", sa.Date()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("start_time ~ '^([01][0-9]|2[0-3]):[0-5][0-9]$'", name="school_start_time_format"),
    )


def downgrade():
    op.drop_table("lesson_school_routine")
