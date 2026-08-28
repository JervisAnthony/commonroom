# Commonroom Core (`commonroom-core`)

Shared data contracts, domain types, and cross-application primitives for the **Commonroom** ecosystem.

---

## 1. Role and Boundaries

`packages/commonroom-core` is the single source of truth for cross-product domain contracts shared between Hogwarts Trials, Pensieve, and The Burrow Clock.

### What Belongs Here
- Shared domain contracts consumed by $\ge 2$ applications (e.g., User Identity references, House enums, ApiError envelopes, privacy/consent primitives).
- Technology-neutral schema definitions and manifests under [`schemas/`](schemas/).

### What Explicitly Does NOT Belong Here
- ❌ Application-specific business logic (e.g., quiz grading algorithms, AI prompting logic, geofence computations).
- ❌ UI components or framework code.
- ❌ Database models, migrations, or ORM definitions.
- ❌ Direct dependencies on or imports from any `apps/*` directory.

---

## 2. Technology-Neutral Source of Truth

- **Canonical Format**: All domain contracts are authored as neutral **JSON Schema (Draft 2020-12)** documents located in [`schemas/v1/`](schemas/v1/).
- **Language Adapters**: Future language-specific representations (e.g., TypeScript types, Python Pydantic models) may be generated or adapted from these neutral schemas, but generated artifacts must **never** replace the JSON Schema files as the canonical source of truth.
- **Independent Consumption**: Applications import or generate types from `commonroom-core` contracts (`apps/* -> packages/commonroom-core`). Applications must never directly access or modify peer applications' internal contracts.

---

## 3. Schema Directory & Manifest

All shared schemas are cataloged in the schema manifest:
- **Directory**: [`schemas/`](schemas/)
- **Manifest**: [`schemas/manifest.json`](schemas/manifest.json)
- **Schema Documentation**: [`schemas/README.md`](schemas/README.md)
