"""SQLAlchemy 2.x relational persistence models for Hogwarts Trials quiz domain.

Defines the database schema and ORM models for quizzes, questions, choices,
membership, and answer keys.

NOTE: Domain models (Pydantic) remain separate from persistence models (SQLAlchemy).
"""

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative class for all Hogwarts Trials persistence models."""


class QuizModel(Base):
    """Relational table representing a quiz entity."""

    __tablename__ = "quizzes"

    quiz_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Ordered quiz question associations
    quiz_questions: Mapped[list["QuizQuestionModel"]] = relationship(
        "QuizQuestionModel",
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="QuizQuestionModel.position",
    )


class QuestionModel(Base):
    """Relational table representing a question entity."""

    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint(
            "question_type IN ('single_choice', 'multiple_choice')",
            name="ck_questions_question_type",
        ),
        CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="ck_questions_difficulty",
        ),
        CheckConstraint(
            "source_tier IN ('book_canon', 'screen_adaptation', 'official_expanded', 'synthetic')",
            name="ck_questions_source_tier",
        ),
        CheckConstraint(
            "curation_status IN ('draft', 'reviewed', 'approved')",
            name="ck_questions_curation_status",
        ),
    )

    question_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(32), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(32), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_tier: Mapped[str] = mapped_column(String(32), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    chapter_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    curation_status: Mapped[str] = mapped_column(String(32), nullable=False)

    # Ordered response choices
    choices: Mapped[list["QuestionChoiceModel"]] = relationship(
        "QuestionChoiceModel",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="QuestionChoiceModel.position",
    )

    # Correct choice mappings (server-side answer key)
    correct_choices: Mapped[list["QuestionCorrectChoiceModel"]] = relationship(
        "QuestionCorrectChoiceModel",
        back_populates="question",
        cascade="all, delete-orphan",
    )

    # Quiz memberships
    quiz_memberships: Mapped[list["QuizQuestionModel"]] = relationship(
        "QuizQuestionModel",
        back_populates="question",
    )


class QuizQuestionModel(Base):
    """Relational association mapping a question to a quiz with a contiguous 1-based position."""

    __tablename__ = "quiz_questions"
    __table_args__ = (
        UniqueConstraint("quiz_id", "position", name="uq_quiz_questions_quiz_position"),
        Index("ix_quiz_questions_quiz_position", "quiz_id", "position"),
    )

    quiz_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("quizzes.quiz_id", ondelete="CASCADE"),
        primary_key=True,
    )
    question_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("questions.question_id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    quiz: Mapped["QuizModel"] = relationship("QuizModel", back_populates="quiz_questions")
    question: Mapped["QuestionModel"] = relationship("QuestionModel", back_populates="quiz_memberships")


class QuestionChoiceModel(Base):
    """Relational table representing an individual choice for a question."""

    __tablename__ = "question_choices"
    __table_args__ = (
        UniqueConstraint("question_id", "position", name="uq_question_choices_question_position"),
        Index("ix_question_choices_question_position", "question_id", "position"),
    )

    choice_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    question_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("questions.question_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    question: Mapped["QuestionModel"] = relationship("QuestionModel", back_populates="choices")


class QuestionCorrectChoiceModel(Base):
    """Relational table mapping a question to its correct choice IDs (answer key)."""

    __tablename__ = "question_correct_choices"
    __table_args__ = (
        Index("ix_question_correct_choices_choice", "choice_id"),
    )

    question_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("questions.question_id", ondelete="CASCADE"),
        primary_key=True,
    )
    choice_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("question_choices.choice_id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Relationships
    question: Mapped["QuestionModel"] = relationship("QuestionModel", back_populates="correct_choices")
    choice: Mapped["QuestionChoiceModel"] = relationship("QuestionChoiceModel")

