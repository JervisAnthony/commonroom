# Pensieve API

Pensieve is Commonroom's planned AI companion and lore discovery service, with
source provenance and guided learning. This foundation implements only an
independent FastAPI application titled **Pensieve API** and a public health route.
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

## Boundaries and deferred work

Pensieve imports no Hogwarts Trials or Burrow Clock internals. Its contracts remain
product-local; this foundation requires no changes to `commonroom-core`.
AI integrations, prompts, retrieval/RAG, embeddings, citations, streaming, news
ingestion, persistence, authentication, accounts, frontend and deployment are
explicitly deferred. No simulated AI answers or placeholder lore routes exist.

Future canonical answers must distinguish supported source tiers (book canon,
film adaptations and expanded publications), cite identifiable lawful sources,
and separate generated roleplay from verified lore. No retrieval or citation
system is implemented here. Follow the
[content boundaries](../../../docs/ip-and-content-boundaries.md); do not add
copyrighted passages, proprietary datasets, scraped licensed content or fabricated
citations presented as real sources.

Commonroom is an unofficial fan project, unaffiliated with franchise rights holders.
