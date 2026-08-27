# AGENTS.md

Operational and architectural instructions for AI coding agents (including Antigravity and automated contributors) working within the **Commonroom** repository.

---

## Core Agent Invariants

1. **Always inspect repository state before editing.**
   Check the current working directory, Git branch, working tree status, and recent commit history before planning or executing any changes.

2. **Never work directly on `main`.**
   All development must occur on a dedicated feature or task branch cut from the latest `main`.

3. **One intentional feature branch per commit/work unit.**
   Keep branches and pull requests focused on a single coherent task or objective. Do not bundle unrelated chores, refactors, or features together.

4. **Never merge a PR unless explicitly instructed by the repository owner.**
   Agents must never execute git merges into `main` or protected branches without explicit, unambiguous user confirmation.

5. **Do not broaden scope beyond the active task.**
   Implement only what was requested. Resist speculative additions, preemptive refactoring, or touching unrelated subsystems.

6. **Do not add dependencies without necessity.**
   Avoid adding third-party packages, libraries, or tools unless they are strictly required to fulfill the explicit task requirements. Always verify if native/standard capabilities suffice.

7. **Do not implement speculative abstractions.**
   Write concrete, direct solutions. Do not build premature generic frameworks, plugin architectures, or abstraction layers for hypothetical future requirements.

8. **Shared code belongs in `packages/commonroom-core` only when genuinely shared.**
   Code belongs in an application package by default. Do not promote code to `commonroom-core` unless it is actively required and consumed by two or more applications. Never use `commonroom-core` as a generic dumping ground.

9. **Respect product boundaries.**
   Strictly observe application ownership boundaries:
   - **Hogwarts Trials** owns quiz progression, question banks, scoring, sorting, and academic competitions.
   - **Pensieve** owns AI companion experiences, lore discovery, news aggregation, and source-provenance retrieval.
   - **The Burrow Clock** owns location sharing, friend presence, geofencing, and privacy controls.
   Applications must never depend directly on each other's internal modules or private state.

10. **Privacy-sensitive functionality requires explicit tests and threat-aware design.**
    Any feature touching location, identity, presence, or user relationships must be built privacy-first: default-off, explicitly consented, scoped, revocable, and backed by comprehensive automated test coverage.

11. **Never commit secrets, API keys, credentials, tokens, private location data, or personal information.**
    Do not place real secrets, live API keys, sensitive tokens, real GPS coordinates, or identifiable user data in commits, fixtures, documentation, or test files. Always use mock data and environment variables.

12. **Do not add copyrighted franchise content merely as test fixtures.**
    Do not import copyrighted book text, movie scripts, ripped assets, official artwork, or proprietary franchise datasets. Use synthetic, original, or generic placeholders for test fixtures and seed data.

13. **Prefer deterministic tests.**
    Tests must produce consistent, reproducible outcomes. Avoid flakiness, race conditions, non-mocked external network calls, or reliance on nondeterministic LLM outputs in test suites.

14. **Run all available validation before reporting completion.**
    Execute relevant linters, type checks, build steps, and test suites prior to completing any work unit (including `python scripts/validate_repository.py` for repository-level integrity).

15. **Report exactly what changed, what was tested, and any unresolved concerns.**
    Provide a transparent, concise final summary including previous state, branch name, file modifications, validation results, current git status, and any architectural risks or assumptions.

