"""Household, student profiles and auth (Track C, Mid-1).

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "household",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "student_profile",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "household_id",
            UUID(as_uuid=True),
            sa.ForeignKey("household.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("grade", sa.SmallInteger(), nullable=False),
        sa.Column("avatar_key", sa.Text(), server_default="default", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("char_length(display_name) BETWEEN 1 AND 30", name="display_name_length"),
        sa.CheckConstraint("grade BETWEEN 1 AND 5", name="grade_range"),
    )
    op.create_index(
        "ix_student_profile_active",
        "student_profile",
        ["household_id"],
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    op.create_table(
        "parent_pin",
        sa.Column(
            "household_id",
            UUID(as_uuid=True),
            sa.ForeignKey("household.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("pin_hash", sa.Text(), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "auth_session",
        sa.Column("token_hash", sa.Text(), primary_key=True),
        sa.Column(
            "household_id",
            UUID(as_uuid=True),
            sa.ForeignKey("household.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "student_id",
            UUID(as_uuid=True),
            sa.ForeignKey("student_profile.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(role = 'student' AND student_id IS NOT NULL) OR (role = 'parent')", name="role_student"
        ),
    )


def downgrade() -> None:
    op.drop_table("auth_session")
    op.drop_table("parent_pin")
    op.drop_index("ix_student_profile_active", table_name="student_profile")
    op.drop_table("student_profile")
    op.drop_table("household")
