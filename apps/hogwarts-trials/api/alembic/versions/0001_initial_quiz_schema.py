"""Initial relational persistence schema for Hogwarts Trials quiz domain.

Revision ID: 0001
Revises: None
Create Date: 2026-09-06 00:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. quizzes table
    op.create_table(
        "quizzes",
        sa.Column("quiz_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("quiz_id", name="pk_quizzes"),
    )

    # 2. questions table
    op.create_table(
        "questions",
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(length=32), nullable=False),
        sa.Column("difficulty", sa.String(length=32), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("source_tier", sa.String(length=32), nullable=False),
        sa.Column("source_reference", sa.String(length=255), nullable=False),
        sa.Column("chapter_reference", sa.String(length=255), nullable=True),
        sa.Column("curation_status", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "question_type IN ('single_choice', 'multiple_choice')",
            name="ck_questions_question_type",
        ),
        sa.CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="ck_questions_difficulty",
        ),
        sa.CheckConstraint(
            "source_tier IN ('book_canon', 'screen_adaptation', 'official_expanded', 'synthetic')",
            name="ck_questions_source_tier",
        ),
        sa.CheckConstraint(
            "curation_status IN ('draft', 'reviewed', 'approved')",
            name="ck_questions_curation_status",
        ),
        sa.PrimaryKeyConstraint("question_id", name="pk_questions"),
    )

    # 3. quiz_questions membership table
    op.create_table(
        "quiz_questions",
        sa.Column("quiz_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["quiz_id"],
            ["quizzes.quiz_id"],
            name="fk_quiz_questions_quiz_id_quizzes",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.question_id"],
            name="fk_quiz_questions_question_id_questions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("quiz_id", "question_id", name="pk_quiz_questions"),
        sa.UniqueConstraint("quiz_id", "position", name="uq_quiz_questions_quiz_position"),
    )
    op.create_index(
        "ix_quiz_questions_quiz_position",
        "quiz_questions",
        ["quiz_id", "position"],
        unique=False,
    )

    # 4. question_choices table
    op.create_table(
        "question_choices",
        sa.Column("choice_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.question_id"],
            name="fk_question_choices_question_id_questions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("choice_id", name="pk_question_choices"),
        sa.UniqueConstraint("question_id", "position", name="uq_question_choices_question_position"),
    )
    op.create_index(
        "ix_question_choices_question_id",
        "question_choices",
        ["question_id"],
        unique=False,
    )
    op.create_index(
        "ix_question_choices_question_position",
        "question_choices",
        ["question_id", "position"],
        unique=False,
    )

    # 5. question_correct_choices table (server answer key)
    op.create_table(
        "question_correct_choices",
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("choice_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.question_id"],
            name="fk_question_correct_choices_question_id_questions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["choice_id"],
            ["question_choices.choice_id"],
            name="fk_question_correct_choices_choice_id_question_choices",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("question_id", "choice_id", name="pk_question_correct_choices"),
    )
    op.create_index(
        "ix_question_correct_choices_choice",
        "question_correct_choices",
        ["choice_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_question_correct_choices_choice", table_name="question_correct_choices")
    op.drop_table("question_correct_choices")

    op.drop_index("ix_question_choices_question_position", table_name="question_choices")
    op.drop_index("ix_question_choices_question_id", table_name="question_choices")
    op.drop_table("question_choices")

    op.drop_index("ix_quiz_questions_quiz_position", table_name="quiz_questions")
    op.drop_table("quiz_questions")

    op.drop_table("questions")
    op.drop_table("quizzes")
