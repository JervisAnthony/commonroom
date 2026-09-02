# Hogwarts Trials API

**Purpose:** This service provides the backend logic for the Hogwarts Trials application within the Commonroom ecosystem.

**Status:** This is a FastAPI backend scaffold with product-local quiz domain contracts.

### Implementation Scope
**Implemented:**
- Minimal FastAPI application setup
- Deterministic health endpoint (`/api/v1/health`)
- Product-local quiz domain foundation (`Question`, `QuestionChoice`, `QuestionProvenance`, `Quiz`, `QuizQuestion`, `AnswerSubmission`)
- Automated tests for health endpoint and quiz domain invariants

**Deferred / Unimplemented:**
- Deterministic grading and scoring engine
- Quiz HTTP endpoints and request routing
- Question banks and real canon content
- Quiz sessions, progression, and state management
- Sorting Ceremony logic
- House points and progression
- Authentication and user accounts
- Database connections and persistence (e.g., PostgreSQL)
- AI / LLM integrations

### Quiz Domain Foundation
The API defines a typed, validated, and immutable domain model under `hogwarts_trials_api.domain`:
- **Question and Quiz Structural Contracts**: Strictly validated questions supporting single-choice and multiple-choice types, bounded choices, and contiguous quiz question sequences.
- **Provenance Metadata**: Categorization of canonical source tiers (`book_canon`, `screen_adaptation`, `official_expanded`) and curation lifecycles.
- **Answer Submission Contract**: Structured submission models validating selection constraints.
- **Validation-Only Phase**: This stage focuses purely on structural and invariant validation. Scoring/grading policies, REST exposure, persistence, and production question banks remain explicitly deferred.

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
