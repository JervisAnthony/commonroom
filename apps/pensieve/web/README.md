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

## Claim-passage lookup boundary

`POST /api/claims/passages/lookup` is the same-origin web JSON operation. Its
server client calls only `POST /api/v1/claims/passages/lookup` on the configured
API origin. There is no browser client or claim entry/results interface yet;
the homepage and its health behavior are unchanged.

From the repository root, configure the external Python environment as above,
then start the existing explicit synthetic bundle in a separate terminal:

```powershell
$env:UV_PROJECT_ENVIRONMENT = Join-Path $env:TEMP 'commonroom-pensieve-api-venv'
uv sync --frozen --all-packages
uv run --frozen --project apps/pensieve/api python -m pensieve_api.bundle_app --bundle 'apps/pensieve/api/examples/synthetic_passage_bundle.v1.json' --port 8104
```

Start the web server in another terminal:

```powershell
$env:NEXT_TELEMETRY_DISABLED = '1'
$env:PENSIEVE_API_ORIGIN = 'http://127.0.0.1:8104'
pnpm --filter pensieve-web run dev
# After stopping the web process, restore this terminal's previous origin value.
# If it was previously absent:
Remove-Item Env:PENSIEVE_API_ORIGIN
```

In a third terminal, submit the complete synthetic claim:

```powershell
$claim = @{
    kind = 'sourced_lore'
    statement = 'A fictional lantern arrives.'
    sources = @(@{
        source_id = 'synthetic-atlas'
        title = 'The Folded Lantern Atlas'
        canon_tier = 'book'
        locator = @{ kind = 'chapter'; reference = 'A' }
    })
}
$body = $claim | ConvertTo-Json -Depth 8
$result = Invoke-RestMethod -Method Post -Uri 'http://localhost:3001/api/claims/passages/lookup' -ContentType 'application/json' -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
$result | ConvertTo-Json -Depth 12
```

The example returns two passages in bundle order (`arrival`, `departure`),
including the original Unicode text. This is an explicitly selected synthetic
example; no bundle loads automatically.

The pure `parseSourcedLoreClaim(value)` and
`parseClaimPassageResponse(value, claim)` adapters return independently owned
snapshots or `null`. Required own fields, exact primitives/literals and no extra
fields are enforced at every object. A request has exactly `kind: "sourced_lore"`,
nonblank `statement` and a nonempty ordered `sources` array. Each citation has
`source_id`, `title`, `canon_tier` (`book`, `film`, `expanded_publication`) and
`locator: { kind, reference }`; locator kinds are `chapter`, `scene`, `section`,
`other`. Source IDs are case-sensitive text, not UUIDs. Required text follows
Pydantic Unicode whitespace stripping (including U+0085 and U+00A0, preserving
U+FEFF); interior whitespace, accents and casing survive. Enum values are exact.
Generated roleplay and malformed later citations fail before network activity.

Responses require normalized wire text and exactly `statement`, `references`,
`all_references_registered` and `all_references_have_passages`. Each outcome has
exactly `reference`, `status` and `passages`; each passage has `kind:
"source_passage"`, `passage_id`, `reference` and `text`. Runtime checks bind the
statement, citation count, order and full metadata to the validated submitted
snapshot. Passage citations must match their containing outcome. Non-matching
outcomes contain no passages; matching outcomes may be empty. Duplicate passage
IDs within one outcome fail; the same IDs may recur across repeated citations.
No citations or passages are sorted or deduplicated. Valid text, including
interior/newline whitespace, survives exactly. Every nested result is a new
object/array, even for repeated input objects; these are mutable owned snapshots,
not frozen objects.

Both aggregates must be actual booleans equal to the outcomes. Registration
requires nonempty references, all `REGISTRY_MATCH`; passage availability also
requires text at every citation. An empty response reference list is invalid.

| Client result | HTTP | JSON |
| --- | --- | --- |
| `ok` | 200 | Validated response directly |
| `invalid_request` | 400 | `{"error":"INVALID_CLAIM"}` |
| `not_configured` | 503 | `{"error":"LOOKUP_NOT_CONFIGURED"}` |
| `unavailable` | 502 | `{"error":"LOOKUP_UNAVAILABLE"}` |

Missing/wrong request media type, bad JSON and invalid claims share the same 400
response. JSON media types tolerate casing and charset parameters. Every explicit
response is JSON with `Cache-Control: no-store`. Unsupported HTTP methods use
Next.js defaults. Only the exact known backend 503 JSON body
`{"detail":"Passage lookup is not configured"}` maps to `not_configured`.
Unexpected statuses (including 422), bodies, redirects, transport failures and
inconsistent response data map to the bounded 502 error.

`lookupClaimPassages(value, options?)` validates and serializes its owned request
before yielding. It reads server-only `PENSIEVE_API_ORIGIN` at call time, using
`http://127.0.0.1:8000` only when absent, with the same origin validation as health.
It makes at most one fixed POST with JSON Accept/Content-Type, no cache and no
redirects. Its three-second deadline covers fetch **and body reading**, aborts on
expiry, bounds even abort-ignoring transports, and clears timers on completion.
There is no health preflight, retry, polling or shared result cache. Incoming
cookies, authorization, headers, query parameters and backend headers are never
forwarded. Test options are server-side only. Failure results/logging expose no
raw origins, request values, backend bodies or error details; validated successes
intentionally expose passage text.

`SOURCE_NOT_REGISTERED`, `SOURCE_METADATA_MISMATCH`, `LOCATOR_NOT_REGISTERED`
and `REGISTRY_MATCH` without text are ordinary HTTP 200 data, including mixed
claims. The default `pensieve_api.main:app` remains healthy while valid lookup
returns the distinct unconfigured 503. Health connectivity, configured passage
availability and substantive claim support are separate. Matching metadata and
available text prove neither authenticity, rights, canon ranking nor claim support.

**Configured passage text remains publicly accessible without application
authorization.** Configure only material intended for public read access. UI,
authentication, AI/provider integration, ingestion, deployment and substantive
source/claim verification remain deferred.

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
