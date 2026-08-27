# Commonroom Product Vision

## Ecosystem Overview

**Commonroom** is an original fan-built wizarding companion ecosystem designed to bring magical utility, learning, and connection into everyday life. Rather than building a single monolithic application, Commonroom is structured as a suite of three focused, independently deployable products connected by a shared conceptual universe and common underlying contracts.

### Guiding Ecosystem Principle

> *"Hogwarts Trials tests what you know.*  
> *Pensieve helps you discover what you don't.*  
> *The Burrow Clock keeps your chosen people connected."*

---

## The Three Products

### 1. Hogwarts Trials (Knowledge & Academic Competition)

**Product Archetype**: Academic trivia, examination progression, and house affiliation game.

**Core Vision**:  
Hogwarts Trials provides a rigorous, engaging, and structured magical knowledge experience. It caters to casual fans and deep lore enthusiasts alike by offering differentiated quiz experiences based on media format, customizable difficulty, and authentic house competition.

**Key Product Pillars**:
- **Media-Specific Quiz Modes**: Dedicated tracks for Book-only canon, Movie-only adaptation details, and Combined universe knowledge.
- **Sorting & House Identity**: Transparent, meaningful sorting into Hogwarts houses with persistent house affiliation.
- **Academic Progression**: Tiered difficulty advancing from introductory first-year questions up to O.W.L. (Ordinary Wizarding Level) and N.E.W.T. (Nastily Exhausting Wizarding Test) examinations.
- **House Cup & Achievements**: Community-oriented house point scoring driven by quiz mastery, streak maintenance, and competitive milestones.

---

### 2. Pensieve (AI Lore Discovery & Companion)

**Product Archetype**: AI-powered wizarding companion, canonical retrieval engine, and lore discovery portal.

**Core Vision**:  
Pensieve acts as an intelligent, context-aware magical archive. It aggregates wizarding world news, answers complex lore inquiries with source provenance, and provides guided learning journeys across magical disciplines.

**Key Product Pillars**:
- **Canon-Aware Retrieval with Provenance**: Direct answers to lore questions backed by explicit citations distinguishing book canon, film adaptations, and expanded publications.
- **Specialist Learning Experiences**: Deep-dive interactive modules for Spells, Potions, Magical Creatures, Herbology, Divination, and Arithmancy.
- **News Aggregation & Summarization**: Curated and summarized updates regarding wizarding world releases, media, community events, and lore developments.
- **Explicit Content Tiering**: Crystal-clear delineation between verified canonical facts, adaptation nuances, and identified generative roleplay.

---

### 3. The Burrow Clock (Consensual Presence & Location Sharing)

**Product Archetype**: Mobile-first, privacy-fundamental family and friend presence sharing.

**Core Vision**:  
Inspired by the iconic magical family clock that tracks loved ones' general whereabouts, The Burrow Clock offers a warm, ambient, and low-anxiety way for close groups to stay connected without resorting to surveillance-style real-time tracking.

**Key Product Pillars**:
- **Privacy as a Fundamental Invariant**: Sharing is strictly opt-in, permission-scoped per friend, and instantly revocable at all times.
- **Ambient Presence over Surveillance**: Prioritizes categorized presence states (e.g., *Home*, *Work*, *Traveling*, *In Transit*, *Mortal Peril (Fantasy)*) and geofenced zones over raw GPS coordinate broadcasting.
- **Granular & Ephemeral Controls**: Configurable precision (approximate vs. precise) and time-limited sharing sessions with automatic expiry.
- **Safety Delineation**: Fantasy/roleplay statuses remain strictly aesthetic and explicitly decoupled from real-world emergency or SOS services.

---

## Ecosystem Synergy & Long-Term Horizon

While each application serves a distinct user need and maintains independent operational boundaries:
1. Users may carry a consistent identity, house affiliation, and wizarding persona across products.
2. Shared contracts in `packages/commonroom-core` will eventually standardize identity, friendships, permissions, and notifications.
3. Cross-application features will communicate exclusively through documented APIs and shared schemas, ensuring zero tight coupling between product internals.

