# Hogwarts Trials

**Hogwarts Trials** is an academic trivia and wizarding knowledge application within the Commonroom ecosystem.

## Applications

- [Web Client](./web/README.md) - The playable Next.js public practice-quiz frontend.
- [API Backend](./api/README.md) - The FastAPI backend service, quiz domain model, deterministic grading engine, and quiz REST API.

## Implementation Status

**Implemented:**
- Responsive Next.js discovery, quiz player, server-graded results and selection review
- Product-local same-origin API handlers using server-only `HOGWARTS_TRIALS_API_URL`
- Single/multiple-choice selection, skip/revisit, unanswered notices, retry without lost answers, and fresh replay
- Native Node tests for quiz state and public integration boundaries, included in web CI
- FastAPI API scaffold
- Typed quiz-domain contracts
- Deterministic base grading/scoring engine
- First quiz REST surface (quiz discovery, playable quiz detail, stateless grading)
- Synthetic API demonstration catalog
- Quiz and attempt repository ports with in-memory and PostgreSQL persistence
- Alembic migrations and one-shot attempt lifecycle with persisted result snapshots
- Separate immutable attempt ownership, enforced before GET/submit reads
- Fail-closed trusted-principal dependency: stateful attempt routes default to 401; authenticated non-owners and legacy unowned attempts receive generic 404
- Public quiz discovery/detail/stateless grading; public attempt DTOs omit owner identity

**Still Deferred:**
- Real curated question bank
- Actual OAuth/OIDC provider integration and token validation
- Users/accounts persistence, registration/login/logout, and frontend authentication
- Account/profile management, roles/admin authorization, and attempt history by user
- Persistent user score history
- Sorting ceremony
- House points
- Leaderboards
- Competitive-exam integrity controls
- Authenticated frontend gameplay and saved player progression (current public grading is stateless)

## Public practice experience

The `/` catalog and `/quizzes/[quizId]` player use only public discovery,
detail and `POST /api/v1/quizzes/{quiz_id}/grade`. Results are server-authoritative
and remain in browser memory for the current run. Protected attempt routes,
authentication and saved progression are deferred. The current catalog contains
synthetic demonstration questions, not curated Harry Potter canon; answer keys
and explanations are not exposed.

For local startup, run `uv sync --frozen --all-packages --group dev`, then
`uv run --package hogwarts-trials-api uvicorn hogwarts_trials_api.main:app --reload`
from the root. In another terminal set
`HOGWARTS_TRIALS_API_URL=http://127.0.0.1:8000`, then run
`pnpm --filter hogwarts-trials-web run dev`. The web client serves on port 3000;
the API serves on port 8000. Missing or unavailable backend configuration gives
a controlled runtime error with retry; builds do not contact the API.
See the [web guide](./web/README.md) for configuration, endpoint mappings,
troubleshooting and lint/typecheck/test/build commands.

## Product Scope & Boundaries

- **Domain Responsibilities**: Quiz engine, question banks, quiz scoring, difficulty progression, sorting ceremony, house points earned via quiz activity, and competitive examinations (O.W.L.s / N.E.W.T.s).
- **Non-Responsibilities**: Live news aggregation, general-purpose conversational AI assistants, or friend location tracking.
