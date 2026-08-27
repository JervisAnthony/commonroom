# Commonroom

**Commonroom** is an original fan-built wizarding companion ecosystem that brings magical utility, learning, and connection into everyday life. Rather than a single monolithic app, Commonroom is structured as a suite of three independently deployable applications connected by a shared conceptual universe and common domain contracts.

---

## The Applications

### 1. [Hogwarts Trials](apps/hogwarts-trials/)
An academic knowledge and trivia application featuring:
- Dedicated quiz tracks for Book-only, Movie-only, and Combined modes.
- Structured difficulty progression from introductory levels to O.W.L. and N.E.W.T. examinations.
- Sorting ceremony, house affiliation, and house point competitions.

### 2. [Pensieve](apps/pensieve/)
An AI-powered wizarding companion and canonical lore discovery engine featuring:
- Question answering with explicit source provenance and citations.
- Wizarding world news aggregation and summarization.
- Specialist learning journeys across spells, potions, magical creatures, and lore.
- Clear separation between verified canon, adaptation differences, and generated roleplay.

### 3. [The Burrow Clock](apps/burrow-clock/)
A mobile-first, privacy-fundamental presence sharing application featuring:
- Ambient, low-anxiety presence updates inspired by the magical family clock.
- Strict opt-in consent, per-friend scoping, and instant revocability.
- Ephemeral sharing sessions, geofencing, and distinction between approximate and precise presence.
- Separation of playful fantasy statuses (e.g., *"Mortal Peril"*) from real-world emergency systems.

---

## Repository Architecture

The project is organized as a monorepo containing distinct applications and shared packages:

```text
commonroom/
├── apps/
│   ├── hogwarts-trials/       # Academic trivia & examinations
│   ├── pensieve/              # AI companion & lore discovery
│   └── burrow-clock/          # Consensual presence sharing
├── packages/
│   └── commonroom-core/       # Shared contracts, types, and domain schemas
├── docs/                      # Ecosystem specifications and standards
│   ├── architecture.md        # Technical architecture and boundary invariants
│   ├── product-vision.md      # Product philosophy and long-term vision
│   └── ip-and-content-boundaries.md # Fan project policies and IP boundaries
├── AGENTS.md                  # Operating instructions for AI coding agents
├── README.md                  # Ecosystem overview (this file)
└── .gitignore
```

### Architectural Dependency Invariant
- Applications may consume shared contracts from `packages/commonroom-core` (`apps/* -> packages/commonroom-core`).
- Applications must never depend directly on each other's internal modules or private state.
- For complete architectural details, see [docs/architecture.md](docs/architecture.md).

---

## Project Status

> **Stage: Commit 1 — Ecosystem Foundation**
>
> The repository is currently in its initial architecture and foundation phase. Application logic, frameworks, databases, and UI components will be introduced in subsequent focused commits.

---

## Development & Governance

- All development is performed on dedicated feature branches cut from `main` following our [Contribution Workflow](CONTRIBUTING.md).
- Product boundaries, privacy invariants, and canonical content tiering must be strictly maintained.
- AI coding agents and contributors must follow the operational invariants defined in [AGENTS.md](AGENTS.md).
- Security policies, vulnerability reporting, and priority tiers are documented in [SECURITY.md](SECURITY.md).
- Repository integrity is validated locally and in CI using `python scripts/validate_repository.py`.

---

## Fan Project Disclaimer

**Commonroom** is an unofficial, fan-built companion ecosystem created for educational, personal, and transformative community enjoyment. It is not affiliated with, endorsed by, or sponsored by J.K. Rowling, Warner Bros. Entertainment Inc., Wizarding World Digital, or any related entity. All trademarks and copyrights belong to their respective owners. For full guidelines, see [docs/ip-and-content-boundaries.md](docs/ip-and-content-boundaries.md).
