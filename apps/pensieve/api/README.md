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

## Catalog revision comparison and acknowledgment

`pensieve_api.domain.catalog_governance` provides three explicit Python operations:

- `compare_catalogs(previous, candidate) -> CatalogComparison` revalidates both
  complete `SourceCatalog` objects from fresh dumps, including proposed entries.
- `acknowledge_catalog_changes(comparison) -> CatalogAcknowledgment` records a
  caller declaration covering the complete transition.
- `build_registry_for_revision(previous, candidate, acknowledgment=None)` recomputes
  the comparison, enforces the revision policy, then builds the existing registry
  from the same validated candidate snapshot. Only eligible entries are included.

The operations reject unrelated input types with `TypeError`. Invalid mutated
catalogs retain Pydantic validation errors; missing or mismatched acknowledgment
and changed replacements with the same normalized `catalog_id` raise `ValueError`.
Every full-document change requires acknowledgment and a distinct catalog ID,
including ID-only, note-only, proposed-only and ordering changes. Comparison still
reports same-ID edits so they can be inspected. Identical normalized documents
need neither acknowledgment nor a new ID. Any supplied acknowledgment is checked
even for an unchanged transition.

`CatalogComparison` contains canonical `previous_document` and `candidate_document`
JSON strings, `previous_entry_order`, `candidate_entry_order`, and `source_changes`.
Each `SourceChange` has a `source_id`, optional `before`/`after` `EntrySnapshot`
(absence means addition/removal), and sorted `added_locators`/`removed_locators`.
Snapshots expose ID, title, tier, ordered locator pairs, status and note. Source-ID
edits are removal plus addition; no rename inference occurs. Source changes sort
by exact normalized ID, locator deltas by kind then reference. Snapshots preserve
entry and locator sequences. Existing whitespace trimming applies, with no case
folding, aliases, Unicode normalization or locator interpretation.

`has_changes` compares the complete normalized documents, including schema version,
catalog ID, all metadata, notes, statuses and ordering. `registry_metadata_changed`
instead compares eligible source IDs, titles, tiers and locator membership.
`eligibility_added` and `eligibility_removed` distinguish sources entering/leaving
the eligible set from `eligible_metadata_changed`, which lists matching-metadata
edits within sources that remain eligible. All three are sorted ID tuples.
Proposed-only edits, notes, catalog IDs and sequence reordering have no matching
effect. Locator kind/reference edits remove one pair and add another.

Bindings use complete normalized JSON with sorted object keys, ASCII escapes and
fixed compact separators, preserving every list's order. An acknowledgment for
A -> B fails for A -> C, X -> B, B -> A, or any intervening valid document edit,
even if catalog IDs are reused. Equivalent reconstructed normalized documents
are accepted, and reuse for the exact same pair is allowed. Acknowledgment is
never automatic, consumed, or reduced to a boolean flag or changed-source list.

Comparison results and acknowledgments are frozen dataclasses containing only
deeply immutable snapshots, tuples and scalars. Caller mutations cannot change
existing results or registries. For deterministic report JSON, use
`json.dumps(dataclasses.asdict(report), sort_keys=True, ensure_ascii=True,
separators=(",", ":"))`; properties are inspected separately. This is a Python
serialization path, not another versioned public wire schema.

This self-contained synthetic example performs no file loading:

```python
from dataclasses import asdict
import json
from pensieve_api.domain.catalog_governance import (
    compare_catalogs, acknowledge_catalog_changes, build_registry_for_revision,
)
from pensieve_api.domain.source_catalog import SourceCatalog
from pensieve_api.domain.provenance import SourceReference
from pensieve_api.domain.source_registry import ResolutionStatus

previous = SourceCatalog(schema_version=1, catalog_id="synthetic-revision-a", entries=[])
candidate = SourceCatalog(schema_version=1, catalog_id="synthetic-revision-b", entries=[{
    "source": {
        "source_id": "synthetic-paper-atlas", "title": "The Folded Lantern Atlas",
        "canon_tier": "book", "locators": [{"kind": "chapter", "reference": "1"}],
    },
    "curation_status": "metadata_reviewed",
    "curation_note": "The author declares this invented metadata eligible for matching.",
}])
report = compare_catalogs(previous, candidate)
print(json.dumps(asdict(report), sort_keys=True, ensure_ascii=True, separators=(",", ":")))
assert report.has_changes and report.registry_metadata_changed
assert report.eligibility_added == ("synthetic-paper-atlas",)
# The caller inspects the report and explicitly declares acknowledgment.
acknowledgment = acknowledge_catalog_changes(report)
registry = build_registry_for_revision(previous, candidate, acknowledgment)
reference = SourceReference(
    source_id="synthetic-paper-atlas", title="The Folded Lantern Atlas", canon_tier="book",
    locator={"kind": "chapter", "reference": "1"},
)
assert registry.resolve_reference(reference).status is ResolutionStatus.REGISTRY_MATCH
```

Structural validity checks document shape. Declared eligibility selects sources.
Registry matching compares metadata. Acknowledgment declares acceptance of a
particular change; it proves no inspection and does not identify or authorize a
reviewer. Authenticated approval, source authenticity, licensing and substantive
claim support remain outside this workflow. No lore statement is evaluated.

Enforcement is opt-in: the unchanged `SourceCatalog.build_registry()` remains
available. The caller supplies the previous catalog; this cannot establish that
it is currently adopted or latest. There is no universal governance enforcement,
persistent adoption, global freshness, tamper-proof audit history, signatures or
protection against hostile in-process Python code. No endpoints, configuration,
filesystem loading, databases or external I/O are added. Fresh-process audit-hook
tests guard against accidental I/O regressions; they are not an OS sandbox.

## Local source passages and exact lookup

`pensieve_api.domain.source_passages` defines:

- `SourcePassage`: required `kind="source_passage"`, nonblank `passage_id`, existing
  `SourceReference` in `reference`, and nonblank `text`. The strict Pydantic v2
  model forbids extra fields, rejects unrelated content kinds, and supports Python
  construction, `model_validate()`, JSON validation and JSON round trips.
- `PassageStore(registry: SourceRegistry, passages: Sequence[SourcePassage])`:
  explicit ordered finite input (including empty lists/tuples). Mappings, strings,
  iterators and unrelated records are rejected. Every complete record, including
  nested references, is revalidated from a fresh dump. Duplicate normalized IDs
  raise `ValueError`; IDs compare case-sensitively. Distinct IDs may share the same
  reference and identical text. Each reference must resolve through the public
  registry operation to `REGISTRY_MATCH`; otherwise construction raises
  `ValueError` identifying the passage and existing resolution status.
- `lookup_reference(reference: SourceReference) -> PassageLookup`: revalidates
  the mutable reference and resolves registry metadata first. Wrong operation
  input types raise `TypeError`; malformed mutable state raises validation errors.
- Frozen dataclass `PassageLookup(status: ResolutionStatus,
  passages: tuple[SourcePassage, ...])`: `SOURCE_NOT_REGISTERED`,
  `SOURCE_METADATA_MISMATCH`, then `LOCATOR_NOT_REGISTERED` retain that precedence
  and return empty tuples. `REGISTRY_MATCH` returns all matching passages in input
  order, or an empty tuple when the citation is registered but no text is stored.

Matching includes complete source ID, title, tier and locator kind/reference.
Existing whitespace trimming applies to IDs, metadata and text; interior text
whitespace and non-ASCII characters are preserved. Comparisons remain exact and
case-sensitive, without aliases, fuzzy matching, text search, ranking or locator
interpretation. Trimming is not byte-for-byte fidelity to an external publication.

Inputs remain unchanged. The store owns serialized validated records and retains
the supplied registry as its metadata snapshot dependency. Caller collection,
passage and nested reference mutations cannot change stored records. Each lookup
returns fresh independent Pydantic copies, including nested references. The outer
result is frozen, but its nested snapshots are mutable; editing one cannot change
another passage, lookup, stored record or the registry.

Run this self-contained synthetic example in the configured API environment;
it loads no files and performs no external I/O:

```python
from pensieve_api.domain.provenance import SourceReference
from pensieve_api.domain.source_catalog import SourceCatalog
from pensieve_api.domain.source_passages import PassageStore, SourcePassage
from pensieve_api.domain.source_registry import ResolutionStatus

catalog = SourceCatalog(schema_version=1, catalog_id="synthetic-local-v1", entries=[{
    "source": {
        "source_id": "synthetic-paper-atlas", "title": "The Folded Lantern Atlas",
        "canon_tier": "book", "locators": [
            {"kind": "chapter", "reference": "1"},
            {"kind": "chapter", "reference": "2"},
        ],
    },
    "curation_status": "metadata_reviewed",
    "curation_note": "An original fictional metadata eligibility declaration.",
}])
registry = catalog.build_registry()
reference = SourceReference(
    source_id="synthetic-paper-atlas", title="The Folded Lantern Atlas", canon_tier="book",
    locator={"kind": "chapter", "reference": "1"},
)
passage = SourcePassage(
    kind="source_passage", passage_id="synthetic-lantern-1", reference=reference,
    text="A folded paper lantern drifted across the imaginary orchard.",
)
assert SourcePassage.model_validate_json(passage.model_dump_json()) == passage
store = PassageStore(registry, [passage])
result = store.lookup_reference(reference)
assert result.status is ResolutionStatus.REGISTRY_MATCH
assert result.passages == (passage,)
without_text = reference.model_copy(deep=True)
without_text.locator.reference = "2"
result = store.lookup_reference(without_text)
assert result.status is ResolutionStatus.REGISTRY_MATCH and result.passages == ()
```

A store belongs to the supplied registry snapshot, including a registry returned
by `build_registry_for_revision()`. Later catalog mutations or replacement never
automatically update or invalidate it. Explicitly construct a new registry and
store for another revision; removed/demoted sources, changed matching metadata or
removed locators cause incompatible retained passages to fail new-store
construction. The acknowledgment workflow is unchanged. A store establishes no
catalog revision identity, current adoption, global freshness or authenticated
approval. It does not promote proposals.

Structural record validity, declared catalog eligibility, registry metadata
agreement and availability of caller-supplied text are separate guarantees.
Availability means only that the caller supplied stored text at a matching
declared citation. It proves no external passage existence, authenticity,
fidelity, lawful acquisition, canonical status or substantive claim support.
The discriminator is a caller declaration, not a detector of fabricated or
mislabeled prose. No claim or passage is evaluated semantically; generated
roleplay remains separate. Use original synthetic fixtures and fictional metadata;
do not add copyrighted franchise passages or scraped datasets. No loaders,
global store, persistence or endpoints are added. Claim-level composition of this
exact lookup is described below.

## Claim passage lookup

`pensieve_api.domain.claim_passages` adds a small composition of public operations:

- `lookup_claim_passages(claim: SourcedLoreClaim, store: PassageStore)
  -> ClaimPassageLookup` requires those existing object types. Dictionaries,
  strings, roleplay, passages and unrelated claims raise `TypeError`; a registry
  is not a passage store. The entire claim is revalidated from a fresh
  `model_dump(warnings=False)` before any lookup. Invalid mutable discriminators,
  statements, source lists and nested references raise existing validation errors,
  including invalid state in a later citation. Structurally valid metadata
  mismatches are lookup outcomes instead.
- Frozen `ReferencePassages` contains `reference: SourceReference`,
  `status: ResolutionStatus` and `passages: tuple[SourcePassage, ...]`.
- Frozen `ClaimPassageLookup` contains the normalized supplied `statement: str`
  and `references: tuple[ReferencePassages, ...]`, with two computed read-only
  aggregate properties.

The function calls only `store.lookup_reference()` once per validated citation,
including repeats, in input order. It preserves every failure and continues
looking up later citations. Each result retains an independent normalized
snapshot of the submitted citation, its existing status and every matching local
passage in store construction order. Nothing is sorted, deduplicated or flattened.
Complete source ID, title, canon tier and locator kind/reference are matched after
existing whitespace trimming, exactly and case-sensitively, without aliases or
locator interpretation. The statement is normalized by the existing contract and
copied without rewriting, summarization, generation or semantic evaluation.

`SOURCE_NOT_REGISTERED`, `SOURCE_METADATA_MISMATCH` and `LOCATOR_NOT_REGISTERED`
retain existing precedence and contain no passages. `REGISTRY_MATCH` may contain
an empty tuple: metadata agreement is distinct from local text availability.
`all_references_registered` is true only when the references tuple is nonempty
and every status is `REGISTRY_MATCH`. `all_references_have_passages` additionally
requires a nonempty passage tuple at every citation. Both are false for a directly
constructed empty result. All registered with one text-empty citation therefore
means registration is true and availability is false. These properties summarize
only registration and caller-supplied text availability. An unrelated statement
with the same citations yields the same lookup outcomes; available text cannot
establish that it supports the statement, is genuine, canonical, lawfully acquired
or faithful to an external publication.

Inputs, stores and registries remain unchanged. Every returned reference and
passage is independent of caller models, other calls and other entries, including
duplicate citations. The retained submitted-reference snapshot does not alias a
returned passage's reference. Frozen outer dataclasses and tuples contain mutable
independent Pydantic snapshots; editing a nested locator or passage cannot change
another entry, the caller, stored records or registry outcomes.

Catalog mutations do not automatically change an existing store or returned
result. Explicitly build a replacement registry (including through the unchanged
`build_registry_for_revision()` acknowledgment workflow) and a new store to
observe replacement metadata and text. Incompatible retained passages fail
new-store construction after source removal/demotion or metadata/locator changes.
Proposals stay excluded unless explicitly made eligible in a new registry.
No revision identity, current adoption, freshness, authenticated approval or source
verification is added.

This self-contained example uses fictional metadata and original synthetic prose,
with no file loading or external I/O. Run it in the configured API environment:

```python
from pensieve_api.domain.claim_passages import lookup_claim_passages
from pensieve_api.domain.provenance import SourceReference, SourcedLoreClaim
from pensieve_api.domain.source_catalog import SourceCatalog
from pensieve_api.domain.source_passages import PassageStore, SourcePassage
from pensieve_api.domain.source_registry import ResolutionStatus

catalog = SourceCatalog(schema_version=1, catalog_id="synthetic-claim-v1", entries=[{
    "source": {
        "source_id": "synthetic-atlas", "title": "The Folded Lantern Atlas", "canon_tier": "book",
        "locators": [{"kind": "chapter", "reference": "A"},
                     {"kind": "chapter", "reference": "B"}],
    },
    "curation_status": "metadata_reviewed",
    "curation_note": "Original fictional eligibility declaration.",
}])
reference = SourceReference(
    source_id="synthetic-atlas", title="The Folded Lantern Atlas", canon_tier="book",
    locator={"kind": "chapter", "reference": "A"},
)
without_text = reference.model_copy(deep=True)
without_text.locator.reference = "B"
passage = SourcePassage(
    kind="source_passage", passage_id="synthetic-lantern", reference=reference,
    text="A folded paper lantern drifted above the imaginary orchard.",
)
store = PassageStore(catalog.build_registry(), [passage])
claim = SourcedLoreClaim(
    kind="sourced_lore", statement="An original observation about an invented orchard.",
    sources=[reference, without_text, reference],
)
result = lookup_claim_passages(claim, store)
assert result.statement == claim.statement
assert [entry.reference for entry in result.references] == [reference, without_text, reference]
assert [entry.status for entry in result.references] == [ResolutionStatus.REGISTRY_MATCH] * 3
assert [entry.passages for entry in result.references] == [(passage,), (), (passage,)]
assert result.all_references_registered
assert not result.all_references_have_passages
```

The repeated first citation remains a separate third outcome with independent
copies. Neither aggregate evaluates the statement. Generated roleplay remains
separate; do not add copyrighted franchise passages, scraped data or fabricated
citations presented as genuine. Semantic retrieval/RAG, support verification,
generated answers and question-answering endpoints remain deferred.

## Boundaries and deferred work

Pensieve imports no Hogwarts Trials or Burrow Clock internals. Its contracts remain
product-local; this foundation requires no changes to `commonroom-core`.
AI integrations, prompts, semantic retrieval/RAG, embeddings, citation authenticity
verification, streaming, news
ingestion, persistence, authentication, accounts, frontend and deployment are
explicitly deferred. No simulated AI answers or placeholder lore routes exist.

Future canonical answers must distinguish supported source tiers (book canon,
film adaptations and expanded publications), cite identifiable lawful sources,
and separate generated roleplay from sourced lore. Lore search and question-answering
endpoints, databases, migrations and pgvector remain deferred. No semantic retrieval or
citation verification system is implemented here. Follow the
[content boundaries](../../../docs/ip-and-content-boundaries.md); do not add
copyrighted passages, proprietary datasets, scraped licensed content or fabricated
citations presented as real sources.

Commonroom is an unofficial fan project, unaffiliated with franchise rights holders.
