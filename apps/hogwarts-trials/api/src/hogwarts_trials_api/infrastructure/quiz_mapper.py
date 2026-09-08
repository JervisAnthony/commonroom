"""Domain <-> persistence mapper for Hogwarts Trials quiz domain.

Provides explicit bidirectional mapping between SQLAlchemy relational persistence models
and immutable domain models (Quiz, Question, QuestionChoice, QuestionProvenance, QuizQuestion).
Ensures that persistence models never leak outside the infrastructure layer.
"""

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
from hogwarts_trials_api.infrastructure.models import (
    QuestionChoiceModel,
    QuestionCorrectChoiceModel,
    QuestionModel,
    QuizModel,
    QuizQuestionModel,
)


def question_model_to_domain(model: QuestionModel) -> Question:
    """Map a QuestionModel persistence instance to an immutable domain Question."""
    provenance = QuestionProvenance(
        source_tier=SourceTier(model.source_tier),
        source_reference=model.source_reference,
        chapter_reference=model.chapter_reference,
        curation_status=CurationStatus(model.curation_status),
    )

    # Sort choices deterministically by their 1-based position
    sorted_choices = sorted(model.choices, key=lambda c: c.position)
    domain_choices = tuple(
        QuestionChoice(choice_id=c.choice_id, text=c.text)
        for c in sorted_choices
    )

    # Reconstruct correct choice IDs in deterministic order corresponding to choice position
    choice_id_order = {c.choice_id: idx for idx, c in enumerate(domain_choices)}
    raw_correct_ids = [cc.choice_id for cc in model.correct_choices]
    correct_choice_ids = tuple(
        sorted(raw_correct_ids, key=lambda cid: choice_id_order.get(cid, 999999))
    )

    return Question(
        question_id=model.question_id,
        prompt=model.prompt,
        question_type=QuestionType(model.question_type),
        difficulty=QuestionDifficulty(model.difficulty),
        choices=domain_choices,
        correct_choice_ids=correct_choice_ids,
        provenance=provenance,
        explanation=model.explanation,
    )


def quiz_model_to_domain(model: QuizModel) -> Quiz:
    """Map a QuizModel persistence instance to an immutable domain Quiz."""
    sorted_quiz_questions = sorted(model.quiz_questions, key=lambda qq: qq.position)
    domain_quiz_questions = tuple(
        QuizQuestion(
            position=qq.position,
            question=question_model_to_domain(qq.question),
        )
        for qq in sorted_quiz_questions
    )

    return Quiz(
        quiz_id=model.quiz_id,
        title=model.title,
        description=model.description,
        questions=domain_quiz_questions,
    )


def quiz_domain_to_model(quiz: Quiz) -> QuizModel:
    """Convert an immutable domain Quiz to a QuizModel persistence instance graph.

    Primarily used for test fixtures and database seeding.
    """
    quiz_model = QuizModel(
        quiz_id=quiz.quiz_id,
        title=quiz.title,
        description=quiz.description,
    )

    for qq in sorted(quiz.questions, key=lambda q: q.position):
        q = qq.question
        question_model = QuestionModel(
            question_id=q.question_id,
            prompt=q.prompt,
            question_type=q.question_type.value,
            difficulty=q.difficulty.value,
            explanation=q.explanation,
            source_tier=q.provenance.source_tier.value,
            source_reference=q.provenance.source_reference,
            chapter_reference=q.provenance.chapter_reference,
            curation_status=q.provenance.curation_status.value,
        )

        for idx, choice in enumerate(q.choices, start=1):
            choice_model = QuestionChoiceModel(
                choice_id=choice.choice_id,
                question_id=q.question_id,
                text=choice.text,
                position=idx,
            )
            question_model.choices.append(choice_model)

        for correct_id in q.correct_choice_ids:
            correct_model = QuestionCorrectChoiceModel(
                question_id=q.question_id,
                choice_id=correct_id,
            )
            question_model.correct_choices.append(correct_model)

        quiz_question_model = QuizQuestionModel(
            quiz_id=quiz.quiz_id,
            question_id=q.question_id,
            position=qq.position,
            question=question_model,
        )
        quiz_model.quiz_questions.append(quiz_question_model)

    return quiz_model

