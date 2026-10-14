"""Persist curriculum delivery progress separately from assessment mastery."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "lesson_learning_progress",
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
        sa.Column("state", JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("lesson_learning_progress")
