# Architecture Decision Records (ADRs)

This directory contains the Architecture Decision Records for the **Commonroom** ecosystem.

## Index of Architecture Decision Records

| ADR | Title | Status | Date / Scope |
| :--- | :--- | :---: | :--- |
| [ADR 0001](0001-client-platforms.md) | Client Platform Strategy (Next.js & React Native / Expo) | **Accepted** | Commit 3 — Tech Architecture |
| [ADR 0002](0002-backend-and-api.md) | Backend Services and API Architecture (Python, FastAPI, OpenAPI) | **Accepted** | Commit 3 — Tech Architecture |
| [ADR 0003](0003-data-and-retrieval.md) | Primary Datastore and Vector Retrieval (PostgreSQL + pgvector) | **Accepted** | Commit 3 — Tech Architecture |
| [ADR 0004](0004-monorepo-and-shared-contracts.md) | Monorepo Tooling and Shared Contract Strategy (pnpm, uv, OpenAPI/JSON Schema) | **Accepted** | Commit 3 — Tech Architecture |

---

## ADR Format and Lifecycle

Each Architecture Decision Record documents an architectural decision along with its context, rationale, consequences, and alternatives considered:

1. **Title**: Numbered sequentially (`NNNN-title.md`).
2. **Status**: Proposed, Accepted, Deprecated, or Superseded.
3. **Context**: The problem statement and environmental context driving the decision.
4. **Decision**: The chosen technical direction and architectural boundaries.
5. **Consequences**: Positive effects, trade-offs, and downstream impacts.
6. **Alternatives Considered**: Options evaluated and the rationale for not selecting them as the baseline.

For a comprehensive overview of the full system architecture, see [docs/technology-architecture.md](../technology-architecture.md).

