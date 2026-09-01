# Development Toolchain & Monorepo Baseline

This document specifies the development runtimes, package managers, workspace configuration, and local validation workflow for the **Commonroom** monorepo.

---

## 1. Approved Runtime & Tooling Pins

| Dimension | Pinned Standard | Specification Location | Enforcement Mechanism |
| :--- | :--- | :--- | :--- |
| **Node.js Runtime** | `24.20.0` (LTS) | [`.node-version`](../.node-version) | Local NVM/asdf/mise, CI setup-node |
| **TypeScript/JS Package Manager** | `pnpm@11.21.0` | [`package.json`](../package.json) | Corepack, CI setup-node |
| **Python Runtime** | `3.13` (Development Baseline) | [`.python-version`](../.python-version) | Local pyenv/uv, CI setup-python |
| **Python Package Manager** | `uv >=0.12,<0.13` | [`pyproject.toml`](../pyproject.toml) | Local uv, CI setup-uv |

---

## 2. Workspace Architecture

The monorepo coordinates both TypeScript/JavaScript and Python environments through native workspace mechanisms without adding heavy external orchestrators:

1. **pnpm Workspace (`pnpm-workspace.yaml`)**:
   - Defines future package boundaries (`apps/*/web`, `apps/*/mobile`, `packages/*`).
   - `packages/commonroom-core` remains a technology-neutral contract layer and does not become an npm package unless a `package.json` is explicitly introduced.
2. **uv Python Workspace (`pyproject.toml`)**:
   - Configured as a virtual non-package workspace root (`package = false`).
   - Declares the future member glob `apps/*/api` without requiring empty or placeholder packages to exist today.
3. **Lockfile Policy**:
   - Both [`pnpm-lock.yaml`](../pnpm-lock.yaml) and [`uv.lock`](../uv.lock) are checked into version control to ensure deterministic, reproducible builds across local machines and CI.

---

## 3. Package Management Rules

- **JavaScript / TypeScript**: Always use **`pnpm`**. Do not use `npm` or `yarn` for workspace package management.
- **Python**: Always use **`uv`**. Do not use `pip`, `poetry`, or `pipenv` for managed Commonroom project dependencies.
- **Bootstrapping**: Bootstrapping the package managers themselves (e.g., via Corepack or standalone installer) is separate from managing project dependencies.

---

## 4. Local Environment Setup & Verification

### Step 1: Verify Runtimes
```bash
node --version
python --version
```

### Step 2: Enable & Verify Package Managers
```bash
# Enable pnpm via Corepack
corepack enable
pnpm --version

# Verify uv
uv --version
```

### Step 3: Verify Lockfiles & Workspaces
```bash
# Verify pnpm workspace
pnpm install --frozen-lockfile --ignore-scripts

# Verify uv workspace
uv lock --check
```

### Step 4: Run Repository Validators
```bash
python scripts/validate_contract_schemas.py
python scripts/validate_toolchain.py
python scripts/validate_repository.py
```

---

## 5. Current Implementation State

> **Note**: Initial application scaffolding for the Hogwarts Trials web client and FastAPI backend has begun. Other applications (`apps/pensieve`, `apps/burrow-clock`) currently contain conceptual architecture documentation and do not contain runnable client or backend code.

### Step 5: Hogwarts Trials Web Application

From the repository root:

```bash
pnpm --filter hogwarts-trials-web dev
pnpm --filter hogwarts-trials-web lint
pnpm --filter hogwarts-trials-web typecheck
pnpm --filter hogwarts-trials-web build
```

### Step 6: Hogwarts Trials API

From the repository root:

```bash
uv run --project apps/hogwarts-trials/api pytest apps/hogwarts-trials/api/tests
uv run --project apps/hogwarts-trials/api uvicorn hogwarts_trials_api.main:app --reload
```
