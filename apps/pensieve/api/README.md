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
