# Hogwarts Trials

**Hogwarts Trials** is an academic trivia and wizarding knowledge application within the Commonroom ecosystem.

## Applications

- [Web Client](./web/README.md) - The Next.js frontend application (currently a scaffold).
- [API Backend](./api/README.md) - The FastAPI backend service, quiz domain model, deterministic grading engine, and quiz REST API.

## Implementation Status

**Implemented:**
- Next.js web scaffold
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
- Final frontend gameplay integration

## Product Scope & Boundaries
- **Domain Responsibilities**: Quiz engine, question banks, quiz scoring, difficulty progression, sorting ceremony, house points earned via quiz activity, and competitive examinations (O.W.L.s / N.E.W.T.s).
- **Non-Responsibilities**: Live news aggregation, general-purpose conversational AI assistants, or friend location tracking.
