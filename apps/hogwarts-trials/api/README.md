# Hogwarts Trials API

**Purpose:** This service provides the backend logic for the Hogwarts Trials application within the Commonroom ecosystem.

**Status:** This is a FastAPI backend scaffold with product-local quiz domain contracts and a deterministic grading engine.

### Implementation Scope
**Implemented:**
- Minimal FastAPI application setup
- Deterministic health endpoint (`/api/v1/health`)
- Product-local quiz domain foundation (`Question`, `QuestionChoice`, `QuestionProvenance`, `Quiz`, `QuizQuestion`, `AnswerSubmission`)
- Deterministic pure-domain grading engine (`grade_question`, `grade_quiz`, `QuestionResult`, `QuizResult`, `QuizGradingError`)
- Exact-match answer evaluation for single-choice and multiple-choice questions
- Unanswered-question handling (omitted submissions evaluated as unanswered with 0 points)
- One-point-per-question base scoring policy
- Immutable `QuestionResult` and `QuizResult` models with consistency validation
- Automated tests for health endpoint, quiz domain invariants, and grading engine

**Deferred / Unimplemented:**
- Quiz HTTP endpoints and request routing (no REST quiz endpoints yet)
- Question banks and production canon content
- Quiz sessions, progression, and state management
- Sorting Ceremony logic
- House points and progression (no house-point conversion)
- Authentication and user accounts
- Database connections and persistence (e.g., PostgreSQL)
- AI / LLM integrations
- Partial credit (none awarded)
- Difficulty weighting (none applied; all questions are 1 base point)

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
- **Current Scope**: Pure domain evaluation only. HTTP routing, persistence, lifecycle sessions, and real question banks remain explicitly deferred.

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
- `GET /api/v1/health`: Returns a JSON payload confirming service health.

### Testing

From the repository root:
```bash
uv run --project apps/hogwarts-trials/api pytest apps/hogwarts-trials/api/tests
```
