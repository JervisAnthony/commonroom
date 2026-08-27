# Commonroom Core (`commonroom-core`)
Shared contracts, domain types, interfaces, and cross-application primitives for the **Commonroom** ecosystem.

## Package Philosophy & Boundaries
- **Inclusion Criteria**: Only concepts and contracts actively shared across two or more applications belong here (e.g., User Identity, Wizarding Profile, House Enums, Notification and Privacy Primitives).
- **Not a Dumping Ground**: Application-specific business logic, UI components, and domain calculations must remain inside their respective `apps/*` packages.
- **Dependency Invariant**: Applications depend on `commonroom-core` (`apps/* -> packages/commonroom-core`); `commonroom-core` must never depend on any application.

*Note: Shared domain models and schemas will be introduced in subsequent commits.*

