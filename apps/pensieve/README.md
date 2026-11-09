# Pensieve

**Pensieve** is an AI-powered wizarding-world companion and canonical lore discovery portal within the Commonroom ecosystem.

## Product Scope & Boundaries
- **Domain Responsibilities**: AI assistant interactions, lore question answering with canonical citations, wizarding world news ingestion and summarization, structured learning modules (spells, potions, creatures), and explicitly declared generative roleplay.
- **Non-Responsibilities**: Authoritative competitive quiz scoring or friend GPS tracking.

## Implemented foundation

The independent [Pensieve API](api/README.md) uses Python 3.13+, FastAPI and
Pydantic in the uv workspace. Public `GET /api/v1/health` returns HTTP 200 with
`{"status": "ok", "service": "pensieve-api"}`. OpenAPI documentation is available
at `/docs`, `/redoc` and `/openapi.json`. See the API README for the pinned runtime,
uv requirements, external environment setup, startup and validation commands.

Import and health need no database, pgvector, external services, provider keys or
environment configuration. Pensieve has no dependencies on other application
internals and requires no shared-core changes.

The [Pensieve web foundation](web/README.md) is a responsive Next.js homepage with
server-rendered service availability and manual refresh. Health confirms service
connectivity only; passage configuration and source verification are separate.

The [web claim-passage boundary](web/README.md#claim-passage-lookup-boundary)
adds a same-origin JSON POST backed by strict product-local TypeScript parsing,
request-bound response snapshots and a server-only API client. Lookup UI remains
deferred; normal negative citation outcomes are data, not service failures.

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
The HTTP lookup adapter reuses these existing request and response types.
Domain operations remain independently usable.

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
caller mutations cannot change registered entries. No registry-management routes are added.

## Versioned curated source catalog

Pensieve-local `CatalogEntry` pairs an existing `RegisteredSource` with a required
original nonblank `curation_note` and an exact `proposed` or `metadata_reviewed`
status. `SourceCatalog` requires integer `schema_version=1`, a nonblank
`catalog_id` and an explicit ordered `entries` list. Empty catalogs are valid;
unknown versions, unexpected fields, invalid nested metadata and duplicate
normalized source IDs across all statuses are rejected.

`proposed` entries remain in the catalog but cannot appear in registry matches.
`metadata_reviewed` means only that the author declared matching eligibility.
It establishes neither independent human review, authenticity, licensing, lawful
acquisition, canonical authority, factual accuracy nor support for any claim.
Structural validity never promotes a proposal.

Explicitly call `build_registry()` to revalidate the whole catalog and snapshot
only eligible sources into the existing `SourceRegistry`. Empty or all-proposed
catalogs create empty registries. Later metadata, status and locator changes do
not alter existing snapshots; construct a new registry to apply changes. Catalog
construction and registration add no routes or OpenAPI changes and evaluate no
source content or claims.

Pydantic `model_validate_json()`, `model_dump(mode="json")` and
`model_dump_json()` support parsing and deterministic serialization. The
[version 1 synthetic catalog](api/examples/synthetic_catalog.v1.json) contains
an eligible fictional book and a proposed fictional film. It is an example,
not an automatically trusted or loaded production catalog. See the
[executable catalog example and curation policy](api/README.md#versioned-curated-source-catalog).
The catalog domain performs no I/O. Imports and default startup load no data;
the explicit file adapter below reads only a caller-selected bundle.

Contributors must keep IDs unique, supply original metadata and notes rather than
licensed passages, and explicitly review metadata changes before inclusion in a
new curated catalog revision. Keep proposals excluded until eligibility is
declared. Registration differs from factual verification: source authenticity
and claim-support verification remain explicitly deferred.

## Catalog revision comparison and acknowledgment

The Pensieve-local operations `compare_catalogs(previous, candidate)`,
`acknowledge_catalog_changes(comparison)` and
`build_registry_for_revision(previous, candidate, acknowledgment=None)` offer an
opt-in replacement workflow. Both complete catalogs are revalidated from fresh
dumps, including proposals. The registry is built from the same validated candidate
snapshot, with proposed sources excluded and existing resolution behavior preserved.

Frozen `CatalogComparison`, `SourceChange`, `EntrySnapshot` and
`CatalogAcknowledgment` dataclasses retain deeply immutable values. Reports contain
complete normalized document JSON, entry order, before/after source snapshots and
locator membership deltas. Source changes sort by exact normalized ID; locator
deltas sort by kind/reference. Snapshots retain sequence order. Existing trimming
and case-sensitive matching apply. Source-ID edits are removal plus addition.

`has_changes` covers the whole document, including catalog ID, notes, proposals
and ordering. `registry_metadata_changed` covers only eligible IDs, titles, tiers
and locator membership. `eligibility_added`/`eligibility_removed` distinguish
membership changes from `eligible_metadata_changed` within sources remaining
eligible. Notes, proposed-only edits, ID-only edits and reordering have no matching
effect. Deterministic JSON uses `dataclasses.asdict` with sorted keys and fixed
separators; see the [executable example](api/README.md#catalog-revision-comparison-and-acknowledgment)
for compare, inspect, explicitly acknowledge, then build.

Every document change requires acknowledgment and a distinct normalized
`catalog_id`. Same-ID edits remain reportable but guarded construction rejects
them. Identical normalized documents need neither a new ID nor acknowledgment.
Missing or mismatched acknowledgment fails; a supplied acknowledgment is checked
even for no-change. Bindings include both complete normalized documents, so reused
IDs cannot conceal intervening changes. Equivalent reconstructed documents and
exact-pair acknowledgment reuse are allowed; nothing is consumed. Caller mutations
cannot alter existing comparison, acknowledgment or registry snapshots.

Structural validity, author-declared eligibility, registry metadata matching and
acknowledgment of a change are separate guarantees. Acknowledgment proves no
inspection, reviewer identity, authorization, licensing, source authenticity or
substantive claim support. Authenticated approval is not implemented.
The unchanged direct `SourceCatalog.build_registry()` remains available. The caller
supplies the baseline, so this provides no universal enforcement, persistent
adoption, authoritative latest revision, global freshness, tamper-proof audit trail
or protection against hostile in-process Python code. It adds no external I/O,
configuration, endpoints or OpenAPI schemas. Source authenticity and claim-support
verification remain deferred.

## Local source passages and exact lookup

`SourcePassage` requires `kind="source_passage"`, nonblank `passage_id`, an existing
`SourceReference` in `reference`, and nonblank `text`. This strict Pydantic v2
record rejects extra fields and unrelated content kinds and supports Python and
JSON validation/round trips. The discriminator is a caller declaration, not a
detector of fabricated or mislabeled prose. Outer whitespace is trimmed; interior
whitespace and non-ASCII text are preserved, without claiming byte-for-byte
fidelity to an external publication.

Construct `PassageStore(registry, passages)` with an existing `SourceRegistry` and
an explicit ordered finite sequence of `SourcePassage` objects (lists and tuples
are supported, including empty ones). Complete records are revalidated, and each
reference must resolve to `REGISTRY_MATCH`; incompatible records raise `ValueError`
identifying the passage and resolution status. Duplicate normalized passage IDs
are rejected, case-distinct IDs are allowed, and distinct IDs may share a reference
and identical text.

`lookup_reference(reference)` accepts an existing `SourceReference`, revalidates
it and resolves registry metadata first. The frozen `PassageLookup` contains the
existing `status` and an ordered `passages` tuple. `SOURCE_NOT_REGISTERED`,
`SOURCE_METADATA_MISMATCH` and `LOCATOR_NOT_REGISTERED` return no passages, with
the registry's existing precedence. `REGISTRY_MATCH` returns all exact matches in
construction order, or an empty tuple for registered citations with no stored
text. Complete source ID, title, canon tier and locator kind/reference must match
after trimming, case-sensitively, without aliases, search or locator interpretation.

Inputs remain unchanged. Serialized validated records isolate the store from
caller collection and model mutations. Each lookup returns fresh independent
passage and nested reference copies. The outer result is frozen; its nested
Pydantic snapshots remain mutable. Editing one cannot affect another or the store.

The store belongs to its supplied registry snapshot. Later catalog edits or
replacement do not update or invalidate it. Explicitly build another registry
(including through `build_registry_for_revision()`) and a new store to apply a
revision; retained incompatible passages fail construction after source removal,
demotion, metadata changes or locator removal. Governance remains unchanged; the
store establishes no catalog revision identity, adoption or global freshness.

Structural validity, declared eligibility, registry agreement and available text
remain separate from authenticity/fidelity and substantive claim support. Text
availability only means a caller supplied text at a matching declared citation;
it proves no external passage existence, genuineness, lawful acquisition,
canonical status or claim support. No prose is evaluated. Generated roleplay
remains separate. Tests and examples use original synthetic text and fictional
metadata; do not add copyrighted franchise passages or scraped datasets.

See the [executable synthetic example](api/README.md#local-source-passages-and-exact-lookup).
The domain module introduces no loaders, global store or external I/O.
The explicit HTTP adapter is described below.

## Claim passage lookup

`lookup_claim_passages(claim: SourcedLoreClaim, store: PassageStore)` revalidates
the entire mutable claim before any lookup, then calls the store's public
`lookup_reference()` for every citation in declared order, preserving duplicates
and continuing after failed lookups. It returns frozen `ClaimPassageLookup` with
the normalized supplied `statement` and a `references` tuple of frozen
`ReferencePassages(reference, status, passages)` results. Each retains an
independent normalized submitted citation, its existing registry status, and all
matching passages in store construction order. Wrong operation types raise
`TypeError`; invalid mutable claims retain existing validation errors.

Complete source ID, title, canon tier and locator kind/reference match exactly
after existing trimming, case-sensitively. `SOURCE_NOT_REGISTERED`,
`SOURCE_METADATA_MISMATCH` and `LOCATOR_NOT_REGISTERED` preserve that precedence
and return no text. `REGISTRY_MATCH` can also return no text: registered metadata
does not imply a locally stored passage.

`all_references_registered` is true only for a nonempty result whose every status
is `REGISTRY_MATCH`. `all_references_have_passages` additionally requires text at
every citation. Both are false for an empty result. An all-registered result with
one text-empty citation therefore reports `True` and `False`, respectively.
These computed properties describe registration and caller-supplied text
availability only. Even an unrelated statement can have text at every citation;
no statement is rewritten, generated or evaluated for substantive support.

Inputs remain unchanged. Nested reference and passage snapshots are mutable
independent copies, despite frozen outer dataclasses and tuple containers.
Mutations cannot affect other entries (including duplicates), another call, the
caller, stored records or registry metadata. Submitted-reference snapshots and
passage references are separate. Catalog edits do not automatically change an
existing store or result; explicitly construct a new eligible registry/store to
observe a replacement, revalidating retained passages. No promotion, revision
identity, adoption, freshness, authenticated approval or authenticity is inferred.

See the [self-contained synthetic example](api/README.md#claim-passage-lookup),
which demonstrates duplicate citations and registered metadata without text.
Examples use original fictional prose and metadata, with no copyrighted franchise
passages, scraped data or fabricated citations presented as genuine. Semantic
retrieval/RAG, support verification and question-answering endpoints remain deferred.

## Claim passage lookup HTTP API

Public `POST /api/v1/claims/passages/lookup` accepts the existing strict
`SourcedLoreClaim`: required `kind="sourced_lore"`, nonblank `statement`, and
nonempty `sources`. Malformed requests return standard HTTP 422 errors. Clients
cannot supply a registry, catalog, store, trusted text or authority flags.
HTTP 200 returns required `statement`, ordered `references` objects containing
`reference`, `status` and `passages` arrays, and booleans
`all_references_registered` and `all_references_have_passages` from the domain
operation. Normalization, citation order, duplicates and passage order are preserved.

`SOURCE_NOT_REGISTERED`, `SOURCE_METADATA_MISMATCH` and `LOCATOR_NOT_REGISTERED`
retain their precedence and return empty passage arrays. `REGISTRY_MATCH` may also
have no text. Unknown sources and mismatches are normal HTTP 200 outcomes; later
citations still run. Aggregates describe registration and local text availability,
never source authenticity, canonical authority or substantive claim support.

Explicitly compose `create_app(passage_store=store)` in `pensieve_api.main` with an
existing `PassageStore`. Each application's dependency reads its own state, keeping
instances independent. Default `app = create_app()` and the standard
`uvicorn pensieve_api.main:app` command remain unconfigured: health works and valid
lookups return HTTP 503 with
`{"detail": "Passage lookup is not configured"}`. An explicitly supplied empty
store is configured and returns ordinary HTTP 200 lookup outcomes. No examples,
catalog files, environment settings or trusted production passages are automatically
loaded. No provider keys, database or external I/O is needed.

Configuring the endpoint exposes the supplied store's passage text to callers as
**public read access**. Supply only material intended for that access; no
authorization or restricted/private-data service is added. Requests perform no
writes, promotion, adoption, persistence, new payload logging or prose evaluation.
Existing snapshot, provenance and content/IP boundaries remain in force. Caller
catalog/passage mutations and client response edits do not change an existing
store; build an explicit eligible replacement registry/store and application to
apply revisions, preserving proposal exclusion and acknowledgment semantics.

The [executable HTTP example](api/README.md#claim-passage-lookup-http-api) builds a
synthetic eligible registry/store, posts duplicate citations and a registered
citation without text, and asserts the complete HTTP JSON result. Generated OpenAPI
contains exactly health GET and lookup POST, with typed 200/503 and standard 422
contracts. No catalog, governance or roleplay operations are exposed.
AI answers, semantic retrieval/RAG, support verification, authenticity checks,
persistence, ingestion, authentication and deployment remain deferred. Exact
citation lookup is not a question-answering system.

The product scope above describes future intentions. AI, semantic retrieval, embeddings,
citation verification, streaming, news ingestion, persistence, authentication,
accounts and claim lookup UI remain deferred. Pensieve cannot yet answer lore questions.

Future answers must distinguish supported canonical source tiers, including books
versus films, cite identifiable lawful sources, and label generated roleplay
separately from sourced lore. Follow the
[IP and content boundaries](../../docs/ip-and-content-boundaries.md).
Commonroom is an unofficial fan project, unaffiliated with franchise rights holders.

## Versioned passage bundles

Import `PassageBundle` from `pensieve_api.domain.passage_bundle`. It is a strict
Pydantic document with exactly three required fields and no defaults:
`schema_version: Literal[1]` (the exact integer, excluding booleans and floats),
`catalog: SourceCatalog` and `passages: list[SourcePassage]`. The passage list
is ordered and may be empty; tuples, generators, unrelated records and unknown
fields are rejected. Existing nested contracts, normalization and JSON round trips
apply unchanged, preserving interior whitespace, non-ASCII text and record order.

Parsing validates structure, including catalog source-ID uniqueness, without
constructing a registry or store. Structurally valid documents can fail
`build_store()`: the existing `PassageStore` rejects duplicate normalized passage
IDs and references incompatible with eligible registry metadata. Case-distinct IDs
are distinct; distinct IDs may share identical text and a citation. Eligible
citations may have no text, and empty or all-proposed catalogs are valid.
Proposals remain excluded; inclusion never promotes them.

`build_store() -> PassageStore` revalidates the complete current bundle from a fresh
`model_dump(warnings=False)`, including proposals and every nested reference,
before any construction. It calls the validated catalog's public
`build_registry()` once, then constructs one existing `PassageStore` from that
registry and the ordered passages. Exceptions propagate without filtering or
partial success. Each call creates independent snapshots. Caller edits, collection
changes and returned passage/reference edits cannot change earlier stores; later
valid builds reflect explicit edits, while failed builds leave inputs and earlier
stores intact. There is no cache, active bundle, loader or automatic file discovery.

This uses direct catalog construction. For guarded replacement, callers must
continue using `compare_catalogs()`, `acknowledge_catalog_changes()` and
`build_registry_for_revision()`, followed by explicit `PassageStore` construction.
That opt-in workflow still requires an exact baseline/candidate acknowledgment and
a distinct catalog ID for changed documents. **Catalog acknowledgment does not
cover passage text or the complete bundle.** A passage-only edit is not an
acknowledged transition merely because the catalog ID stays the same; no new
passage revision approval policy is supplied.

`schema_version` identifies the serialization format; `catalog.catalog_id` is a
caller-declared metadata catalog identity; passage text is unverified local content.
None establishes current adoption, freshness, authenticated approval, source
authenticity, lawful acquisition, external passage fidelity, canonical authority or
substantive claim support. Matching remains exact and case-sensitive after trimming.

The [synthetic passage bundle](api/examples/synthetic_passage_bundle.v1.json) contains fictional metadata and original
prose: two ordered passages at book chapter A, registered chapter B without text,
and an excluded proposed film. It is an explicit example, never automatically loaded
or trusted production data. From the repository root, with the external uv
environment configured per Local development in the API README, run this PowerShell example:

```powershell
@'
from pathlib import Path

from fastapi.testclient import TestClient

from pensieve_api.domain.passage_bundle import PassageBundle
from pensieve_api.main import create_app

bundle = PassageBundle.model_validate_json(
    Path("apps/pensieve/api/examples/synthetic_passage_bundle.v1.json")
    .read_text(encoding="utf-8")
)
store = bundle.build_store()
application = create_app(passage_store=store)
a = bundle.passages[0].reference.model_dump(mode="json")
b = a | {"locator": {"kind": "chapter", "reference": "B"}}
claim = {
    "kind": "sourced_lore",
    "statement": "A fictional lantern arrives.",
    "sources": [a, b, a],
}
with TestClient(application) as client:
    response = client.post("/api/v1/claims/passages/lookup", json=claim)
    assert response.status_code == 200
    body = response.json()
assert [r["reference"] for r in body["references"]] == [a, b, a]
assert [r["status"] for r in body["references"]] == ["REGISTRY_MATCH"] * 3
assert [len(r["passages"]) for r in body["references"]] == [2, 0, 2]
expected = [p.model_dump(mode="json") for p in bundle.passages]
assert [p["passage_id"] for p in expected] == ["arrival", "departure"]
assert [r["passages"] for r in body["references"]] == [expected, [], expected]
assert body["all_references_registered"] is True
assert body["all_references_have_passages"] is False
'@ | uv run --frozen --project apps/pensieve/api python -
```

File reading is an explicit caller action. Standard
`uvicorn pensieve_api.main:app` remains unconfigured: valid lookups return the
existing HTTP 503 while health and docs remain available. This is a serializable
data contract with no new HTTP operation or OpenAPI bundle/catalog schema. The
explicit file startup adapter below composes it outside the I/O-free domain.

Passing this store to `create_app()` intentionally exposes its text through the
existing **public-read endpoint**. Configure only material intended for that
access. Parsing/building supplies no authorization or private-data service.
Existing provenance and content/IP limits still apply: use original synthetic
examples, never copyrighted franchise passages or scraped datasets. AI answers,
retrieval/search/ranking, support verification, authenticity checks, ingestion,
persistence, authentication and deployment remain deferred.

## Explicit bundle file startup

`pensieve_api.bundle_app.create_app_from_bundle_file(path: str | pathlib.Path)
-> FastAPI` constructs the existing API from one explicitly chosen local bundle.
It accepts strings and concrete `Path` objects; unrelated types raise `TypeError`
and blank string paths raise `ValueError` before I/O. Other path characters are
preserved, including meaningful spaces and non-ASCII names. Relative paths use
the caller's current directory; absolute paths are supported. There is no
environment-variable or home expansion, URL interpretation, search or discovery.

Each call reads only the selected file once with `encoding="utf-8-sig"` (UTF-8
with an optional leading BOM), parses the complete text with
`PassageBundle.model_validate_json()`, calls `build_store()` once, then passes
that store to the existing `create_app()`. Programmatic file, decoding,
validation and construction exceptions propagate without a fallback app.
The factory never starts a server or modifies `pensieve_api.main.app`.

From the repository root, using the external uv environment described in the
API README's Local development section:

```powershell
uv run --frozen --project apps/pensieve/api python -m pensieve_api.bundle_app --help
uv run --frozen --project apps/pensieve/api python -m pensieve_api.bundle_app --bundle "apps/pensieve/api/examples/synthetic_passage_bundle.v1.json"
# Optional local port:
uv run --frozen --project apps/pensieve/api python -m pensieve_api.bundle_app --bundle "apps/pensieve/api/examples/synthetic_passage_bundle.v1.json" --port 8104
```

`--bundle PATH` is required. `--port PORT` defaults to 8000 and accepts integers
1 through 65535. Argument errors exit 2; help exits 0 without loading. Expected
loading failures print a concise stderr diagnostic without raw JSON or passage
text and return 1 before starting the server. Programming and server/runtime
failures propagate normally. Successful startup runs uvicorn on **127.0.0.1**,
with one worker and reload disabled; the command returns 0 when the runner returns
normally. There are no host, reload, worker or environment configuration options.

The standard `uvicorn pensieve_api.main:app` still starts the unconfigured
application: valid lookups return HTTP 503, while health and docs work. Importing
the new module loads no bundle or application configuration and starts no server.
Installed wheels contain `pensieve_api/bundle_app.py`; the synthetic JSON remains
a repository example. Operators supply their own explicit local document.

Each created app holds an independent load-once snapshot. Requests never reread
the bundle. File edits or deletion and response edits cannot change earlier apps.
Explicitly reconstruct or restart to observe changed data; a failed reconstruction
leaves earlier apps intact. There is no watching, hot reload, background refresh,
global configured cache or fallback discovery.

This uses direct `PassageBundle.build_store()` construction, without inventing a
baseline or acknowledgment. Guarded catalog replacement still requires explicit
`compare_catalogs()`, `acknowledge_catalog_changes()`,
`build_registry_for_revision()` and `PassageStore` composition. Catalog
acknowledgment binds catalog documents, not passage text or a complete bundle.
Reconstruction is neither authenticated approval, persistent adoption nor
freshness enforcement. Existing proposal exclusion remains unchanged.

For an in-process example, run this PowerShell block from the repository root:

```powershell
@'
from fastapi.testclient import TestClient

from pensieve_api.bundle_app import create_app_from_bundle_file

application = create_app_from_bundle_file(
    "apps/pensieve/api/examples/synthetic_passage_bundle.v1.json"
)
a = {
    "source_id": "synthetic-atlas",
    "title": "The Folded Lantern Atlas",
    "canon_tier": "book",
    "locator": {"kind": "chapter", "reference": "A"},
}
b = a | {"locator": {"kind": "chapter", "reference": "B"}}
with TestClient(application) as client:
    response = client.post("/api/v1/claims/passages/lookup", json={
        "kind": "sourced_lore",
        "statement": "A fictional lantern arrives.",
        "sources": [a, b, a],
    })
    assert response.status_code == 200
    body = response.json()
assert [r["reference"] for r in body["references"]] == [a, b, a]
assert [r["status"] for r in body["references"]] == ["REGISTRY_MATCH"] * 3
assert [len(r["passages"]) for r in body["references"]] == [2, 0, 2]
assert [p["passage_id"] for p in body["references"][0]["passages"]] == [
    "arrival", "departure"
]
assert body["references"][0]["passages"] == body["references"][2]["passages"]
assert body["all_references_registered"] is True
assert body["all_references_have_passages"] is False
'@ | uv run --frozen --project apps/pensieve/api python -
```

Configured text is exposed through the existing **public-read lookup endpoint**.
Loopback binding supplies no application authorization; use only material intended
for that access. This is not a private-data service. Parsing, registration and text
availability establish no authenticity, canonical authority, lawful acquisition,
external fidelity or substantive claim support. Use fictional metadata and original
prose, respecting existing content/IP boundaries; never add copyrighted franchise
passages or scraped datasets. The domain remains free of I/O, and no API operation
or OpenAPI contract changes. AI answers, search/ranking/RAG, source/support
verification, scraping/content-ingestion pipelines, persistence, authentication,
claim lookup UI and deployment remain deferred.
