"""Separate attempt ownership persistence, without backfilling legacy owners.

Revision ID: 0003
Revises: 0002
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quiz_attempt_ownerships",
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("attempt_id", name="pk_quiz_attempt_ownerships"),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["quiz_attempts.attempt_id"],
            name="fk_quiz_attempt_ownerships_attempt_id_quiz_attempts",
            ondelete="CASCADE",
        ),
    )


def downgrade() -> None:
    op.drop_table("quiz_attempt_ownerships")
