"""PostgreSQL-backed QuizRepository adapter for Hogwarts Trials API.

Implements the read-only QuizRepository protocol by querying relational persistence models
via SQLAlchemy 2.x and mapping them to detached, immutable domain Quiz instances.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from hogwarts_trials_api.application.quiz_repository import QuizRepository
from hogwarts_trials_api.domain.quiz import Quiz
from hogwarts_trials_api.infrastructure.models import (
    QuestionModel,
    QuizModel,
    QuizQuestionModel,
)
from hogwarts_trials_api.infrastructure.quiz_mapper import quiz_model_to_domain


class PostgresQuizRepository:
    """PostgreSQL implementation of the QuizRepository protocol."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def list_quizzes(self) -> tuple[Quiz, ...]:
        """Retrieve all quizzes in deterministic order (title ascending, quiz_id ascending).

        Eagerly loads related questions, choices, and answer keys to avoid N+1 queries.
        """
        stmt = (
            select(QuizModel)
            .options(
                selectinload(QuizModel.quiz_questions)
                .selectinload(QuizQuestionModel.question)
                .selectinload(QuestionModel.choices),
                selectinload(QuizModel.quiz_questions)
                .selectinload(QuizQuestionModel.question)
                .selectinload(QuestionModel.correct_choices),
            )
            .order_by(QuizModel.title.asc(), QuizModel.quiz_id.asc())
        )

        with self._session_factory() as session:
            results = session.scalars(stmt).all()
            return tuple(quiz_model_to_domain(m) for m in results)

    def get_quiz(self, quiz_id: UUID) -> Quiz | None:
        """Retrieve a specific quiz by its unique identifier, or None if not found."""
        stmt = (
            select(QuizModel)
            .where(QuizModel.quiz_id == quiz_id)
            .options(
                selectinload(QuizModel.quiz_questions)
                .selectinload(QuizQuestionModel.question)
                .selectinload(QuestionModel.choices),
                selectinload(QuizModel.quiz_questions)
                .selectinload(QuizQuestionModel.question)
                .selectinload(QuestionModel.correct_choices),
            )
        )

        with self._session_factory() as session:
            model = session.scalars(stmt).first()
            if model is None:
                return None
            return quiz_model_to_domain(model)


# Compile-time protocol conformance check
_: QuizRepository = PostgresQuizRepository(sessionmaker())  # type: ignore[arg-type]

