# ADR 0002: Backend Services and API Architecture

## Status
Accepted

## Context
The **Commonroom** ecosystem requires backend services capable of handling diverse workloads:
- **Hogwarts Trials**: Deterministic server-side quiz scoring, question bank administration, sorting logic, and house point transactions.
- **Pensieve**: AI agent orchestration, vector retrieval (RAG), embeddings computation, news ingestion, and streaming responses.
- **The Burrow Clock**: Realtime presence synchronization, geofence event evaluation, and strict server-side location authorization.

The architecture must support independent deployment and domain isolation without introducing a sprawling monolithic backend.

---

## Decision

We establish an independent, service-oriented backend architecture based on **Python 3.13+** and **FastAPI**:

1. **Backend Runtime & Framework**:
   - **Language**: Python 3.13+
   - **Web Framework**: **FastAPI**
   - **Data Validation & Typing**: **Pydantic**
2. **Domain Isolation**:
   - Each product owns its own independent backend service and domain logic (e.g., `apps/hogwarts-trials/api`, `apps/pensieve/api`, `apps/burrow-clock/api`).
   - There is no single monolithic Commonroom backend service.
3. **API Contract Standard**:
   - Primary communication is via **REST** with automated **OpenAPI** specification generation.
   - FastAPI-generated OpenAPI schemas will serve as the source of truth for generating or validating client-side TypeScript contracts, preventing manual contract duplication and drift.
4. **Realtime Mechanisms**:
   - **WebSockets** for bidirectional realtime interaction (e.g., The Burrow Clock presence synchronization).
   - **Server-Sent Events (SSE)** for unidirectional server-to-client streaming (e.g., Pensieve AI response token streaming).
5. **Security & Credential Boundary**:
   - All database credentials, external API keys, and LLM provider credentials must reside strictly on the backend.
   - Clients must never access or store privileged upstream provider credentials.

---

## Consequences

### Positive
- **Ecosystem Suitability**: Python provides unmatched native library support for AI, embeddings, natural language processing, vector retrieval, and data ingestion (essential for Pensieve).
- **Type Safety & Validation**: Pydantic guarantees strict runtime validation and serialization for all incoming and outgoing payloads.
- **Automated Contract Generation**: OpenAPI schemas are generated natively from FastAPI endpoints, allowing automated client SDK/type generation.
- **Independent Scaling & Deployment**: Products can be deployed, scaled, and maintained independently without coupling deployment cycles.

### Trade-offs
- The dual-language architecture (TypeScript clients and Python backends) requires automated schema translation and disciplined contract management in `packages/commonroom-core`.

---

## Alternatives Considered

1. **Node.js / NestJS Universal Backend**:
   - *Rationale for Rejection*: While Node.js would unify the language across frontend and backend, its ecosystem for AI orchestration, vector embeddings, scientific data processing, and document processing is significantly less mature and feature-complete than Python.
2. **Serverless-Only Functions (e.g., AWS Lambda / Cloud Functions)**:
   - *Rationale for Rejection*: Pure serverless architectures introduce cold-start latency issues, complex persistent WebSocket connection state management for The Burrow Clock, and potential cloud vendor lock-in during early foundation stages.
3. **Single Monolithic Commonroom Backend**:
   - *Rationale for Rejection*: A single monolith violates product domain boundaries, couples release schedules, mixes trivia logic with AI retrieval and realtime presence, and prevents independent scaling.

