# Hogwarts Trials API

**Purpose:** This service provides the backend logic for the Hogwarts Trials application within the Commonroom ecosystem.

**Status:** This is an initial FastAPI infrastructure scaffold.

### Implementation Scope
**Implemented:**
- Minimal FastAPI application setup
- Deterministic health endpoint (`/api/v1/health`)
- Automated tests

**Deferred / Unimplemented:**
- Quiz engine and question banks
- Quiz sessions and scoring
- Sorting Ceremony logic
- House points and progression
- Authentication and user accounts
- Database connections and persistence (e.g., PostgreSQL)
- AI / LLM integrations

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
