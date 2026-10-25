# Pensieve

**Pensieve** is an AI-powered wizarding-world companion and canonical lore discovery portal within the Commonroom ecosystem.

## Product Scope & Boundaries
- **Domain Responsibilities**: AI assistant interactions, lore question answering with canonical citations, wizarding world news ingestion and summarization, structured learning modules (spells, potions, creatures), and explicitly declared generative roleplay.
- **Non-Responsibilities**: Authoritative competitive quiz scoring or friend GPS tracking.

## Implemented foundation

The independent [Pensieve API](api/README.md) uses Python 3.13+, FastAPI and
Pydantic in the uv workspace. Its only application endpoint is public
`GET /api/v1/health`, returning HTTP 200 with
`{"status": "ok", "service": "pensieve-api"}`. OpenAPI documentation is available
at `/docs`, `/redoc` and `/openapi.json`. See the API README for the pinned runtime,
uv requirements, external environment setup, startup and validation commands.

Import and health need no database, pgvector, external services, provider keys or
environment configuration. Pensieve has no dependencies on other application
internals and requires no shared-core changes.

## Source provenance contracts

Product-local Pydantic contracts now represent source attribution: `CanonTier`
(`book`, `film`, `expanded_publication`), `SourceLocator`, `SourceReference`,
`SourcedLoreClaim` and `GeneratedRoleplay`. Lore requires an explicit
`kind="sourced_lore"`, an originally phrased statement and at least one source.
Roleplay requires `kind="generated_roleplay"` and original content; source and
statement fields are rejected. Required text is trimmed and must be nonblank;
unknown fields and invalid types are rejected.

For example, entirely fictional metadata could attribute the original statement
"The imaginary atlas describes a lantern garden" to source ID `synthetic-atlas`,
title *The Imaginary Lantern Atlas*, tier `book`, chapter `3`. See the
[API contract examples](api/README.md#source-provenance-contracts) for construction
and JSON round trips.

Canon tiers describe source categories, not proof of correctness. Structural
validation does not verify originality, source authenticity, licensing or actual
support for a claim. An attributed claim is not automatically a verified canonical
fact. Generated roleplay remains explicitly distinguishable from sourced lore.
These models add no API routes or OpenAPI schemas.

## Source registry and reference resolution

`RegisteredSource` declares a source ID, title, existing canon tier and a nonempty
list of unique locators. `SourceRegistry` snapshots an explicitly supplied finite
collection (which may be empty); it has no automatic records or persistence.
Duplicate IDs and duplicate normalized locator pairs are rejected.

Reference resolution compares source ID, title/tier, then locator kind/reference,
in that order. Outcomes are `SOURCE_NOT_REGISTERED`, `SOURCE_METADATA_MISMATCH`,
`LOCATOR_NOT_REGISTERED` or `REGISTRY_MATCH`. Comparisons are exact after contract
whitespace trimming, without case folding, aliases or retrieval.
Claim resolution preserves every reference, including order and duplicates, and
reports `all_references_registered`; generated roleplay is rejected.

For example, registering the synthetic atlas above with chapter `3` allows its
matching reference to return `REGISTRY_MATCH`. Changing its chapter to `4` returns
`LOCATOR_NOT_REGISTERED`. See the [executable example](api/README.md#source-registry-and-reference-resolution).

Structural validation checks the shape of supplied metadata. Registry matching
checks that metadata against caller-registered entries. Source authenticity
verification would establish whether a source is genuine; claim-support
verification would assess whether it supports the statement. Only the first two
are implemented. A registry match proves neither authenticity, lawful acquisition,
external passage existence, claim support nor canonical or factual correctness.
The registry uses immutable stored metadata and independent result snapshots;
caller mutations cannot change registered entries. No API routes are added.

The product scope above describes future intentions. AI, retrieval, embeddings,
citation verification, streaming, news ingestion, persistence, authentication, accounts and a
web frontend remain deferred. Pensieve cannot yet answer lore questions.

Future answers must distinguish supported canonical source tiers, including books
versus films, cite identifiable lawful sources, and label generated roleplay
separately from sourced lore. Follow the
[IP and content boundaries](../../docs/ip-and-content-boundaries.md).
Commonroom is an unofficial fan project, unaffiliated with franchise rights holders.

