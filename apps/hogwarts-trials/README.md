# Hogwarts Trials

**Hogwarts Trials** is an academic trivia and wizarding knowledge application within the Commonroom ecosystem.

## Applications

- [Web Client](./web/README.md) - The Next.js frontend application (currently a scaffold).
- [API Backend](./api/README.md) - The FastAPI backend service, quiz domain model, and deterministic grading engine.

## Implementation Status

**Implemented:**
- Next.js web scaffold
- FastAPI API scaffold
- Typed quiz-domain contracts
- Deterministic base grading/scoring engine

**Still Deferred:**
- Quiz REST endpoints
- Persistence/database
- Curated question bank
- Authentication
- Quiz attempt/session lifecycle
- Sorting ceremony
- House points
- Leaderboards
- Final frontend gameplay integration

## Product Scope & Boundaries
- **Domain Responsibilities**: Quiz engine, question banks, quiz scoring, difficulty progression, sorting ceremony, house points earned via quiz activity, and competitive examinations (O.W.L.s / N.E.W.T.s).
- **Non-Responsibilities**: Live news aggregation, general-purpose conversational AI assistants, or friend location tracking.
