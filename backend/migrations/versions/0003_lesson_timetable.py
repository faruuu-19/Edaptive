"""Persist real lesson timetable and delivery state. Local implementation for team review."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "lesson_timetable",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id",
            UUID(as_uuid=True),
            sa.ForeignKey("student_profile.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "household_id",
            UUID(as_uuid=True),
            sa.ForeignKey("household.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("state", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "one_active_lesson_timetable",
        "lesson_timetable",
        ["student_id"],
        unique=True,
        postgresql_where=sa.text("status='active'"),
    )


def downgrade():
    op.drop_table("lesson_timetable")
