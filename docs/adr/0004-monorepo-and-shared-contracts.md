# ADR 0004: Monorepo Tooling and Shared Contract Strategy

## Status
Accepted

## Context
The **Commonroom** monorepo contains multi-language codebases:
- TypeScript client applications in `apps/` (Next.js web apps and React Native / Expo mobile app).
- Python backend services in `apps/` (FastAPI services).
- Shared contracts, types, and privacy/domain schemas in `packages/commonroom-core`.

To ensure efficient local development, fast CI runs, and clean dependency boundaries, we need standard tooling for both TypeScript and Python workspaces without introducing heavy, premature monorepo orchestration frameworks.

---

## Decision

We establish **pnpm workspaces** for TypeScript/JavaScript, **uv** for Python, and a **technology-neutral schema strategy** for `commonroom-core`:

1. **TypeScript Workspace Management**:
   - **`pnpm`** with pnpm workspaces is the approved package manager for all TypeScript and Node-based projects.
   - Provides strict, non-flat `node_modules` structure, rapid disk-efficient content-addressable storage, and robust workspace protocol (`workspace:*`).
2. **Python Environment & Package Management**:
   - **`uv`** is the approved tool for Python virtual environment creation, package resolution, and lockfile management.
   - Offers extremely fast dependency resolution and standardized workspace management for Python 3.13+.
3. **Shared Contract Strategy (`packages/commonroom-core`)**:
   - `packages/commonroom-core` remains the single source of truth for cross-product domain contracts (identity, profiles, house enums, friendship contracts, privacy primitives).
   - Contracts are defined in **technology-neutral formats** such as **OpenAPI specifications**, **JSON Schema**, and versioned schema documents.
   - Language-specific representations (TypeScript types, Pydantic models) will be generated or adapted from these neutral source contracts.
   - `commonroom-core` must **never** become an npm-only or Python-only package.
4. **No Heavy Monorepo Orchestration Initially**:
   - We explicitly defer complex monorepo build tools (e.g., Turborepo, Nx, Bazel, Pants).
   - At the current repository scale, standard workspace scripts and `scripts/validate_repository.py` provide full validation and build management without additional configuration overhead.

---

## Consequences

### Positive
- **Deterministic Tooling**: `pnpm` and `uv` represent state-of-the-art package management in their respective language ecosystems.
- **Strict Boundary Enforcement**: pnpm's symlink model prevents phantom dependencies in frontend apps; neutral schemas in `commonroom-core` prevent frontend and backend contract drift.
- **Minimal Cognitive Overhead**: Developers interact with native, familiar tooling (`pnpm`, `uv`) rather than learning bespoke orchestration layers.

### Trade-offs
- Multi-language task coordination across TypeScript and Python is handled via simple repository scripts and CI workflows rather than an automated distributed computation cache.

---

## Alternatives Considered

1. **npm / yarn**:
   - *Rationale for Rejection*: Standard `npm` and `yarn` (classic) suffer from flat `node_modules` hoisting issues (phantom dependencies) and slower installation speeds compared to `pnpm`.
2. **Poetry / pip-tools / pipenv**:
   - *Rationale for Rejection*: `uv` provides orders-of-magnitude faster dependency resolution, native cross-platform lockfiles, and direct integration with Python 3.13+ without legacy configuration quirks.
3. **Turborepo / Nx / Bazel**:
   - *Rationale for Rejection*: Introducing complex monorepo orchestrators adds significant configuration boilerplate and maintenance overhead before the codebase scale justifies distributed caching or task-graph pipelines.

