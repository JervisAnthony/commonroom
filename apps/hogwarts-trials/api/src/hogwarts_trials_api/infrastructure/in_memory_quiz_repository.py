"""In-memory synthetic quiz repository for Hogwarts Trials API.

Provides a concrete in-memory implementation of the QuizRepository protocol holding
immutable synthetic demonstration quizzes for API development, testing, and validation.

NOTE: This repository contains synthetic, generic demonstration questions only. It does
NOT represent the production Hogwarts Trials question bank and contains no franchise
trivia, canon text, or copyrighted material.
"""

from collections.abc import Sequence
from uuid import UUID

from hogwarts_trials_api.domain.quiz import (
    CurationStatus,
    Question,
    QuestionChoice,
    QuestionDifficulty,
    QuestionProvenance,
    QuestionType,
    Quiz,
    QuizQuestion,
    SourceTier,
)

# Deterministic UUID constants for the synthetic demonstration quiz
DEMO_QUIZ_ID = UUID("00000000-0000-4000-8000-000000000001")

# Question 1: Single-choice arithmetic (2 + 2 = 4)
Q1_ID = UUID("00000000-0000-4000-8000-000000000010")
Q1_C1_ID = UUID("00000000-0000-4000-8000-000000000011")
Q1_C2_ID = UUID("00000000-0000-4000-8000-000000000012")  # correct
Q1_C3_ID = UUID("00000000-0000-4000-8000-000000000013")
Q1_C4_ID = UUID("00000000-0000-4000-8000-000000000014")

# Question 2: Multiple-choice geometric shapes (quadrilaterals: Square, Rectangle)
Q2_ID = UUID("00000000-0000-4000-8000-000000000020")
Q2_C1_ID = UUID("00000000-0000-4000-8000-000000000021")  # correct (Square)
Q2_C2_ID = UUID("00000000-0000-4000-8000-000000000022")  # Triangle
Q2_C3_ID = UUID("00000000-0000-4000-8000-000000000023")  # correct (Rectangle)
Q2_C4_ID = UUID("00000000-0000-4000-8000-000000000024")  # Hexagon

# Question 3: Single-choice number classification (Prime number: 7)
Q3_ID = UUID("00000000-0000-4000-8000-000000000030")
Q3_C1_ID = UUID("00000000-0000-4000-8000-000000000031")  # 4
Q3_C2_ID = UUID("00000000-0000-4000-8000-000000000032")  # 6
Q3_C3_ID = UUID("00000000-0000-4000-8000-000000000033")  # correct (7)
Q3_C4_ID = UUID("00000000-0000-4000-8000-000000000034")  # 9

_PROVENANCE = QuestionProvenance(
    source_tier=SourceTier.synthetic,
    source_reference="synthetic-api-fixture",
    chapter_reference=None,
    curation_status=CurationStatus.approved,
)

_QUESTION_1 = Question(
    question_id=Q1_ID,
    prompt="What is the result of 2 + 2?",
    question_type=QuestionType.single_choice,
    difficulty=QuestionDifficulty.easy,
    choices=(
        QuestionChoice(choice_id=Q1_C1_ID, text="3"),
        QuestionChoice(choice_id=Q1_C2_ID, text="4"),
        QuestionChoice(choice_id=Q1_C3_ID, text="5"),
        QuestionChoice(choice_id=Q1_C4_ID, text="6"),
    ),
    correct_choice_ids=(Q1_C2_ID,),
    provenance=_PROVENANCE,
    explanation="Basic arithmetic: two plus two equals four.",
)

_QUESTION_2 = Question(
    question_id=Q2_ID,
    prompt="Which of the following shapes are quadrilaterals? (Select all that apply)",
    question_type=QuestionType.multiple_choice,
    difficulty=QuestionDifficulty.medium,
    choices=(
        QuestionChoice(choice_id=Q2_C1_ID, text="Square"),
        QuestionChoice(choice_id=Q2_C2_ID, text="Triangle"),
        QuestionChoice(choice_id=Q2_C3_ID, text="Rectangle"),
        QuestionChoice(choice_id=Q2_C4_ID, text="Hexagon"),
    ),
    correct_choice_ids=(Q2_C1_ID, Q2_C3_ID),
    provenance=_PROVENANCE,
    explanation="A quadrilateral is a polygon with exactly four sides (Square and Rectangle).",
)

_QUESTION_3 = Question(
    question_id=Q3_ID,
    prompt="Which of the following numbers is a prime number?",
    question_type=QuestionType.single_choice,
    difficulty=QuestionDifficulty.easy,
    choices=(
        QuestionChoice(choice_id=Q3_C1_ID, text="4"),
        QuestionChoice(choice_id=Q3_C2_ID, text="6"),
        QuestionChoice(choice_id=Q3_C3_ID, text="7"),
        QuestionChoice(choice_id=Q3_C4_ID, text="9"),
    ),
    correct_choice_ids=(Q3_C3_ID,),
    provenance=_PROVENANCE,
    explanation="Seven is only divisible by 1 and itself, making it a prime number.",
)

_DEMO_QUIZ = Quiz(
    quiz_id=DEMO_QUIZ_ID,
    title="Synthetic Demonstration Quiz",
    description="A demonstration quiz featuring basic arithmetic, shapes, and prime numbers.",
    questions=(
        QuizQuestion(position=1, question=_QUESTION_1),
        QuizQuestion(position=2, question=_QUESTION_2),
        QuizQuestion(position=3, question=_QUESTION_3),
    ),
)


class InMemoryQuizRepository:
    """In-memory quiz repository holding immutable synthetic demonstration quizzes."""

    def __init__(self, quizzes: Sequence[Quiz] | None = None) -> None:
        if quizzes is None:
            self._quizzes: tuple[Quiz, ...] = (_DEMO_QUIZ,)
        else:
            self._quizzes = tuple(quizzes)
        self._by_id: dict[UUID, Quiz] = {quiz.quiz_id: quiz for quiz in self._quizzes}

    def list_quizzes(self) -> tuple[Quiz, ...]:
        """Return all available quizzes in deterministic catalog order."""
        return self._quizzes

    def get_quiz(self, quiz_id: UUID) -> Quiz | None:
        """Retrieve a quiz by its unique identifier, or None if not found."""
        return self._by_id.get(quiz_id)
