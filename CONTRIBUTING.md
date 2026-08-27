# Contributing to Commonroom

Thank you for contributing to **Commonroom**! This document outlines our development workflow, branching model, quality standards, and governance rules.

---

## 1. Development Workflow

All contributions follow a structured, branch-and-PR workflow:

```text
main
  ↓
feature/<focused-work-unit>
  ↓
Pull Request
  ↓
Review + validation
  ↓
Squash merge
  ↓
main
```

### Branch Naming Conventions
Use descriptive, hyphenated branch names prefixed with the work category:
- `feature/<description>` — New capabilities or architectural modules (e.g., `feature/hogwarts-trials-quiz-engine`)
- `fix/<description>` — Bug fixes or issue resolutions (e.g., `fix/link-validator-windows-paths`)
- `docs/<description>` — Documentation improvements or additions (e.g., `docs/add-api-specs`)
- `chore/<description>` — Maintenance, governance, or tooling tasks (e.g., `chore/repository-governance-ci`)

---

## 2. Contribution Rules & Invariants

To maintain stability, product boundaries, and code quality across the ecosystem, all contributors (human and AI agents) must observe the following rules:

1. **Never work directly on `main`**: All development must occur on dedicated branches cut from the latest `main`.
2. **Start fresh from latest `main`**: Always pull and rebase/fast-forward against current `main` before creating a new branch.
3. **One focused branch per work unit**: Keep branches and pull requests scoped to a single coherent task or objective. Do not bundle unrelated refactors, chores, or features.
4. **One coherent Pull Request**: Ensure PRs are focused, well-documented, and use the standard PR template.
5. **Prefer squash merge**: PRs should be squash-merged into `main` to maintain a clean, linear commit history.
6. **Delete merged feature branches**: Remove remote and local feature branches once merged to prevent branch sprawl.
7. **Do not mix unrelated changes**: Keep diffs tight and focused on the requested task. Resist speculative additions or preemptive refactorings.
8. **Respect `AGENTS.md`**: Adhere strictly to the operational guidelines and invariants specified in [AGENTS.md](AGENTS.md).
9. **Respect product ownership boundaries**:
   - **Hogwarts Trials** owns quiz progression, question banks, scoring, sorting, and academic competitions.
   - **Pensieve** owns AI companion experiences, lore discovery, news aggregation, and source-provenance retrieval.
   - **The Burrow Clock** owns location sharing, friend presence, geofencing, and privacy controls.
   - Applications must never depend directly on each other's internal modules or private state.
10. **Shared code criteria (`commonroom-core`)**: Code belongs in an application package by default. Promote code to `packages/commonroom-core` only when actively required and consumed by at least two applications.
11. **Zero secrets and private data**: Never commit secrets, API keys, credentials, tokens, real GPS coordinates, or personal identifiable information.
12. **Zero copyrighted franchise assets**: Never introduce copyrighted book passages, movie scripts, ripped assets, official artwork, or proprietary franchise datasets. See [docs/ip-and-content-boundaries.md](docs/ip-and-content-boundaries.md).
13. **Pass all validation before review**: Ensure the repository validator (`python scripts/validate_repository.py`) and all relevant tests pass before requesting review or marking a PR ready.

