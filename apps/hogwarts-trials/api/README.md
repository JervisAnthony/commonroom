# Hogwarts Trials API

**Purpose:** This service provides the backend logic for the Hogwarts Trials application within the Commonroom ecosystem.

**Status:** This is a FastAPI backend scaffold with product-local quiz domain contracts, a deterministic grading engine, a `QuizRepository` application port with in-memory and PostgreSQL adapters, Alembic database migrations, and a stateless quiz REST API.

### Implementation Scope
**Implemented:**
- Minimal FastAPI application setup
- Deterministic health endpoint (`/api/v1/health`)
- Product-local quiz domain foundation (`Question`, `QuestionChoice`, `QuestionProvenance`, `Quiz`, `QuizQuestion`, `AnswerSubmission`)
- Deterministic pure-domain grading engine (`grade_question`, `grade_quiz`, `QuestionResult`, `QuizResult`, `QuizGradingError`)
- Server-owned quiz attempt domain aggregate (`QuizAttempt`, `AttemptStatus`, `complete_attempt`, `create_quiz_attempt`, `QuizAttemptError`)
- Application repository ports (`QuizRepository` and `QuizAttemptRepository` protocols)
- Concrete in-memory repositories for quizzes and attempts (`InMemoryQuizRepository`, `InMemoryQuizAttemptRepository`)
- Concrete PostgreSQL relational repositories for quizzes and attempts (`PostgresQuizRepository`, `PostgresQuizAttemptRepository`)
- SQLAlchemy 2.x relational persistence models for quizzes and attempts (`QuizModel`, `QuestionModel`, `QuizQuestionModel`, `QuestionChoiceModel`, `QuestionCorrectChoiceModel`, `QuizAttemptModel`, `QuizAttemptQuestionResultModel`, `QuizAttemptSelectedChoiceModel`)
- Explicit domain <-> persistence mappers and snapshot reconstruction
- Alembic database migrations:
  - Revision `0001`: Relational quiz schema
  - Revision `0002`: Relational attempt lifecycle schema
- Configurable repository backend selection via environment variables (`memory` vs `postgres`, defaulting to `memory`)
- FastAPI dependency providers for repository injection (`get_quiz_repository`, `get_quiz_attempt_repository`)
- Public wire DTOs strictly preventing answer key and provenance leakage (`QuizAttemptResponse`, `QuizGradeResponse`, `QuizDetailResponse`)
- Quiz REST API (`hogwarts_trials_api.api.quizzes`):
  - `GET /api/v1/quizzes`: List available quizzes as summary items
  - `GET /api/v1/quizzes/{quiz_id}`: Retrieve a playable quiz definition
  - `POST /api/v1/quizzes/{quiz_id}/grade`: Evaluate submitted answers statelessly
  - `POST /api/v1/quizzes/{quiz_id}/attempts`: Start a new server-owned quiz attempt (returns 201 Created)
- Attempt REST API (`hogwarts_trials_api.api.attempts`):
  - `GET /api/v1/attempts/{attempt_id}`: Retrieve attempt status and evaluated result snapshot
  - `POST /api/v1/attempts/{attempt_id}/submit`: Submit final answers to complete an in-progress attempt exactly once
- One-shot attempt lifecycle (`in_progress` -> `completed`) with atomic completion transactions and row locking
- Persisted evaluated result snapshots (GET attempt does not re-grade completed attempts)
- Exact-match answer evaluation for single-choice and multiple-choice questions
- Unanswered-question handling (omitted submissions evaluated as unanswered with 0 points)
- One-point-per-question base scoring policy
- Immutable `QuestionResult`, `QuizResult`, and `QuizAttempt` models with consistency validation
- Automated test coverage for health endpoint, quiz domain, attempt domain, grading engine, in-memory repositories, PostgreSQL repositories, database migrations, and REST APIs
- GitHub Actions CI PostgreSQL service container validation

**Deferred / Unimplemented:**
- Question banks and production canon content (synthetic demonstration fixtures only)
- Repository write methods for quizzes (quiz authoring / editing remains deferred; quiz boundary is strictly read-only)
- Authentication, user accounts, and identity (no users, tokens, or permissions)
- User ownership of attempts (attempt IDs alone are NOT an authorization boundary)
- Timers, deadlines, and expiration (attempts do not expire)
- Incremental answer autosave, pause, or resume (attempts are strictly one-shot final submissions)
- Attempt cancellation or retries on the same attempt (new attempt required for resubmission)
- Persistent user score history
- House points and progression (no house-point conversion)
- Sorting Ceremony logic
- Leaderboards and rankings
- Rate limiting and cheating detection
- AI / LLM integrations
- Partial credit (none awarded)
- Difficulty weighting (none applied; all questions are 1 base point)

### Quiz Domain & Grading Engine
The API defines typed, validated, and immutable domain contracts under `hogwarts_trials_api.domain`:
- **Question and Quiz Structural Contracts**: Strictly validated questions supporting single-choice and multiple-choice types, bounded choices, and contiguous quiz question sequences.
- **Provenance Metadata**: Categorization of canonical source tiers (`book_canon`, `screen_adaptation`, `official_expanded`, `synthetic`) and curation lifecycles.
- **Answer Submission Contract**: Structured submission models validating selection constraints.
- **Deterministic Grading Engine**:
  - `grade_question`: Evaluates individual question submissions against server-owned answer keys using exact-match set equality. Unanswered questions receive 0 points.
  - `grade_quiz`: Aggregates complete quiz outcomes ordered strictly by `QuizQuestion.position`. Missing submissions are treated as unanswered. Duplicate or unknown question submissions raise `QuizGradingError`.
  - **Base Scoring Policy**: Every question is worth exactly 1 base point. No partial credit, negative marking, difficulty multipliers, or house point conversions are applied.
  - **Immutable Result Models**: `QuestionResult` and `QuizResult` enforce internal consistency across total points, max points, and status counts.

### Quiz Repository & Relational Persistence
The application accesses quiz data exclusively through the `QuizRepository` protocol in `hogwarts_trials_api.application.quiz_repository`.

- **Backend Implementations**:
  - `InMemoryQuizRepository` (default): Holds immutable synthetic demonstration quizzes in memory for fast local development and testing without requiring database infrastructure.
  - `PostgresQuizRepository`: Synchronous PostgreSQL-backed adapter querying relational persistence models via SQLAlchemy 2.x and reconstructing detached domain models via an explicit mapper.
- **Backend Selection**:
  The backend is selected via environment variables:
  - `HOGWARTS_TRIALS_QUIZ_REPOSITORY`: Backend selector (`memory` or `postgres`, defaults to `memory`).
  - `HOGWARTS_TRIALS_DATABASE_URL`: Connection string required only when `HOGWARTS_TRIALS_QUIZ_REPOSITORY=postgres`.
  Format:
  ```
  postgresql+psycopg://user:password@host:5432/database
  ```
- **Engine Isolation**: Memory mode constructs no SQLAlchemy engine, requires no database URL, and attempts no network connections.
- **Relational Schema**:
  The relational model separates concern into five explicit tables:
  - `quizzes`: Quiz metadata (`quiz_id`, `title`, `description`).
  - `questions`: Question metadata, prompt, difficulty, source tier, curation status, and explanation.
  - `quiz_questions`: Associative membership linking quizzes and questions with contiguous 1-based `position`.
  - `question_choices`: Individual choices with ordered 1-based `position`.
  - `question_correct_choices`: Association table storing server-owned answer keys.
- **Read-Only Boundary**: The `QuizRepository` interface currently provides only `list_quizzes()` and `get_quiz(quiz_id)`. Write operations, authoring mutations, and user submissions are not persisted at this boundary.

### Database Migrations (Alembic)
Database migrations are managed via Alembic under `apps/hogwarts-trials/api`:
- **Run migrations up to latest:**
  ```bash
  HOGWARTS_TRIALS_DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/database" \
  uv run --project apps/hogwarts-trials/api alembic -c apps/hogwarts-trials/api/alembic.ini upgrade head
  ```
- **Rollback migrations to base:**
  ```bash
  HOGWARTS_TRIALS_DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/database" \
  uv run --project apps/hogwarts-trials/api alembic -c apps/hogwarts-trials/api/alembic.ini downgrade base
  ```

### Quiz & Attempt REST API & Security Invariants
The REST API under `hogwarts_trials_api.api` connects the application repository ports (`QuizRepository`, `QuizAttemptRepository`) and domain grading engine to HTTP clients:
- **Repository Seams**: Endpoints consume repository abstractions via FastAPI dependency injection (`get_quiz_repository`, `get_quiz_attempt_repository`), decoupling HTTP routing from the choice of storage backend.
- `GET /api/v1/quizzes`: Returns a list of `QuizSummaryResponse` objects (`quiz_id`, `title`, `description`, `question_count`).
- `GET /api/v1/quizzes/{quiz_id}`: Returns a playable `QuizDetailResponse`. Questions and choices are exposed without `correct_choice_ids`, `explanation`, `provenance`, or curation metadata.
- `POST /api/v1/quizzes/{quiz_id}/grade`: Stateless grading endpoint. Evaluates submitted answers via `grade_quiz` without persisting state, strictly omitting answer keys. Retained for backwards compatibility, simple development, and stateless evaluation.
- `POST /api/v1/quizzes/{quiz_id}/attempts`: Creates a server-owned `in_progress` attempt for the specified quiz, returning 201 Created with a server-generated UUID v4 `attempt_id` and `result: null`.
- `GET /api/v1/attempts/{attempt_id}`: Retrieves the state of an attempt. Returns `status: "in_progress"` with `result: null` for active attempts, or `status: "completed"` with the evaluated `QuizGradeResponse` snapshot for completed attempts.
- `POST /api/v1/attempts/{attempt_id}/submit`: Submits final answers for an in-progress attempt exactly once. The attempt is graded via `complete_attempt` and marked `completed` in an atomic database transaction. Resubmitting a completed attempt returns `409 Conflict`.
- **Persisted Result Snapshots**: Completed attempts persist evaluated question outcomes and selections so that subsequent `GET /api/v1/attempts/{attempt_id}` requests retrieve the snapshot without recalculating or re-grading.
- **Answer-Key Secrecy**: The public API strictly guarantees that server-owned answer keys (`correct_choice_ids`) and editorial explanations are never returned to clients across all endpoints.
- **Authorization & Security Boundary Notice**: Attempt identifiers are high-entropy UUID v4 values generated server-side. However, **attempt IDs alone are NOT an authorization boundary**. Until authentication and user accounts are introduced in future commits, possessing an attempt UUID is not equivalent to secure identity or ownership.
- **Synthetic Fixture Notice**: Demonstration questions (basic math, shapes, prime numbers) are synthetic placeholders enabling development without using copyrighted franchise material.

### Requirements
- Python >= 3.13
- `uv` for workspace management

### Local Development

**Installation:**
The project dependencies are managed at the monorepo root workspace using `uv`.
```bash
uv sync --all-packages
```

**Running the Server (In-Memory Default):**
From the repository root:
```bash
uv run --project apps/hogwarts-trials/api uvicorn hogwarts_trials_api.main:app --reload
```
The server will start at `http://127.0.0.1:8000`.

**Running the Server (PostgreSQL Backend):**
```bash
HOGWARTS_TRIALS_QUIZ_REPOSITORY=postgres \
HOGWARTS_TRIALS_DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/database" \
uv run --project apps/hogwarts-trials/api uvicorn hogwarts_trials_api.main:app --reload
```

**Endpoints:**
- `GET /api/v1/health`: Returns service health status.
- `GET /api/v1/quizzes`: Lists available quiz summaries.
- `GET /api/v1/quizzes/{quiz_id}`: Retrieves playable quiz definition.
- `POST /api/v1/quizzes/{quiz_id}/grade`: Stateless grading endpoint (backwards compatible).
- `POST /api/v1/quizzes/{quiz_id}/attempts`: Starts a new server-owned quiz attempt (201 Created).
- `GET /api/v1/attempts/{attempt_id}`: Retrieves quiz attempt status and result snapshot.
- `POST /api/v1/attempts/{attempt_id}/submit`: Submits final answers and completes attempt.

### Testing

From the repository root:
```bash
uv run --project apps/hogwarts-trials/api pytest apps/hogwarts-trials/api/tests
```

**Running with PostgreSQL Integration Tests:**
When a dedicated PostgreSQL test instance is available, specify `HOGWARTS_TRIALS_TEST_DATABASE_URL`:
```bash
HOGWARTS_TRIALS_TEST_DATABASE_URL="postgresql+psycopg://test_user:test_password@localhost:5432/test_db" \
uv run --project apps/hogwarts-trials/api pytest apps/hogwarts-trials/api/tests
```
When `HOGWARTS_TRIALS_TEST_DATABASE_URL` is unset, PostgreSQL integration tests are skipped safely while all unit tests run and pass.
