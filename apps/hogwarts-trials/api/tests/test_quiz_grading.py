"""Deterministic grading engine tests for Hogwarts Trials.

Verifies pure-domain evaluation rules, base scoring (1 point/question),
exact-match correctness, canonical ordering, error cases, immutability,
and aggregation invariants.
"""

import copy
from uuid import UUID
import pytest
from pydantic import ValidationError

from hogwarts_trials_api.domain import (
    AnswerSubmission,
    CurationStatus,
    Question,
    QuestionChoice,
    QuestionDifficulty,
    QuestionProvenance,
    QuestionResult,
    QuestionResultStatus,
    QuestionType,
    Quiz,
    QuizGradingError,
    QuizQuestion,
    QuizResult,
    SourceTier,
    grade_question,
    grade_quiz,
)

# Fixed deterministic UUID fixtures
ID_Q1 = UUID("00000000-0000-0000-0000-000000000001")
ID_Q2 = UUID("00000000-0000-0000-0000-000000000002")
ID_Q3 = UUID("00000000-0000-0000-0000-000000000003")
ID_C1 = UUID("00000000-0000-0000-0000-000000000011")
ID_C2 = UUID("00000000-0000-0000-0000-000000000012")
ID_C3 = UUID("00000000-0000-0000-0000-000000000013")
ID_C4 = UUID("00000000-0000-0000-0000-000000000014")
ID_UNKNOWN_C = UUID("00000000-0000-0000-0000-000000000099")
ID_UNKNOWN_Q = UUID("00000000-0000-0000-0000-000000000098")
ID_QUIZ = UUID("00000000-0000-0000-0000-000000000101")


def make_provenance() -> QuestionProvenance:
    """Helper to create synthetic question provenance."""
    return QuestionProvenance(
        source_tier=SourceTier.book_canon,
        source_reference="synthetic-volume-1",
        chapter_reference="chapter-1",
        curation_status=CurationStatus.approved,
    )


def make_single_choice_question(
    question_id: UUID = ID_Q1,
    difficulty: QuestionDifficulty = QuestionDifficulty.easy,
) -> Question:
    """Helper for a single-choice question with answer key C1."""
    return Question(
        question_id=question_id,
        prompt="What is two plus two?",
        question_type=QuestionType.single_choice,
        difficulty=difficulty,
        choices=(
            QuestionChoice(choice_id=ID_C1, text="Four"),
            QuestionChoice(choice_id=ID_C2, text="Five"),
            QuestionChoice(choice_id=ID_C3, text="Six"),
        ),
        correct_choice_ids=(ID_C1,),
        provenance=make_provenance(),
    )


def make_multiple_choice_question(
    question_id: UUID = ID_Q2,
    difficulty: QuestionDifficulty = QuestionDifficulty.medium,
) -> Question:
    """Helper for a multiple-choice question with answer key (C1, C2)."""
    return Question(
        question_id=question_id,
        prompt="Select the prime numbers less than five.",
        question_type=QuestionType.multiple_choice,
        difficulty=difficulty,
        choices=(
            QuestionChoice(choice_id=ID_C1, text="Two"),
            QuestionChoice(choice_id=ID_C2, text="Three"),
            QuestionChoice(choice_id=ID_C3, text="Four"),
        ),
        correct_choice_ids=(ID_C1, ID_C2),
        provenance=make_provenance(),
    )


# ==============================================================================
# 20. GRADE_QUESTION TESTS (1-15)
# ==============================================================================


def test_grade_question_correct_single_choice():
    """1. Correct single-choice submission yields correct status with 1/1 point."""
    q = make_single_choice_question()
    sub = AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C1,))
    res = grade_question(q, sub)

    assert res.status == QuestionResultStatus.correct
    assert res.awarded_points == 1
    assert res.max_points == 1
    assert res.selected_choice_ids == (ID_C1,)
    assert res.correct_choice_ids == (ID_C1,)


def test_grade_question_incorrect_single_choice():
    """2. Incorrect single-choice submission yields incorrect status with 0/1 point."""
    q = make_single_choice_question()
    sub = AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C2,))
    res = grade_question(q, sub)

    assert res.status == QuestionResultStatus.incorrect
    assert res.awarded_points == 0
    assert res.max_points == 1
    assert res.selected_choice_ids == (ID_C2,)
    assert res.correct_choice_ids == (ID_C1,)


def test_grade_question_unanswered_single_choice():
    """3. Unanswered single-choice (submission=None) yields unanswered with 0/1 point."""
    q = make_single_choice_question()
    res = grade_question(q, None)

    assert res.status == QuestionResultStatus.unanswered
    assert res.awarded_points == 0
    assert res.max_points == 1
    assert res.selected_choice_ids == ()
    assert res.correct_choice_ids == (ID_C1,)


def test_grade_question_correct_multiple_choice_exact_match():
    """4. Correct multiple-choice submission with exact match yields correct with 1/1."""
    q = make_multiple_choice_question()
    sub = AnswerSubmission(question_id=ID_Q2, selected_choice_ids=(ID_C1, ID_C2))
    res = grade_question(q, sub)

    assert res.status == QuestionResultStatus.correct
    assert res.awarded_points == 1
    assert res.max_points == 1
    assert res.selected_choice_ids == (ID_C1, ID_C2)
    assert res.correct_choice_ids == (ID_C1, ID_C2)


def test_grade_question_multiple_choice_reversed_selection_order():
    """5. Multiple-choice reversed selection order remains correct with 1/1 point."""
    q = make_multiple_choice_question()
    sub = AnswerSubmission(question_id=ID_Q2, selected_choice_ids=(ID_C2, ID_C1))
    res = grade_question(q, sub)

    assert res.status == QuestionResultStatus.correct
    assert res.awarded_points == 1
    # Canonical UUID ordering sorts them deterministically
    assert res.selected_choice_ids == (ID_C1, ID_C2)


def test_grade_question_multiple_choice_subset_incorrect():
    """6. Multiple-choice subset (partial selection) yields incorrect with 0/1 point."""
    q = make_multiple_choice_question()
    sub = AnswerSubmission(question_id=ID_Q2, selected_choice_ids=(ID_C1,))
    res = grade_question(q, sub)

    assert res.status == QuestionResultStatus.incorrect
    assert res.awarded_points == 0
    assert res.max_points == 1


def test_grade_question_multiple_choice_extra_choice_incorrect():
    """7. Multiple-choice with extra valid choice yields incorrect with 0/1 point."""
    q = make_multiple_choice_question()
    sub = AnswerSubmission(
        question_id=ID_Q2, selected_choice_ids=(ID_C1, ID_C2, ID_C3)
    )
    res = grade_question(q, sub)

    assert res.status == QuestionResultStatus.incorrect
    assert res.awarded_points == 0
    assert res.max_points == 1


def test_grade_question_unknown_choice_id_raises_grading_error():
    """8. Selected choice ID that is not part of question raises QuizGradingError."""
    q = make_single_choice_question()
    sub = AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_UNKNOWN_C,))
    with pytest.raises(QuizGradingError, match="not a valid choice"):
        grade_question(q, sub)


def test_grade_question_mismatched_question_id_raises_grading_error():
    """9. Submission question_id mismatching question raises QuizGradingError."""
    q = make_single_choice_question(question_id=ID_Q1)
    sub = AnswerSubmission(question_id=ID_Q2, selected_choice_ids=(ID_C1,))
    with pytest.raises(QuizGradingError, match="does not match"):
        grade_question(q, sub)


def test_grade_question_canonical_correct_choice_ids_ordering():
    """10. Result contains canonical correct_choice_ids ordering."""
    # Construct a question whose correct_choice_ids is in descending UUID order
    q = Question(
        question_id=ID_Q1,
        prompt="Multi question",
        question_type=QuestionType.multiple_choice,
        difficulty=QuestionDifficulty.hard,
        choices=(
            QuestionChoice(choice_id=ID_C1, text="A"),
            QuestionChoice(choice_id=ID_C2, text="B"),
            QuestionChoice(choice_id=ID_C3, text="C"),
        ),
        correct_choice_ids=(ID_C2, ID_C1),
        provenance=make_provenance(),
    )
    res = grade_question(q, None)
    assert res.correct_choice_ids == (ID_C1, ID_C2)


def test_grade_question_canonical_selected_choice_ids_ordering():
    """11. Result contains canonical selected_choice_ids ordering."""
    q = make_multiple_choice_question()
    sub = AnswerSubmission(question_id=ID_Q2, selected_choice_ids=(ID_C2, ID_C1))
    res = grade_question(q, sub)
    assert res.selected_choice_ids == (ID_C1, ID_C2)


@pytest.mark.parametrize("difficulty", [QuestionDifficulty.easy, QuestionDifficulty.hard])
def test_grade_question_difficulty_does_not_affect_base_scoring(
    difficulty: QuestionDifficulty,
):
    """12. Both easy and hard questions award exactly 1 base point when correct."""
    q = make_single_choice_question(difficulty=difficulty)
    sub = AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C1,))
    res = grade_question(q, sub)
    assert res.awarded_points == 1
    assert res.max_points == 1


def test_grade_question_does_not_mutate_question():
    """13. Grading does not mutate the Question input model."""
    q = make_single_choice_question()
    q_copy = copy.deepcopy(q)
    sub = AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C1,))
    grade_question(q, sub)
    assert q == q_copy


def test_grade_question_does_not_mutate_submission():
    """14. Grading does not mutate the AnswerSubmission input model."""
    q = make_single_choice_question()
    sub = AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C1,))
    sub_copy = copy.deepcopy(sub)
    grade_question(q, sub)
    assert sub == sub_copy


def test_grade_question_repeated_produces_identical_json():
    """15. Repeated grading of identical inputs produces identical JSON representation."""
    q = make_single_choice_question()
    sub = AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C1,))
    res1 = grade_question(q, sub)
    res2 = grade_question(q, sub)
    assert res1.model_dump(mode="json") == res2.model_dump(mode="json")


# ==============================================================================
# 21. GRADE_QUIZ TESTS (16-31)
# ==============================================================================


def make_two_question_quiz() -> Quiz:
    """Helper for a two-question quiz."""
    q1 = make_single_choice_question(question_id=ID_Q1)
    q2 = make_multiple_choice_question(question_id=ID_Q2)
    return Quiz(
        quiz_id=ID_QUIZ,
        title="Synthetic Evaluation Quiz",
        questions=(
            QuizQuestion(position=1, question=q1),
            QuizQuestion(position=2, question=q2),
        ),
    )


def test_grade_quiz_all_correct():
    """16. All-correct quiz submission aggregates correctly to 2/2 points."""
    quiz = make_two_question_quiz()
    subs = (
        AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C1,)),
        AnswerSubmission(question_id=ID_Q2, selected_choice_ids=(ID_C1, ID_C2)),
    )
    result = grade_quiz(quiz, subs)

    assert result.total_points == 2
    assert result.max_points == 2
    assert result.correct_count == 2
    assert result.incorrect_count == 0
    assert result.unanswered_count == 0


def test_grade_quiz_mixed_outcomes():
    """17. Mixed correct, incorrect, and unanswered questions aggregate correctly."""
    q1 = make_single_choice_question(question_id=ID_Q1)
    q2 = make_multiple_choice_question(question_id=ID_Q2)
    q3 = Question(
        question_id=ID_Q3,
        prompt="Third prompt",
        question_type=QuestionType.single_choice,
        difficulty=QuestionDifficulty.medium,
        choices=(
            QuestionChoice(choice_id=ID_C1, text="X"),
            QuestionChoice(choice_id=ID_C2, text="Y"),
        ),
        correct_choice_ids=(ID_C1,),
        provenance=make_provenance(),
    )
    quiz = Quiz(
        quiz_id=ID_QUIZ,
        title="Three Question Quiz",
        questions=(
            QuizQuestion(position=1, question=q1),
            QuizQuestion(position=2, question=q2),
            QuizQuestion(position=3, question=q3),
        ),
    )
    # Q1: Correct, Q2: Incorrect, Q3: Unanswered (omitted)
    subs = (
        AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C1,)),
        AnswerSubmission(question_id=ID_Q2, selected_choice_ids=(ID_C3,)),
    )
    result = grade_quiz(quiz, subs)

    assert result.total_points == 1
    assert result.max_points == 3
    assert result.correct_count == 1
    assert result.incorrect_count == 1
    assert result.unanswered_count == 1


def test_grade_quiz_missing_submission_creates_unanswered():
    """18. Missing submission for a question produces UNANSWERED result."""
    quiz = make_two_question_quiz()
    subs = (AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C1,)),)
    result = grade_quiz(quiz, subs)

    assert result.question_results[1].status == QuestionResultStatus.unanswered
    assert result.question_results[1].awarded_points == 0
    assert result.unanswered_count == 1


def test_grade_quiz_all_missing_submissions_creates_unanswered():
    """19. Zero submissions produces all UNANSWERED results."""
    quiz = make_two_question_quiz()
    result = grade_quiz(quiz, ())

    assert result.total_points == 0
    assert result.max_points == 2
    assert result.correct_count == 0
    assert result.incorrect_count == 0
    assert result.unanswered_count == 2
    assert all(r.status == QuestionResultStatus.unanswered for r in result.question_results)


def test_grade_quiz_max_points_equals_question_count():
    """20. max_points equals number of quiz questions."""
    quiz = make_two_question_quiz()
    result = grade_quiz(quiz, ())
    assert result.max_points == len(quiz.questions) == 2


def test_grade_quiz_total_points_equals_awarded_sum():
    """21. total_points equals sum of individual awarded points."""
    quiz = make_two_question_quiz()
    subs = (AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C1,)),)
    result = grade_quiz(quiz, subs)
    assert result.total_points == sum(r.awarded_points for r in result.question_results)


def test_grade_quiz_counts_accuracy():
    """22-24. correct_count, incorrect_count, and unanswered_count are accurate."""
    quiz = make_two_question_quiz()
    subs = (
        AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C1,)),  # correct
        AnswerSubmission(question_id=ID_Q2, selected_choice_ids=(ID_C3,)),  # incorrect
    )
    result = grade_quiz(quiz, subs)
    assert result.correct_count == 1
    assert result.incorrect_count == 1
    assert result.unanswered_count == 0


def test_grade_quiz_duplicate_submissions_rejected():
    """25. Duplicate submissions for the same question raise QuizGradingError."""
    quiz = make_two_question_quiz()
    subs = (
        AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C1,)),
        AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C2,)),
    )
    with pytest.raises(QuizGradingError, match="Duplicate submission detected"):
        grade_quiz(quiz, subs)


def test_grade_quiz_unknown_question_submission_rejected():
    """26. Submission referencing question not in quiz raises QuizGradingError."""
    quiz = make_two_question_quiz()
    subs = (
        AnswerSubmission(question_id=ID_UNKNOWN_Q, selected_choice_ids=(ID_C1,)),
    )
    with pytest.raises(QuizGradingError, match="does not belong to quiz"):
        grade_quiz(quiz, subs)


def test_grade_quiz_submission_order_does_not_control_result_order():
    """27. Submissions provided in reverse order still result in position order."""
    quiz = make_two_question_quiz()
    subs = (
        AnswerSubmission(question_id=ID_Q2, selected_choice_ids=(ID_C1, ID_C2)),
        AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C1,)),
    )
    result = grade_quiz(quiz, subs)
    assert result.question_results[0].question_id == ID_Q1
    assert result.question_results[1].question_id == ID_Q2


def test_grade_quiz_position_controls_result_order():
    """28. Results follow QuizQuestion.position even if quiz.questions is reordered."""
    q1 = make_single_choice_question(question_id=ID_Q1)
    q2 = make_multiple_choice_question(question_id=ID_Q2)
    # Questions provided in reversed tuple order in the Quiz model
    quiz = Quiz(
        quiz_id=ID_QUIZ,
        title="Position Ordering Quiz",
        questions=(
            QuizQuestion(position=2, question=q2),
            QuizQuestion(position=1, question=q1),
        ),
    )
    result = grade_quiz(quiz, ())
    assert result.question_results[0].question_id == ID_Q1
    assert result.question_results[1].question_id == ID_Q2


def test_grade_quiz_repeated_produces_identical_json():
    """29. Repeated grade_quiz calls produce identical JSON output."""
    quiz = make_two_question_quiz()
    subs = (AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C1,)),)
    res1 = grade_quiz(quiz, subs)
    res2 = grade_quiz(quiz, subs)
    assert res1.model_dump(mode="json") == res2.model_dump(mode="json")


def test_grade_quiz_does_not_mutate_quiz():
    """30. Grading does not mutate the Quiz model."""
    quiz = make_two_question_quiz()
    quiz_copy = copy.deepcopy(quiz)
    subs = (AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C1,)),)
    grade_quiz(quiz, subs)
    assert quiz == quiz_copy


def test_grade_quiz_does_not_mutate_submissions():
    """31. Grading does not mutate the submissions sequence."""
    quiz = make_two_question_quiz()
    subs = (AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C1,)),)
    subs_copy = copy.deepcopy(subs)
    grade_quiz(quiz, subs)
    assert subs == subs_copy


# ==============================================================================
# 22. RESULT MODEL VALIDATION TESTS (32-46)
# ==============================================================================


def test_valid_question_result():
    """32. Valid QuestionResult instantiates cleanly."""
    res = QuestionResult(
        question_id=ID_Q1,
        status=QuestionResultStatus.correct,
        selected_choice_ids=(ID_C1,),
        correct_choice_ids=(ID_C1,),
        awarded_points=1,
        max_points=1,
    )
    assert res.question_id == ID_Q1
    assert res.awarded_points == 1


def test_valid_quiz_result():
    """33. Valid QuizResult instantiates cleanly."""
    qr = QuestionResult(
        question_id=ID_Q1,
        status=QuestionResultStatus.correct,
        selected_choice_ids=(ID_C1,),
        correct_choice_ids=(ID_C1,),
        awarded_points=1,
        max_points=1,
    )
    qz = QuizResult(
        quiz_id=ID_QUIZ,
        question_results=(qr,),
        total_points=1,
        max_points=1,
        correct_count=1,
        incorrect_count=0,
        unanswered_count=0,
    )
    assert qz.total_points == 1
    assert len(qz.question_results) == 1


def test_question_result_rejects_extra_fields():
    """34. QuestionResult rejects extra fields."""
    with pytest.raises(ValidationError):
        QuestionResult(
            question_id=ID_Q1,
            status=QuestionResultStatus.correct,
            selected_choice_ids=(ID_C1,),
            correct_choice_ids=(ID_C1,),
            awarded_points=1,
            max_points=1,
            unexpected_field="disallowed",  # type: ignore[call-arg]
        )


def test_quiz_result_rejects_extra_fields():
    """35. QuizResult rejects extra fields."""
    qr = QuestionResult(
        question_id=ID_Q1,
        status=QuestionResultStatus.correct,
        selected_choice_ids=(ID_C1,),
        correct_choice_ids=(ID_C1,),
        awarded_points=1,
        max_points=1,
    )
    with pytest.raises(ValidationError):
        QuizResult(
            quiz_id=ID_QUIZ,
            question_results=(qr,),
            total_points=1,
            max_points=1,
            correct_count=1,
            incorrect_count=0,
            unanswered_count=0,
            unexpected_field="disallowed",  # type: ignore[call-arg]
        )


def test_result_models_are_frozen():
    """36. Result models cannot be modified in-place."""
    qr = QuestionResult(
        question_id=ID_Q1,
        status=QuestionResultStatus.correct,
        selected_choice_ids=(ID_C1,),
        correct_choice_ids=(ID_C1,),
        awarded_points=1,
        max_points=1,
    )
    with pytest.raises(ValidationError):
        qr.awarded_points = 0  # type: ignore[misc]

    qz = QuizResult(
        quiz_id=ID_QUIZ,
        question_results=(qr,),
        total_points=1,
        max_points=1,
        correct_count=1,
        incorrect_count=0,
        unanswered_count=0,
    )
    with pytest.raises(ValidationError):
        qz.total_points = 0  # type: ignore[misc]


def test_question_result_correct_with_zero_points_rejected():
    """37. Correct status with awarded_points=0 is rejected."""
    with pytest.raises(ValidationError, match="award 1 point"):
        QuestionResult(
            question_id=ID_Q1,
            status=QuestionResultStatus.correct,
            selected_choice_ids=(ID_C1,),
            correct_choice_ids=(ID_C1,),
            awarded_points=0,
            max_points=1,
        )


def test_question_result_incorrect_with_one_point_rejected():
    """38. Incorrect status with awarded_points=1 is rejected."""
    with pytest.raises(ValidationError, match="award 0 points"):
        QuestionResult(
            question_id=ID_Q1,
            status=QuestionResultStatus.incorrect,
            selected_choice_ids=(ID_C2,),
            correct_choice_ids=(ID_C1,),
            awarded_points=1,
            max_points=1,
        )


def test_question_result_unanswered_with_selections_rejected():
    """39. Unanswered status with non-empty selected_choice_ids is rejected."""
    with pytest.raises(ValidationError, match="cannot have selected choices"):
        QuestionResult(
            question_id=ID_Q1,
            status=QuestionResultStatus.unanswered,
            selected_choice_ids=(ID_C1,),
            correct_choice_ids=(ID_C1,),
            awarded_points=0,
            max_points=1,
        )


def test_question_result_unanswered_with_nonzero_points_rejected():
    """40. Unanswered status with awarded_points=1 is rejected."""
    with pytest.raises(ValidationError, match="award 0 points"):
        QuestionResult(
            question_id=ID_Q1,
            status=QuestionResultStatus.unanswered,
            selected_choice_ids=(),
            correct_choice_ids=(ID_C1,),
            awarded_points=1,
            max_points=1,
        )


def test_question_result_empty_correct_choice_ids_rejected():
    """41. Empty correct_choice_ids is rejected."""
    with pytest.raises(ValidationError, match="must not be empty"):
        QuestionResult(
            question_id=ID_Q1,
            status=QuestionResultStatus.correct,
            selected_choice_ids=(ID_C1,),
            correct_choice_ids=(),
            awarded_points=1,
            max_points=1,
        )


def test_question_result_duplicate_correct_choice_ids_rejected():
    """42. Duplicate correct_choice_ids is rejected."""
    with pytest.raises(ValidationError, match="unique IDs"):
        QuestionResult(
            question_id=ID_Q1,
            status=QuestionResultStatus.correct,
            selected_choice_ids=(ID_C1,),
            correct_choice_ids=(ID_C1, ID_C1),
            awarded_points=1,
            max_points=1,
        )


def test_quiz_result_inconsistent_total_points_rejected():
    """43. QuizResult with total_points not matching sum of awarded_points is rejected."""
    qr = QuestionResult(
        question_id=ID_Q1,
        status=QuestionResultStatus.correct,
        selected_choice_ids=(ID_C1,),
        correct_choice_ids=(ID_C1,),
        awarded_points=1,
        max_points=1,
    )
    with pytest.raises(ValidationError, match="total_points"):
        QuizResult(
            quiz_id=ID_QUIZ,
            question_results=(qr,),
            total_points=2,  # should be 1
            max_points=1,
            correct_count=1,
            incorrect_count=0,
            unanswered_count=0,
        )


def test_quiz_result_inconsistent_max_points_rejected():
    """44. QuizResult with max_points not matching sum of max_points is rejected."""
    qr = QuestionResult(
        question_id=ID_Q1,
        status=QuestionResultStatus.correct,
        selected_choice_ids=(ID_C1,),
        correct_choice_ids=(ID_C1,),
        awarded_points=1,
        max_points=1,
    )
    with pytest.raises(ValidationError, match="max_points"):
        QuizResult(
            quiz_id=ID_QUIZ,
            question_results=(qr,),
            total_points=1,
            max_points=5,  # should be 1
            correct_count=1,
            incorrect_count=0,
            unanswered_count=0,
        )


def test_quiz_result_inconsistent_status_counts_rejected():
    """45. QuizResult with counts not matching status distribution is rejected."""
    qr = QuestionResult(
        question_id=ID_Q1,
        status=QuestionResultStatus.correct,
        selected_choice_ids=(ID_C1,),
        correct_choice_ids=(ID_C1,),
        awarded_points=1,
        max_points=1,
    )
    with pytest.raises(ValidationError, match="correct_count"):
        QuizResult(
            quiz_id=ID_QUIZ,
            question_results=(qr,),
            total_points=1,
            max_points=1,
            correct_count=0,  # should be 1
            incorrect_count=1,
            unanswered_count=0,
        )


def test_quiz_result_duplicate_question_ids_rejected():
    """46. QuizResult containing duplicate question_ids is rejected."""
    qr1 = QuestionResult(
        question_id=ID_Q1,
        status=QuestionResultStatus.correct,
        selected_choice_ids=(ID_C1,),
        correct_choice_ids=(ID_C1,),
        awarded_points=1,
        max_points=1,
    )
    qr2 = QuestionResult(
        question_id=ID_Q1,  # Duplicate ID
        status=QuestionResultStatus.unanswered,
        selected_choice_ids=(),
        correct_choice_ids=(ID_C1,),
        awarded_points=0,
        max_points=1,
    )
    with pytest.raises(ValidationError, match="Question IDs within a quiz result must be unique"):
        QuizResult(
            quiz_id=ID_QUIZ,
            question_results=(qr1, qr2),
            total_points=1,
            max_points=2,
            correct_count=1,
            incorrect_count=0,
            unanswered_count=1,
        )
