"""Let a parent allow the lesson alarm sound as a per-child permission."""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("consent_kind", "consent", type_="check")
    op.create_check_constraint("consent_kind", "consent", "kind IN ('camera', 'microphone', 'lesson_alarm')")


def downgrade():
    op.execute("DELETE FROM consent WHERE kind = 'lesson_alarm'")
    op.drop_constraint("consent_kind", "consent", type_="check")
    op.create_check_constraint("consent_kind", "consent", "kind IN ('camera', 'microphone')")
