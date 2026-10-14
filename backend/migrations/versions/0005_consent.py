"""Store per-child parental permission decisions; no media input."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "consent",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
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
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("decided_by", sa.Text(), nullable=False),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.CheckConstraint("kind IN ('camera', 'microphone')", name="consent_kind"),
    )
    op.create_index("consent_student_kind_latest", "consent", ["student_id", "kind", "id"])


def downgrade():
    op.drop_table("consent")
