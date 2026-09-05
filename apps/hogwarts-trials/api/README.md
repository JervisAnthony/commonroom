# Hogwarts Trials API

**Purpose:** This service provides the backend logic for the Hogwarts Trials application within the Commonroom ecosystem.

**Status:** This is a FastAPI backend scaffold with product-local quiz domain contracts, a deterministic grading engine, and a stateless quiz REST API.

### Implementation Scope
**Implemented:**
- Minimal FastAPI application setup
- Deterministic health endpoint (`/api/v1/health`)
- Product-local quiz domain foundation (`Question`, `QuestionChoice`, `QuestionProvenance`, `Quiz`, `QuizQuestion`, `AnswerSubmission`)
- Deterministic pure-domain grading engine (`grade_question`, `grade_quiz`, `QuestionResult`, `QuizResult`, `QuizGradingError`)
- Synthetic in-memory demonstration quiz catalog (`hogwarts_trials_api.application.quiz_catalog`)
- Public wire DTOs strictly preventing answer key and provenance leakage (`hogwarts_trials_api.api.schemas`)
- Stateless quiz REST API (`hogwarts_trials_api.api.quizzes`):
  - `GET /api/v1/quizzes`: List available quizzes as summary items
  - `GET /api/v1/quizzes/{quiz_id}`: Retrieve a playable quiz definition
  - `POST /api/v1/quizzes/{quiz_id}/grade`: Evaluate submitted answers statelessly
- Exact-match answer evaluation for single-choice and multiple-choice questions
- Unanswered-question handling (omitted submissions evaluated as unanswered with 0 points)
- One-point-per-question base scoring policy
- Immutable `QuestionResult` and `QuizResult` models with consistency validation
- Automated tests for health endpoint, quiz domain invariants, grading engine, and quiz REST API

**Deferred / Unimplemented:**
- Question banks and production canon content (synthetic demonstration fixtures only)
- Quiz sessions, progression, and state management (no attempt lifecycle or mutable attempts)
- Sorting Ceremony logic
- House points and progression (no house-point conversion)
- Authentication and user accounts (no users, tokens, or permissions)
- Database connections and persistence (e.g., PostgreSQL)
- AI / LLM integrations
- Partial credit (none awarded)
- Difficulty weighting (none applied; all questions are 1 base point)
- Secure competitive examination controls (rate limiting, attempt lock-in, timed sessions)

### Quiz Domain & Grading Engine
The API defines typed, validated, and immutable domain contracts under `hogwarts_trials_api.domain`:
- **Question and Quiz Structural Contracts**: Strictly validated questions supporting single-choice and multiple-choice types, bounded choices, and contiguous quiz question sequences.
- **Provenance Metadata**: Categorization of canonical source tiers (`book_canon`, `screen_adaptation`, `official_expanded`) and curation lifecycles.
- **Answer Submission Contract**: Structured submission models validating selection constraints.
- **Deterministic Grading Engine**:
  - `grade_question`: Evaluates individual question submissions against server-owned answer keys using exact-match set equality. Unanswered questions receive 0 points.
  - `grade_quiz`: Aggregates complete quiz outcomes ordered strictly by `QuizQuestion.position`. Missing submissions are treated as unanswered. Duplicate or unknown question submissions raise `QuizGradingError`.
  - **Base Scoring Policy**: Every question is worth exactly 1 base point. No partial credit, negative marking, difficulty multipliers, or house point conversions are applied.
  - **Immutable Result Models**: `QuestionResult` and `QuizResult` enforce internal consistency across total points, max points, and status counts.

### Quiz REST API & Security Invariants
The REST API under `hogwarts_trials_api.api` connects the application catalog and domain grading engine to HTTP clients:
- `GET /api/v1/quizzes`: Returns a list of `QuizSummaryResponse` objects (`quiz_id`, `title`, `description`, `question_count`).
- `GET /api/v1/quizzes/{quiz_id}`: Returns a playable `QuizDetailResponse`. Questions and choices are exposed without `correct_choice_ids`, `explanation`, `provenance`, or curation metadata.
- `POST /api/v1/quizzes/{quiz_id}/grade`: Accepts `QuizGradeRequest` containing zero or more `AnswerSubmission` records. Missing question submissions are treated as unanswered. Evaluates via `grade_quiz` and returns `QuizGradeResponse` indicating status (`correct`, `incorrect`, `unanswered`) and awarded points, while strictly omitting server-side answer keys.
- **Answer-Key Secrecy**: The public API strictly guarantees that server-owned answer keys (`correct_choice_ids`) and editorial explanations are never returned to clients.
- **Statelessness**: No attempt IDs, session records, or progress state are persisted. Each grade request is evaluated statelessly and deterministically.
- **Synthetic Fixture Notice**: The in-memory catalog contains synthetic demonstration questions (e.g., basic math, shapes, prime numbers) to enable API testing and development without using copyrighted franchise material.
- **Competitive Integrity Notice**: In the absence of authentication, attempt lifecycle tracking, rate limiting, and persistence, this stateless API is not yet suitable for secure competitive examination modes where clients could guess answers.

### Requirements
- Python >= 3.13
- `uv` for workspace management

### Local Development

**Installation:**
The project dependencies are managed at the monorepo root workspace using `uv`.
```bash
uv sync
```

**Running the Server:**
From the repository root:
```bash
uv run --project apps/hogwarts-trials/api uvicorn hogwarts_trials_api.main:app --reload
```
The server will start at `http://127.0.0.1:8000`.

**Endpoints:**
- `GET /api/v1/health`: Returns service health status.
- `GET /api/v1/quizzes`: Lists available quiz summaries.
- `GET /api/v1/quizzes/{quiz_id}`: Retrieves playable quiz definition.
- `POST /api/v1/quizzes/{quiz_id}/grade`: Grades submitted answers statelessly.

### Testing

From the repository root:
```bash
uv run --project apps/hogwarts-trials/api pytest apps/hogwarts-trials/api/tests
```
