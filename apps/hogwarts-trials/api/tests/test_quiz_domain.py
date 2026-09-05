"""Deterministic domain contract tests for Hogwarts Trials quiz models.

Exercises positive and negative structural validation invariants using synthetic fixtures.
"""

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
    QuestionType,
    Quiz,
    QuizQuestion,
    SourceTier,
)

# Fixed deterministic UUID fixtures for reproducible tests
ID_Q1 = UUID("00000000-0000-0000-0000-000000000001")
ID_Q2 = UUID("00000000-0000-0000-0000-000000000002")
ID_C1 = UUID("00000000-0000-0000-0000-000000000011")
ID_C2 = UUID("00000000-0000-0000-0000-000000000012")
ID_C3 = UUID("00000000-0000-0000-0000-000000000013")
ID_C4 = UUID("00000000-0000-0000-0000-000000000014")
ID_QUIZ = UUID("00000000-0000-0000-0000-000000000101")


def make_valid_provenance(
    source_tier: SourceTier = SourceTier.book_canon,
    source_reference: str = "synthetic-volume-1",
    chapter_reference: str | None = "chapter-3",
    curation_status: CurationStatus = CurationStatus.approved,
) -> QuestionProvenance:
    """Helper to create a valid synthetic provenance instance."""
    return QuestionProvenance(
        source_tier=source_tier,
        source_reference=source_reference,
        chapter_reference=chapter_reference,
        curation_status=curation_status,
    )


def make_valid_choices() -> tuple[QuestionChoice, ...]:
    """Helper to create standard synthetic question choices."""
    return (
        QuestionChoice(choice_id=ID_C1, text="Synthetic Choice Alpha"),
        QuestionChoice(choice_id=ID_C2, text="Synthetic Choice Beta"),
        QuestionChoice(choice_id=ID_C3, text="Synthetic Choice Gamma"),
    )


def make_valid_single_choice_question(
    question_id: UUID = ID_Q1,
    prompt: str = "What is two plus two?",
    choices: tuple[QuestionChoice, ...] | None = None,
    correct_choice_ids: tuple[UUID, ...] = (ID_C1,),
    explanation: str | None = "Basic arithmetic deduction.",
) -> Question:
    """Helper to create a valid synthetic single-choice question."""
    return Question(
        question_id=question_id,
        prompt=prompt,
        question_type=QuestionType.single_choice,
        difficulty=QuestionDifficulty.easy,
        choices=choices or make_valid_choices(),
        correct_choice_ids=correct_choice_ids,
        provenance=make_valid_provenance(),
        explanation=explanation,
    )


# ==============================================================================
# 1. ENUMS / SERIALIZATION
# ==============================================================================


def test_enum_serialization_values():
    """Verify that domain enums have stable, exact string values."""
    assert QuestionType.single_choice.value == "single_choice"
    assert QuestionType.multiple_choice.value == "multiple_choice"

    assert QuestionDifficulty.easy.value == "easy"
    assert QuestionDifficulty.medium.value == "medium"
    assert QuestionDifficulty.hard.value == "hard"

    assert SourceTier.book_canon.value == "book_canon"
    assert SourceTier.screen_adaptation.value == "screen_adaptation"
    assert SourceTier.official_expanded.value == "official_expanded"
    assert SourceTier.synthetic.value == "synthetic"

    assert CurationStatus.draft.value == "draft"
    assert CurationStatus.reviewed.value == "reviewed"
    assert CurationStatus.approved.value == "approved"


# ==============================================================================
# 2-5. QUESTION PROVENANCE
# ==============================================================================


def test_source_tier_synthetic_exists_and_accepted_by_provenance():
    """Verify SourceTier.synthetic exists, serializes to 'synthetic', and is accepted by QuestionProvenance."""
    assert hasattr(SourceTier, "synthetic")
    assert SourceTier.synthetic == "synthetic"
    assert SourceTier.synthetic.value == "synthetic"

    # Verify existing SourceTier values remain unchanged
    assert SourceTier.book_canon.value == "book_canon"
    assert SourceTier.screen_adaptation.value == "screen_adaptation"
    assert SourceTier.official_expanded.value == "official_expanded"

    # Verify QuestionProvenance accepts SourceTier.synthetic
    prov = QuestionProvenance(
        source_tier=SourceTier.synthetic,
        source_reference="synthetic-test-fixture",
        chapter_reference=None,
        curation_status=CurationStatus.approved,
    )
    assert prov.source_tier == SourceTier.synthetic
    assert prov.source_reference == "synthetic-test-fixture"


def test_valid_provenance():
    """Verify construction of valid question provenance with optional fields."""
    prov = make_valid_provenance(chapter_reference=None)
    assert prov.source_tier == SourceTier.book_canon
    assert prov.source_reference == "synthetic-volume-1"
    assert prov.chapter_reference is None
    assert prov.curation_status == CurationStatus.approved

    prov_with_chap = make_valid_provenance(chapter_reference=" chapter-12 ")
    assert prov_with_chap.chapter_reference == "chapter-12"


@pytest.mark.parametrize("blank_ref", ["", "   ", "\t\n"])
def test_provenance_blank_source_reference_rejected(blank_ref: str):
    """Verify blank source_reference is rejected."""
    with pytest.raises(ValidationError):
        QuestionProvenance(
            source_tier=SourceTier.book_canon,
            source_reference=blank_ref,
            curation_status=CurationStatus.approved,
        )


@pytest.mark.parametrize("blank_chap", ["", "   ", "\t\n"])
def test_provenance_blank_explicit_chapter_reference_rejected(blank_chap: str):
    """Verify explicitly provided blank chapter_reference is rejected."""
    with pytest.raises(ValidationError):
        QuestionProvenance(
            source_tier=SourceTier.book_canon,
            source_reference="synthetic-volume-1",
            chapter_reference=blank_chap,
            curation_status=CurationStatus.approved,
        )


def test_provenance_extra_fields_rejected():
    """Verify extra fields are strictly forbidden on provenance."""
    with pytest.raises(ValidationError):
        QuestionProvenance(
            source_tier=SourceTier.book_canon,
            source_reference="synthetic-volume-1",
            curation_status=CurationStatus.approved,
            extra_field="disallowed",  # type: ignore[call-arg]
        )


# ==============================================================================
# 6-7. QUESTION CHOICE
# ==============================================================================


def test_valid_question_choice():
    """Verify construction and whitespace stripping for valid choice."""
    choice = QuestionChoice(choice_id=ID_C1, text="  Option One  ")
    assert choice.choice_id == ID_C1
    assert choice.text == "Option One"


@pytest.mark.parametrize("blank_text", ["", "   ", "\n"])
def test_question_choice_blank_text_rejected(blank_text: str):
    """Verify blank choice text is rejected."""
    with pytest.raises(ValidationError):
        QuestionChoice(choice_id=ID_C1, text=blank_text)


# ==============================================================================
# 8-14. SINGLE-CHOICE QUESTION
# ==============================================================================


def test_valid_single_choice_question():
    """Verify a valid single-choice question constructs cleanly."""
    q = make_valid_single_choice_question()
    assert q.question_id == ID_Q1
    assert q.question_type == QuestionType.single_choice
    assert len(q.choices) == 3
    assert q.correct_choice_ids == (ID_C1,)
    assert q.explanation == "Basic arithmetic deduction."


def test_single_choice_fewer_than_two_choices_rejected():
    """Verify question with fewer than 2 choices is rejected."""
    with pytest.raises(ValidationError, match="at least 2 choices"):
        make_valid_single_choice_question(
            choices=(QuestionChoice(choice_id=ID_C1, text="Solo Choice"),),
            correct_choice_ids=(ID_C1,),
        )


def test_question_duplicate_choice_ids_rejected():
    """Verify question with duplicate choice IDs is rejected."""
    choices = (
        QuestionChoice(choice_id=ID_C1, text="Choice Alpha"),
        QuestionChoice(choice_id=ID_C1, text="Choice Beta"),
    )
    with pytest.raises(ValidationError, match="Choice IDs within a question must be unique"):
        make_valid_single_choice_question(choices=choices, correct_choice_ids=(ID_C1,))


def test_question_duplicate_correct_choice_ids_rejected():
    """Verify duplicate correct_choice_ids are rejected."""
    with pytest.raises(ValidationError, match="correct_choice_ids must be unique"):
        make_valid_single_choice_question(correct_choice_ids=(ID_C1, ID_C1))


def test_question_nonexistent_correct_choice_id_rejected():
    """Verify correct_choice_id that does not match any choice is rejected."""
    with pytest.raises(ValidationError, match="does not exist in choices"):
        make_valid_single_choice_question(correct_choice_ids=(ID_C4,))


def test_single_choice_zero_correct_choices_rejected():
    """Verify single-choice question with empty correct_choice_ids is rejected."""
    with pytest.raises(ValidationError, match="exactly one correct choice ID"):
        make_valid_single_choice_question(correct_choice_ids=())


def test_single_choice_multiple_correct_choices_rejected():
    """Verify single-choice question with more than one correct choice is rejected."""
    with pytest.raises(ValidationError, match="exactly one correct choice ID"):
        make_valid_single_choice_question(correct_choice_ids=(ID_C1, ID_C2))


# ==============================================================================
# 15-17. MULTIPLE-CHOICE QUESTION
# ==============================================================================


def test_valid_multiple_choice_question():
    """Verify valid multiple-choice question constructs cleanly."""
    q = Question(
        question_id=ID_Q1,
        prompt="Select two correct synthetic responses.",
        question_type=QuestionType.multiple_choice,
        difficulty=QuestionDifficulty.medium,
        choices=make_valid_choices(),
        correct_choice_ids=(ID_C1, ID_C2),
        provenance=make_valid_provenance(),
    )
    assert q.question_type == QuestionType.multiple_choice
    assert q.correct_choice_ids == (ID_C1, ID_C2)
    assert q.explanation is None


def test_multiple_choice_only_one_correct_choice_rejected():
    """Verify multiple-choice question with only one correct choice is rejected."""
    with pytest.raises(ValidationError, match="at least two correct choice IDs"):
        Question(
            question_id=ID_Q1,
            prompt="Select correct responses.",
            question_type=QuestionType.multiple_choice,
            difficulty=QuestionDifficulty.medium,
            choices=make_valid_choices(),
            correct_choice_ids=(ID_C1,),
            provenance=make_valid_provenance(),
        )


def test_multiple_choice_all_choices_correct_rejected():
    """Verify multiple-choice question with every choice marked correct is rejected."""
    with pytest.raises(ValidationError, match="cannot have all available choices marked correct"):
        Question(
            question_id=ID_Q1,
            prompt="Select correct responses.",
            question_type=QuestionType.multiple_choice,
            difficulty=QuestionDifficulty.hard,
            choices=make_valid_choices(),  # 3 choices
            correct_choice_ids=(ID_C1, ID_C2, ID_C3),  # all 3 correct
            provenance=make_valid_provenance(),
        )


# ==============================================================================
# 18-19. QUESTION TEXT & BOUNDS
# ==============================================================================


@pytest.mark.parametrize("blank_prompt", ["", "   ", "\n\t"])
def test_question_blank_prompt_rejected(blank_prompt: str):
    """Verify blank prompt is rejected."""
    with pytest.raises(ValidationError):
        make_valid_single_choice_question(prompt=blank_prompt)


@pytest.mark.parametrize("blank_exp", ["", "   ", "\n"])
def test_question_blank_explicit_explanation_rejected(blank_exp: str):
    """Verify explicitly provided blank explanation is rejected."""
    with pytest.raises(ValidationError):
        make_valid_single_choice_question(explanation=blank_exp)


def test_question_choices_cap_exceeded_rejected():
    """Verify that choices cannot exceed the upper limit of 8."""
    nine_choices = tuple(
        QuestionChoice(
            choice_id=UUID(f"00000000-0000-0000-0000-{i:012d}"),
            text=f"Choice {i}",
        )
        for i in range(1, 10)
    )
    with pytest.raises(ValidationError, match="cannot contain more than 8 choices"):
        make_valid_single_choice_question(
            choices=nine_choices,
            correct_choice_ids=(nine_choices[0].choice_id,),
        )


# ==============================================================================
# 20. QUIZ QUESTION
# ==============================================================================


@pytest.mark.parametrize("invalid_pos", [0, -1, -10])
def test_quiz_question_position_non_positive_rejected(invalid_pos: int):
    """Verify quiz question position must be >= 1."""
    q = make_valid_single_choice_question()
    with pytest.raises(ValidationError):
        QuizQuestion(position=invalid_pos, question=q)


# ==============================================================================
# 21-26. QUIZ
# ==============================================================================


def test_valid_quiz():
    """Verify valid multi-question quiz creation."""
    q1 = make_valid_single_choice_question(question_id=ID_Q1, prompt="First prompt")
    q2 = make_valid_single_choice_question(question_id=ID_Q2, prompt="Second prompt")

    quiz = Quiz(
        quiz_id=ID_QUIZ,
        title="Introductory Synthetic Quiz",
        description="A deterministic test quiz fixture.",
        questions=(
            QuizQuestion(position=1, question=q1),
            QuizQuestion(position=2, question=q2),
        ),
    )
    assert quiz.quiz_id == ID_QUIZ
    assert quiz.title == "Introductory Synthetic Quiz"
    assert len(quiz.questions) == 2


def test_empty_quiz_rejected():
    """Verify quiz without questions is rejected."""
    with pytest.raises(ValidationError, match="at least one question"):
        Quiz(
            quiz_id=ID_QUIZ,
            title="Empty Quiz",
            questions=(),
        )


def test_quiz_duplicate_question_ids_rejected():
    """Verify quiz containing duplicate questions is rejected."""
    q1 = make_valid_single_choice_question(question_id=ID_Q1)
    with pytest.raises(ValidationError, match="Question IDs within a quiz must be unique"):
        Quiz(
            quiz_id=ID_QUIZ,
            title="Duplicate Question Quiz",
            questions=(
                QuizQuestion(position=1, question=q1),
                QuizQuestion(position=2, question=q1),
            ),
        )


def test_quiz_duplicate_positions_rejected():
    """Verify quiz with duplicate position numbers is rejected."""
    q1 = make_valid_single_choice_question(question_id=ID_Q1)
    q2 = make_valid_single_choice_question(question_id=ID_Q2)
    with pytest.raises(ValidationError, match="positions must be unique"):
        Quiz(
            quiz_id=ID_QUIZ,
            title="Duplicate Position Quiz",
            questions=(
                QuizQuestion(position=1, question=q1),
                QuizQuestion(position=1, question=q2),
            ),
        )


def test_quiz_non_contiguous_positions_rejected():
    """Verify quiz positions must form a contiguous sequence."""
    q1 = make_valid_single_choice_question(question_id=ID_Q1)
    q2 = make_valid_single_choice_question(question_id=ID_Q2)
    with pytest.raises(ValidationError, match="contiguous sequence beginning at 1"):
        Quiz(
            quiz_id=ID_QUIZ,
            title="Gapped Positions Quiz",
            questions=(
                QuizQuestion(position=1, question=q1),
                QuizQuestion(position=3, question=q2),
            ),
        )


def test_quiz_first_position_not_one_rejected():
    """Verify quiz positions must start at 1."""
    q1 = make_valid_single_choice_question(question_id=ID_Q1)
    q2 = make_valid_single_choice_question(question_id=ID_Q2)
    with pytest.raises(ValidationError, match="contiguous sequence beginning at 1"):
        Quiz(
            quiz_id=ID_QUIZ,
            title="Shifted Positions Quiz",
            questions=(
                QuizQuestion(position=2, question=q1),
                QuizQuestion(position=3, question=q2),
            ),
        )


# ==============================================================================
# 27-31. ANSWER SUBMISSION
# ==============================================================================


def test_valid_single_selection_submission():
    """Verify single-choice answer submission."""
    sub = AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C1,))
    assert sub.question_id == ID_Q1
    assert sub.selected_choice_ids == (ID_C1,)


def test_valid_multi_selection_submission():
    """Verify multiple-choice answer submission."""
    sub = AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C1, ID_C2))
    assert sub.question_id == ID_Q1
    assert sub.selected_choice_ids == (ID_C1, ID_C2)


def test_answer_submission_empty_selections_rejected():
    """Verify submission with no choices selected is rejected."""
    with pytest.raises(ValidationError, match="At least one choice must be selected"):
        AnswerSubmission(question_id=ID_Q1, selected_choice_ids=())


def test_answer_submission_duplicate_selections_rejected():
    """Verify submission with duplicate choice selections is rejected."""
    with pytest.raises(ValidationError, match="selected_choice_ids must be unique"):
        AnswerSubmission(question_id=ID_Q1, selected_choice_ids=(ID_C1, ID_C1))


def test_answer_submission_extra_fields_rejected():
    """Verify extra fields are forbidden on answer submission."""
    with pytest.raises(ValidationError):
        AnswerSubmission(
            question_id=ID_Q1,
            selected_choice_ids=(ID_C1,),
            extra_token="disallowed",  # type: ignore[call-arg]
        )


# ==============================================================================
# 32. IMMUTABILITY / FROZEN MODELS
# ==============================================================================


def test_domain_model_immutability():
    """Verify domain models are frozen and reject in-place attribute mutation."""
    choice = QuestionChoice(choice_id=ID_C1, text="Immutable Choice")
    with pytest.raises(ValidationError):
        choice.text = "Mutated Choice"  # type: ignore[misc]

    prov = make_valid_provenance()
    with pytest.raises(ValidationError):
        prov.source_reference = "mutated-ref"  # type: ignore[misc]

    question = make_valid_single_choice_question()
    with pytest.raises(ValidationError):
        question.prompt = "Mutated prompt"  # type: ignore[misc]


# ==============================================================================
# 33. SERIALIZATION / JSON DUMP
# ==============================================================================


def test_deterministic_model_dump_json():
    """Verify deterministic JSON serialization of domain models."""
    q = make_valid_single_choice_question()
    data = q.model_dump(mode="json")

    assert data["question_id"] == str(ID_Q1)
    assert data["prompt"] == "What is two plus two?"
    assert data["question_type"] == "single_choice"
    assert data["difficulty"] == "easy"
    assert len(data["choices"]) == 3
    assert data["choices"][0]["choice_id"] == str(ID_C1)
    assert data["choices"][0]["text"] == "Synthetic Choice Alpha"
    assert data["correct_choice_ids"] == [str(ID_C1)]
    assert data["provenance"]["source_tier"] == "book_canon"
    assert data["provenance"]["source_reference"] == "synthetic-volume-1"
    assert data["provenance"]["chapter_reference"] == "chapter-3"
    assert data["provenance"]["curation_status"] == "approved"
    assert data["explanation"] == "Basic arithmetic deduction."

