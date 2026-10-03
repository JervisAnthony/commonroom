"""Relational persistence schema for Hogwarts Trials quiz attempt lifecycle.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-08 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. quiz_attempts table
    op.create_table(
        "quiz_attempts",
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("quiz_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed')",
            name="ck_quiz_attempts_status",
        ),
        sa.ForeignKeyConstraint(
            ["quiz_id"],
            ["quizzes.quiz_id"],
            name="fk_quiz_attempts_quiz_id_quizzes",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("attempt_id", name="pk_quiz_attempts"),
    )
    op.create_index(
        "ix_quiz_attempts_quiz_id",
        "quiz_attempts",
        ["quiz_id"],
        unique=False,
    )

    # 2. quiz_attempt_question_results table
    op.create_table(
        "quiz_attempt_question_results",
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("awarded_points", sa.Integer(), nullable=False),
        sa.Column("max_points", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "status IN ('correct', 'incorrect', 'unanswered')",
            name="ck_quiz_attempt_question_results_status",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["quiz_attempts.attempt_id"],
            name="fk_quiz_attempt_question_results_attempt_id_quiz_attempts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.question_id"],
            name="fk_quiz_attempt_question_results_question_id_questions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "attempt_id",
            "question_id",
            name="pk_quiz_attempt_question_results",
        ),
    )
    op.create_index(
        "ix_quiz_attempt_question_results_question_id",
        "quiz_attempt_question_results",
        ["question_id"],
        unique=False,
    )

    # 3. quiz_attempt_selected_choices table
    op.create_table(
        "quiz_attempt_selected_choices",
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("choice_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["quiz_attempts.attempt_id"],
            name="fk_quiz_attempt_selected_choices_attempt_id_quiz_attempts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.question_id"],
            name="fk_quiz_attempt_selected_choices_question_id_questions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["choice_id"],
            ["question_choices.choice_id"],
            name="fk_quiz_attempt_selected_choices_choice_id_question_choices",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "attempt_id",
            "question_id",
            "choice_id",
            name="pk_quiz_attempt_selected_choices",
        ),
    )
    op.create_index(
        "ix_quiz_attempt_selected_choices_choice_id",
        "quiz_attempt_selected_choices",
        ["choice_id"],
        unique=False,
    )
    op.create_index(
        "ix_quiz_attempt_selected_choices_attempt_question",
        "quiz_attempt_selected_choices",
        ["attempt_id", "question_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_quiz_attempt_selected_choices_attempt_question",
        table_name="quiz_attempt_selected_choices",
    )
    op.drop_index(
        "ix_quiz_attempt_selected_choices_choice_id",
        table_name="quiz_attempt_selected_choices",
    )
    op.drop_table("quiz_attempt_selected_choices")

    op.drop_index(
        "ix_quiz_attempt_question_results_question_id",
        table_name="quiz_attempt_question_results",
    )
    op.drop_table("quiz_attempt_question_results")

    op.drop_index("ix_quiz_attempts_quiz_id", table_name="quiz_attempts")
    op.drop_table("quiz_attempts")
