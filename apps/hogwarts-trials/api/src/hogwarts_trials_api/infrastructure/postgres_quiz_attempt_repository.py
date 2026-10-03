"""PostgreSQL-backed QuizAttemptRepository adapter for Hogwarts Trials API.

Implements the QuizAttemptRepository protocol by persisting and querying relational
attempt models via SQLAlchemy 2.x and mapping them to detached, immutable domain QuizAttempt instances.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from hogwarts_trials_api.application.quiz_attempt_repository import (
    QuizAttemptRepository,
)
from hogwarts_trials_api.domain.attempt import (
    AttemptStatus,
    QuizAttempt,
    QuizAttemptAlreadyCompletedError,
    QuizAttemptError,
    QuizAttemptNotFoundError,
)
from hogwarts_trials_api.domain.grading import (
    QuestionResult,
    QuestionResultStatus,
    QuizResult,
)
from hogwarts_trials_api.infrastructure.models import (
    QuestionModel,
    QuizAttemptModel,
    QuizAttemptQuestionResultModel,
    QuizAttemptSelectedChoiceModel,
    QuizModel,
    QuizQuestionModel,
)


class PostgresQuizAttemptRepository:
    """PostgreSQL implementation of the QuizAttemptRepository protocol."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def create_attempt(self, attempt: QuizAttempt) -> QuizAttempt:
        """Persist a newly started in-progress attempt.

        Raises:
            QuizAttemptError: If an attempt with this ID already exists.
        """
        with self._session_factory() as session:
            with session.begin():
                existing = session.get(QuizAttemptModel, attempt.attempt_id)
                if existing is not None:
                    raise QuizAttemptError(
                        f"Attempt with ID {attempt.attempt_id} already exists"
                    )
                model = QuizAttemptModel(
                    attempt_id=attempt.attempt_id,
                    quiz_id=attempt.quiz_id,
                    status=attempt.status.value,
                )
                session.add(model)
        return attempt

    def get_attempt(self, attempt_id: UUID) -> QuizAttempt | None:
        """Retrieve an attempt by its ID, reconstructing its evaluated snapshot if completed."""
        stmt = (
            select(QuizAttemptModel)
            .where(QuizAttemptModel.attempt_id == attempt_id)
            .options(
                selectinload(QuizAttemptModel.question_results),
                selectinload(QuizAttemptModel.selected_choices),
                selectinload(QuizAttemptModel.quiz)
                .selectinload(QuizModel.quiz_questions)
                .selectinload(QuizQuestionModel.question)
                .selectinload(QuestionModel.correct_choices),
            )
        )

        with self._session_factory() as session:
            model = session.scalars(stmt).first()
            if model is None:
                return None

            if model.status == AttemptStatus.in_progress.value:
                return QuizAttempt(
                    attempt_id=model.attempt_id,
                    quiz_id=model.quiz_id,
                    status=AttemptStatus.in_progress,
                    result=None,
                )

            # Reconstruct snapshot from persisted result tables
            selected_map: dict[UUID, list[UUID]] = {}
            for sc in model.selected_choices:
                selected_map.setdefault(sc.question_id, []).append(sc.choice_id)

            qr_map: dict[UUID, QuizAttemptQuestionResultModel] = {
                qr.question_id: qr for qr in model.question_results
            }

            question_results: list[QuestionResult] = []
            sorted_quiz_questions = sorted(
                model.quiz.quiz_questions, key=lambda qq: qq.position
            )
            for qq in sorted_quiz_questions:
                q = qq.question
                persisted_qr = qr_map.get(q.question_id)
                if persisted_qr is None:
                    raise QuizAttemptError(
                        f"Missing question result snapshot for question {q.question_id} "
                        f"in completed attempt {attempt_id}"
                    )

                selected_ids = tuple(selected_map.get(q.question_id, ()))
                correct_ids = tuple(cc.choice_id for cc in q.correct_choices)

                question_results.append(
                    QuestionResult(
                        question_id=q.question_id,
                        status=QuestionResultStatus(persisted_qr.status),
                        selected_choice_ids=selected_ids,
                        correct_choice_ids=correct_ids,
                        awarded_points=persisted_qr.awarded_points,
                        max_points=persisted_qr.max_points,
                    )
                )

            qr_tuple = tuple(question_results)
            quiz_result = QuizResult(
                quiz_id=model.quiz_id,
                question_results=qr_tuple,
                total_points=sum(r.awarded_points for r in qr_tuple),
                max_points=sum(r.max_points for r in qr_tuple),
                correct_count=sum(
                    1 for r in qr_tuple if r.status == QuestionResultStatus.correct
                ),
                incorrect_count=sum(
                    1 for r in qr_tuple if r.status == QuestionResultStatus.incorrect
                ),
                unanswered_count=sum(
                    1 for r in qr_tuple if r.status == QuestionResultStatus.unanswered
                ),
            )

            return QuizAttempt(
                attempt_id=model.attempt_id,
                quiz_id=model.quiz_id,
                status=AttemptStatus.completed,
                result=quiz_result,
            )

    def complete_attempt(self, attempt: QuizAttempt) -> QuizAttempt:
        """Atomically persist attempt completion and question result snapshots.

        Locks the attempt row during evaluation to prevent concurrent double-completion.

        Raises:
            QuizAttemptNotFoundError: If the attempt does not exist.
            QuizAttemptAlreadyCompletedError: If the attempt has already been completed.
            QuizAttemptError: If the attempt payload is not in completed state or lacks a result.
        """
        if attempt.status != AttemptStatus.completed or attempt.result is None:
            raise QuizAttemptError(
                "Cannot complete attempt without completed status and an evaluated result"
            )

        with self._session_factory() as session:
            with session.begin():
                stmt = (
                    select(QuizAttemptModel)
                    .where(QuizAttemptModel.attempt_id == attempt.attempt_id)
                    .with_for_update()
                )
                attempt_model = session.scalars(stmt).first()
                if attempt_model is None:
                    raise QuizAttemptNotFoundError(
                        f"Attempt with ID {attempt.attempt_id} not found"
                    )
                if attempt_model.status == AttemptStatus.completed.value:
                    raise QuizAttemptAlreadyCompletedError(
                        f"Attempt with ID {attempt.attempt_id} is already completed"
                    )

                # Persist evaluated question outcomes snapshot
                for qr in attempt.result.question_results:
                    session.add(
                        QuizAttemptQuestionResultModel(
                            attempt_id=attempt.attempt_id,
                            question_id=qr.question_id,
                            status=qr.status.value,
                            awarded_points=qr.awarded_points,
                            max_points=qr.max_points,
                        )
                    )
                    for choice_id in qr.selected_choice_ids:
                        session.add(
                            QuizAttemptSelectedChoiceModel(
                                attempt_id=attempt.attempt_id,
                                question_id=qr.question_id,
                                choice_id=choice_id,
                            )
                        )

                attempt_model.status = AttemptStatus.completed.value

        return attempt


# Compile-time protocol conformance check
_: QuizAttemptRepository = PostgresQuizAttemptRepository(sessionmaker())  # type: ignore[arg-type]
