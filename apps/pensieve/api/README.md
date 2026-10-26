# Pensieve API

Pensieve is Commonroom's planned AI companion and lore discovery service, with
source provenance and guided learning. This implements an
independent FastAPI application titled **Pensieve API**, a public health route,
and product-local source provenance contracts.
It cannot answer lore questions.

`GET /api/v1/health` returns HTTP 200:

```json
{"status": "ok", "service": "pensieve-api"}
```

The response uses a typed Pydantic model. Unknown API paths return ordinary HTTP
404. Interactive documentation is available at `/docs` and `/redoc`, and the
generated OpenAPI schema at `/openapi.json`.

## Local development

Use Python 3.13.x (repository pin: [`.python-version`](../../../.python-version))
and uv >=0.12,<0.13. The package supports Python 3.13+. The root workspace's
`apps/*/api` glob discovers `pensieve-api`; Hatchling builds its src-layout package.

From the repository root in PowerShell, configure an environment outside the
repository before installing or running commands:

```powershell
$env:UV_PROJECT_ENVIRONMENT = Join-Path $env:TEMP 'commonroom-pensieve-api-venv'
uv lock --check
uv sync --frozen --all-packages
uv run --frozen --project apps/pensieve/api uvicorn pensieve_api.main:app --reload
```

Visit `http://127.0.0.1:8000/api/v1/health` or `http://127.0.0.1:8000/docs`.
No database, pgvector, provider API keys, credentials, configuration variables,
frontend or external service is required. Import does not initialize storage,
make network calls or perform application filesystem writes.

Run tests and repository checks from the root using the same external environment:

```powershell
uv run --frozen --project apps/pensieve/api pytest apps/pensieve/api/tests
python scripts/validate_repository.py
python scripts/validate_toolchain.py
python scripts/validate_contract_schemas.py
python -m unittest discover -s scripts/tests
```

Tests are deterministic and require no internet access after dependency installation.
CI runs these API tests with frozen workspace dependencies and repository validation,
without database services or provider secrets.

## Source provenance contracts

`pensieve_api.domain.provenance` defines Pydantic v2 models without storage,
retrieval or external I/O:

- `CanonTier`: exact string values `book`, `film`, `expanded_publication`.
  These are source categories, not correctness guarantees or truth rankings.
- `SourceLocator`: required `kind` (`chapter`, `scene`, `section`, `other`) and
  nonblank `reference`.
- `SourceReference`: required nonblank `source_id` and `title`, a `canon_tier`
  and a nested `locator`.
- `SourcedLoreClaim`: required `kind="sourced_lore"`, nonblank original
  `statement` and a nonempty list of `sources` containing `SourceReference` objects.
- `GeneratedRoleplay`: required `kind="generated_roleplay"` and nonblank original
  `content`. It rejects source references and lore statement fields.

All model fields are required. Text is trimmed before checking for blank values;
numbers, booleans and bytes are not coerced to strings. Unknown fields are rejected,
including in nested models. Content kinds and source categories must match exactly.
The models accept nested dictionaries or model objects and support Pydantic JSON
serialization and validation. They are internal contracts with no new routes;
health behavior and the application's OpenAPI schema remain unchanged.

This example uses entirely fictional metadata and original text:

```python
from pensieve_api.domain.provenance import GeneratedRoleplay, SourcedLoreClaim

claim = SourcedLoreClaim.model_validate({
    "kind": "sourced_lore",
    "statement": "The imaginary atlas describes a lantern garden.",
    "sources": [{
        "source_id": "synthetic-atlas",
        "title": "The Imaginary Lantern Atlas",
        "canon_tier": "book",
        "locator": {"kind": "chapter", "reference": "3"},
    }],
})
assert SourcedLoreClaim.model_validate_json(claim.model_dump_json()) == claim

roleplay = GeneratedRoleplay(
    kind="generated_roleplay",
    content="I raise a paper lantern beside the imaginary garden gate.",
)
assert GeneratedRoleplay.model_validate_json(roleplay.model_dump_json()) == roleplay
```

Structural validation cannot establish originality, source authenticity, licensing,
locator existence or whether a source actually supports a claim. Callers must use
original wording and lawful source metadata. Attribution alone does not make a
statement a verified canonical fact. Roleplay is declared generated content and
must remain distinguishable from sourced lore; these contracts do not detect
mislabeling of prose or verify the caller's assertions.

## Source registry and reference resolution

`pensieve_api.domain.source_registry` adds `RegisteredSource`, `SourceRegistry`,
`ResolutionStatus`, `ReferenceResolution` and `ClaimResolution` locally to Pensieve.
`RegisteredSource` requires nonblank `source_id` and `title`, the existing
`CanonTier` and a nonempty strict list of existing `SourceLocator` values. Unknown
fields, malformed types and duplicate locator kind/reference pairs are rejected.
It shares the provenance contracts' trimming and exact tier/kind semantics.

Construct `SourceRegistry` with a finite collection of `RegisteredSource` objects.
An empty collection is valid; duplicate normalized source IDs are rejected.
Construction revalidates and snapshots mutable models into immutable metadata.
There is no global instance, seeded data, storage, network or external service.
Changing caller-owned models or result references cannot change registry entries;
construct a new registry to change registrations. The typed Python results are
internal objects, with no additional API routes or OpenAPI schemas.

`resolve_reference` returns a `ReferenceResolution` with an independent `reference`
snapshot and a `status`, using this precedence:

1. `SOURCE_NOT_REGISTERED`: the source ID is absent.
2. `SOURCE_METADATA_MISMATCH`: the ID exists but title or canon tier differs.
3. `LOCATOR_NOT_REGISTERED`: metadata matches but the locator kind/reference pair is absent.
4. `REGISTRY_MATCH`: all supplied metadata matches a registered entry.

Comparisons are exact after existing contract normalization: no fuzzy matching,
case folding, aliases or URL retrieval. `resolve_claim` accepts `SourcedLoreClaim`
only (rejecting `GeneratedRoleplay`), returns a `ClaimResolution` whose `references`
tuple preserves input order and duplicates, and exposes `all_references_registered`.
The aggregate is true only when every reference matches. Inputs are not mutated.

Using the entirely fictional `claim` from the earlier example:

```python
from pensieve_api.domain.source_registry import (
    RegisteredSource, ResolutionStatus, SourceRegistry,
)

registered = RegisteredSource(
    source_id="synthetic-atlas",
    title="The Imaginary Lantern Atlas",
    canon_tier="book",
    locators=[{"kind": "chapter", "reference": "3"}],
)
registry = SourceRegistry([registered])
result = registry.resolve_reference(claim.sources[0])
assert result.status is ResolutionStatus.REGISTRY_MATCH
outcomes = registry.resolve_claim(claim)
assert outcomes.all_references_registered
assert outcomes.references[0] == result
assert SourceRegistry([]).resolve_reference(claim.sources[0]).status is ResolutionStatus.SOURCE_NOT_REGISTERED
```

These guarantees are distinct:

- **Structural validation** checks required fields, types and declared values.
- **Registry metadata matching** compares those declarations to supplied records.
- **Source authenticity verification** would establish a source's genuineness; it
  is not implemented.
- **Claim-support verification** would assess whether a source supports a statement;
  it is not implemented.

A match does not establish lawful acquisition, passage existence outside the
registry, authenticity, statement support, canonical status or factual correctness.
The statement is never evaluated. Callers remain responsible for original wording
and lawful source metadata.

## Versioned curated source catalog

`pensieve_api.domain.source_catalog` defines strict Pydantic v2 contracts:

- `CatalogEntry`: required `source` (the existing `RegisteredSource`), exact
  `curation_status` (`proposed` or `metadata_reviewed`), and nonblank original
  `curation_note`.
- `SourceCatalog`: required integer `schema_version=1`, nonblank `catalog_id`,
  and explicit `entries` list (which may be empty). Unknown versions, unknown
  fields, invalid nested metadata and duplicate normalized source IDs across
  all statuses are rejected. Entry ordering is preserved; IDs are trimmed and
  compared exactly, without case folding.

`proposed` preserves supplied metadata without eligibility for matching.
`metadata_reviewed` means only that the catalog author declared the entry eligible
for registry matching. It does not establish actual independent human review,
authenticity, licensing, lawful acquisition, canonical authority, factual accuracy
or whether the source supports any lore statement. Structural validity never
automatically promotes an entry.

Call `catalog.build_registry()` explicitly. It revalidates the entire mutable
catalog before selecting only `metadata_reviewed` entries for the existing
`SourceRegistry`. Empty and all-proposed catalogs produce empty registries.
Construction leaves the catalog unchanged. Each registry is an independent
snapshot: subsequent changes to metadata, statuses or nested locators cannot
change an existing registry. Construct another registry to apply new declarations.
Matching and claim-resolution semantics remain unchanged; no claim-verification
result is produced.

The [synthetic version 1 example](examples/synthetic_catalog.v1.json) contains
one eligible fictional book and one proposed fictional film. It is demonstration
data, not a trusted production catalog. No catalog is discovered or loaded at
import or startup; there is no global registry, file scanning, retrieval, storage,
new configuration or external I/O.

Run this example from the repository root in the configured API environment.
The caller explicitly chooses to read the example file:

```python
from pathlib import Path
from pensieve_api.domain.provenance import SourceReference
from pensieve_api.domain.source_catalog import SourceCatalog
from pensieve_api.domain.source_registry import ResolutionStatus

payload = Path("apps/pensieve/api/examples/synthetic_catalog.v1.json").read_text(
    encoding="utf-8",
)
catalog = SourceCatalog.model_validate_json(payload)
assert SourceCatalog.model_validate_json(catalog.model_dump_json()) == catalog
assert SourceCatalog.model_validate(catalog.model_dump(mode="json")) == catalog
registry = catalog.build_registry()
reference = SourceReference(
    source_id="synthetic-moonseed-atlas",
    title="The Moonseed Lantern Atlas",
    canon_tier="book",
    locator={"kind": "chapter", "reference": "3"},
)
assert registry.resolve_reference(reference).status is ResolutionStatus.REGISTRY_MATCH
```

Repeated Pydantic JSON serialization of unchanged data is deterministic. Python
construction with nested dictionaries or model objects is also supported.

For future contributions:

- Keep every source ID unique across the catalog, including proposed entries.
- Supply valid metadata, locators and original explanatory notes. Include no
  reproduced licensed source passages.
- Preserve proposals as `proposed` until an explicit eligibility decision is
  recorded; never infer review from successful validation.
- Explicitly review metadata changes before including them in a new curated
  catalog version. `schema_version` describes the document format; use a distinct
  `catalog_id` for a new curated catalog revision under that format.
- Build a new registry for changed declarations; existing registries remain
  independent snapshots.

Catalog registration controls eligibility for metadata matching. It performs no
automatic content verification. Source authenticity and claim-support verification
remain explicitly deferred, as do licensing and canonical-authority assessments.

## Boundaries and deferred work

Pensieve imports no Hogwarts Trials or Burrow Clock internals. Its contracts remain
product-local; this foundation requires no changes to `commonroom-core`.
AI integrations, prompts, retrieval/RAG, embeddings, citation authenticity
verification, streaming, news
ingestion, persistence, authentication, accounts, frontend and deployment are
explicitly deferred. No simulated AI answers or placeholder lore routes exist.

Future canonical answers must distinguish supported source tiers (book canon,
film adaptations and expanded publications), cite identifiable lawful sources,
and separate generated roleplay from sourced lore. Lore search and question-answering
endpoints, databases, migrations and pgvector remain deferred. No retrieval or
citation verification system is implemented here. Follow the
[content boundaries](../../../docs/ip-and-content-boundaries.md); do not add
copyrighted passages, proprietary datasets, scraped licensed content or fabricated
citations presented as real sources.

Commonroom is an unofficial fan project, unaffiliated with franchise rights holders.
