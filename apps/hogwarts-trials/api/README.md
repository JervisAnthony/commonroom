# Hogwarts Trials API

**Purpose:** This service provides the backend logic for the Hogwarts Trials application within the Commonroom ecosystem.

**Status:** This is a FastAPI backend scaffold with product-local quiz domain contracts, a deterministic grading engine, a `QuizRepository` application port with in-memory and PostgreSQL adapters, Alembic database migrations, and a stateless quiz REST API.

### Implementation Scope
**Implemented:**
- Minimal FastAPI application setup
- Deterministic health endpoint (`/api/v1/health`)
- Product-local quiz domain foundation (`Question`, `QuestionChoice`, `QuestionProvenance`, `Quiz`, `QuizQuestion`, `AnswerSubmission`)
- Deterministic pure-domain grading engine (`grade_question`, `grade_quiz`, `QuestionResult`, `QuizResult`, `QuizGradingError`)
- Application repository port (`QuizRepository` protocol in `hogwarts_trials_api.application.quiz_repository`)
- Concrete in-memory synthetic demonstration quiz repository (`hogwarts_trials_api.infrastructure.in_memory_quiz_repository`)
- Concrete PostgreSQL relational quiz repository adapter (`hogwarts_trials_api.infrastructure.postgres_quiz_repository`)
- SQLAlchemy 2.x relational persistence models (`QuizModel`, `QuestionModel`, `QuizQuestionModel`, `QuestionChoiceModel`, `QuestionCorrectChoiceModel`)
- Explicit domain <-> persistence mapper (`hogwarts_trials_api.infrastructure.quiz_mapper`)
- Initial Alembic database migration for relational quiz schema (`alembic/versions/0001_initial_quiz_schema.py`)
- Configurable repository backend selection via environment variables (`memory` vs `postgres`, defaulting to `memory`)
- FastAPI dependency provider for repository injection (`hogwarts_trials_api.api.dependencies`)
- Public wire DTOs strictly preventing answer key and provenance leakage (`hogwarts_trials_api.api.schemas`)
- Stateless quiz REST API consuming repository port (`hogwarts_trials_api.api.quizzes`):
  - `GET /api/v1/quizzes`: List available quizzes as summary items
  - `GET /api/v1/quizzes/{quiz_id}`: Retrieve a playable quiz definition
  - `POST /api/v1/quizzes/{quiz_id}/grade`: Evaluate submitted answers statelessly
- Exact-match answer evaluation for single-choice and multiple-choice questions
- Unanswered-question handling (omitted submissions evaluated as unanswered with 0 points)
- One-point-per-question base scoring policy
- Immutable `QuestionResult` and `QuizResult` models with consistency validation
- Automated test coverage for health endpoint, quiz domain invariants, grading engine, in-memory repository, PostgreSQL repository adapter, domain-persistence mapper, configuration parsing, grading parity, and quiz REST API
- GitHub Actions CI PostgreSQL service container validation

**Deferred / Unimplemented:**
- Question banks and production canon content (synthetic demonstration fixtures only)
- Repository write methods (quiz authoring / editing remains deferred; repository boundary is strictly read-only)
- Quiz sessions, progression, and state management (no attempt lifecycle or mutable attempts)
- Sorting Ceremony logic
- House points and progression (no house-point conversion)
- Authentication and user accounts (no users, tokens, or permissions)
- User persistence or user-associated score records
- AI / LLM integrations
- Partial credit (none awarded)
- Difficulty weighting (none applied; all questions are 1 base point)
- Secure competitive examination controls (rate limiting, attempt lock-in, timed sessions)

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

### Quiz REST API & Security Invariants
The REST API under `hogwarts_trials_api.api` connects the application repository port (`QuizRepository`) and domain grading engine to HTTP clients:
- **Repository Seam**: Endpoints consume `QuizRepository` via FastAPI dependency injection (`get_quiz_repository`), decoupling HTTP routing from the choice of repository backend.
- `GET /api/v1/quizzes`: Returns a list of `QuizSummaryResponse` objects (`quiz_id`, `title`, `description`, `question_count`).
- `GET /api/v1/quizzes/{quiz_id}`: Returns a playable `QuizDetailResponse`. Questions and choices are exposed without `correct_choice_ids`, `explanation`, `provenance`, or curation metadata.
- `POST /api/v1/quizzes/{quiz_id}/grade`: Accepts `QuizGradeRequest` containing zero or more `AnswerSubmission` records. Missing question submissions are treated as unanswered. Evaluates via `grade_quiz` and returns `QuizGradeResponse` indicating status (`correct`, `incorrect`, `unanswered`) and awarded points, while strictly omitting server-side answer keys.
- **Answer-Key Secrecy**: The public API strictly guarantees that server-owned answer keys (`correct_choice_ids`) and editorial explanations are never returned to clients, whether using the in-memory or PostgreSQL repository.
- **Statelessness**: No attempt IDs, session records, or progress state are persisted. Each grade request is evaluated statelessly and deterministically.
- **Synthetic Fixture Notice**: The demonstration questions (basic math, shapes, prime numbers) are synthetic placeholders enabling development without using copyrighted franchise material.

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
- `POST /api/v1/quizzes/{quiz_id}/grade`: Grades submitted answers statelessly.

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
