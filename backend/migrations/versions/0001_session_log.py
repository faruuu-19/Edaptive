"""Session log: the append-only event table every module reads and writes.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event",
        sa.Column("seq", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_event_session_seq", "event", ["session_id", "seq"])
    op.create_index("ix_event_student_seq", "event", ["student_id", "seq"])
    op.create_index("ix_event_type_seq", "event", ["event_type", "seq"])
    # Append-only at the database level, so no bug in any module can rewrite history.
    op.execute(
        """
        CREATE FUNCTION event_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'session log is append-only (% blocked)', TG_OP;
        END $$;
        CREATE TRIGGER event_no_update_delete BEFORE UPDATE OR DELETE ON event
            FOR EACH ROW EXECUTE FUNCTION event_append_only();
        CREATE TRIGGER event_no_truncate BEFORE TRUNCATE ON event
            FOR EACH STATEMENT EXECUTE FUNCTION event_append_only();
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE event; DROP FUNCTION event_append_only();")
