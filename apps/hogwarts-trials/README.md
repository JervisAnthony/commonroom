# Hogwarts Trials

**Hogwarts Trials** is an academic trivia and wizarding knowledge application within the Commonroom ecosystem.

## Applications

- [Web Client](./web/README.md) - The Next.js frontend application (currently a scaffold).
- [API Backend](./api/README.md) - The FastAPI backend service and quiz domain model.

*Note: The frontend and API scaffolds exist, along with typed quiz-domain contracts. However, full product functionality remains under development. The deterministic grading/scoring engine, quiz REST endpoints, persistence/database, authentication, curated question banks, sorting ceremony, and house points remain deferred.*

## Product Scope & Boundaries
- **Domain Responsibilities**: Quiz engine, question banks, quiz scoring, difficulty progression, sorting ceremony, house points earned via quiz activity, and competitive examinations (O.W.L.s / N.E.W.T.s).
- **Non-Responsibilities**: Live news aggregation, general-purpose conversational AI assistants, or friend location tracking.
