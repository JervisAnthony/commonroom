# Pensieve web

Pensieve's first web workspace provides a responsive homepage and live service
availability. It uses Next.js App Router server components, React and strict
TypeScript. It has no claim-submission or passage-browsing interface and cannot
answer lore questions.

## Local development

Use Node **24.20.0** (`>=24 <25`) and **pnpm 11.21.0**, as pinned by the
[repository toolchain](../../../docs/development-toolchain.md). The existing
`apps/*/web` workspace glob discovers `pensieve-web`. From the repository root
in PowerShell:

```powershell
pnpm install --frozen-lockfile --ignore-scripts
$env:NEXT_TELEMETRY_DISABLED = '1'
pnpm --filter pensieve-web run dev
```

Open <http://localhost:3001>. The page is useful even without a running API.
To run the [API](../api/README.md) locally, use Python 3.13.x and uv >=0.12,<0.13
in a separate terminal from the repository root:

```powershell
$env:UV_PROJECT_ENVIRONMENT = Join-Path $env:TEMP 'commonroom-pensieve-api-venv'
uv lock --check
uv sync --frozen --all-packages
uv run --frozen --project apps/pensieve/api uvicorn pensieve_api.main:app --reload
```

Run the web command in a second terminal. The default API origin is
`http://127.0.0.1:8000`. Optionally set this **server-only** variable before
starting the web process:

```powershell
$env:PENSIEVE_API_ORIGIN = 'http://127.0.0.1:8100'
pnpm --filter pensieve-web run dev
# After stopping the process, restore the default for this terminal:
Remove-Item Env:PENSIEVE_API_ORIGIN
```

Use an absolute HTTP(S) origin, optionally with a port or trailing slash.
Blank values, credentials, query strings, fragments and path prefixes produce
the unavailable state without a request. This configuration is never read from
browser parameters or exposed in the page. Do not use a public environment
variable for the origin.

## Validation and production

From the repository root in PowerShell:

```powershell
$env:NEXT_TELEMETRY_DISABLED = '1'
pnpm --filter pensieve-web run lint
pnpm --filter pensieve-web run typecheck
pnpm --filter pensieve-web run test
pnpm --filter pensieve-web run build
pnpm --filter pensieve-web run start
```

Production also uses <http://localhost:3001>. The root route is dynamic; the
build does not call the API or require API credentials. Native Node tests use
fetch doubles and mocked timers, without live network access. The dedicated web
workflow runs frozen installation, lint, typecheck, tests and build without a backend.

## Service availability

Each page request makes at most one server-side `GET /api/v1/health` request with
`Accept: application/json`, no cache, no redirects and a three-second deadline
covering fetch and body reading. Only HTTP 200 with an `application/json` media
type and an object containing exactly `status: "ok"` and
`service: "pensieve-api"` for those fields confirms connectivity. Additional
fields are ignored. Failures, unexpected responses and timeouts render
**Service unavailable** within a normal HTTP 200 homepage. No raw configuration,
payload or error is displayed or logged by this boundary.

**Refresh service status** is a plain link to `/`, making a fresh page request
and health check. There is no polling, retry loop or persistent health cache.
**Service reachable** confirms connectivity only. The default API responds to
health even without a passage store; passage configuration, source authenticity
and substantive claim verification are separate concerns.

## Product and content boundaries

Pensieve owns lore discovery and source provenance, not quiz scoring or location
sharing. This page collects no identity, relationship or location data and adds
no authentication, AI/provider integration, retrieval, ingestion or deployment.
Future sourced answers must distinguish canonical source tiers and carry lawful
citations; generated roleplay must be labeled separately. Local passage presence
does not establish truth, authenticity or permission to publish.

Commonroom is an unofficial fan project, unaffiliated with the franchise creators,
publishers or rights holders. The page uses original text/CSS and system fonts;
do not add copyrighted passages, official artwork or scraped datasets. Follow the
[content boundaries](../../../docs/ip-and-content-boundaries.md) and
[architecture](../../../docs/architecture.md).
