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
- **Deterministic Tooling**: `pnpm` and `uv` provide fast, deterministic package and environment management across their respective language ecosystems.
- **Strict Boundary Enforcement**: pnpm's symlink model prevents phantom dependencies in frontend apps; neutral schemas in `commonroom-core` prevent frontend and backend contract drift.
- **Minimal Cognitive Overhead**: Developers interact with native, familiar tooling (`pnpm`, `uv`) rather than learning bespoke orchestration layers.

### Trade-offs
- Multi-language task coordination across TypeScript and Python is handled via simple repository scripts and CI workflows rather than an automated distributed computation cache.

---

## Alternatives Considered

1. **npm / yarn (classic)**:
   - *Rationale for Non-Selection*: `pnpm` offers stronger isolation against phantom dependencies through its symlinked dependency layout and provides efficient disk usage across multiple workspace packages.
2. **Poetry / pip-tools / pipenv**:
   - *Rationale for Non-Selection*: `uv` provides unified virtual environment creation, fast lockfile generation, and streamlined workspace management suited for Python 3.13+.
3. **Turborepo / Nx / Bazel**:
   - *Rationale for Non-Selection*: Monorepo build orchestrators introduce additional configuration and build abstractions that are not yet necessary for the current repository size.

