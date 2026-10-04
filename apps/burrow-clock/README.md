# The Burrow Clock

**The Burrow Clock** is a mobile-first, privacy-fundamental consensual family and friend presence sharing application within the Commonroom ecosystem.

## Product Scope & Boundaries
- **Domain Responsibilities**: Friend/family relationships for location sharing, geofencing, presence state computation, per-friend permission scoping, location-sharing sessions, group clock UI, and optional map views.
- **Non-Responsibilities**: Wizarding lore retrieval, trivia authoring, or AI-generated lore reasoning.

## Privacy Invariants
- Location sharing is default-off, strictly opt-in, permission-scoped per friend, and immediately revocable.
- Raw GPS coordinates are never broadcast by default; ambient presence and geofence states are prioritized.
- Fantasy/roleplay statuses (e.g., *"Mortal Peril"*) are purely aesthetic and strictly decoupled from real-world emergency/SOS features.

## Mobile Application Foundation

Commit 14 introduces the mobile shell in `mobile/`: TypeScript, React Native,
and stable Expo SDK 57 for iOS and Android. Its initial screen contains original
Commonroom text and styling, including a visible reminder that location sharing
is off by default. It requests no location permissions and collects no location
data. No franchise artwork, logos, book passages, or production content are included.

The app uses the existing pnpm workspace, the Node version in `.node-version`,
and the pnpm version in the root `package.json`. Run these commands from the
repository root:

```sh
pnpm install --frozen-lockfile --ignore-scripts
pnpm --filter burrow-clock-mobile run dev
pnpm --filter burrow-clock-mobile run typecheck
pnpm --filter burrow-clock-mobile run lint
pnpm --filter burrow-clock-mobile run config:check
pnpm --filter burrow-clock-mobile run check:dependencies
pnpm --filter burrow-clock-mobile run bundle:check
```

Development starts Expo's Metro server. The `android` and `ios` scripts target
an available device or simulator; iOS simulators require macOS. Validation and
CI require no device, simulator, native SDK, Expo account, or signing credentials.
The bundle check exports iOS and Android JavaScript into the ignored `mobile/dist/`
directory; it does not build or sign a native application.
Expo's default Metro configuration supplies workspace support; no custom
navigation, bundler configuration, or service layers are needed for this shell.

## Backend/API Foundation

Commit 15 introduces the FastAPI backend/API shell under `api/`. The importable
application is `burrow_clock_api.main:app`, titled **The Burrow Clock API**.
`GET /api/v1/health` returns HTTP 200 with exactly:

```json
{"status": "ok", "service": "burrow-clock-api"}
```

The API imports without environment configuration, external infrastructure,
network calls, or filesystem mutation. It has no database or privacy-sensitive
functionality, and the mobile shell does not connect to it yet.

Use Python 3.13.x from `.python-version` and uv 0.12.x. From the repository root,
configure an external environment before syncing or running commands; do not
create a repository-local `.venv`. For example, in PowerShell:

```powershell
$env:UV_PROJECT_ENVIRONMENT = Join-Path $env:TEMP 'commonroom-burrow-clock-api-venv'
uv lock --check
uv sync --frozen --all-packages
uv run --frozen --project apps/burrow-clock/api pytest apps/burrow-clock/api/tests
python scripts/validate_repository.py
uv run --frozen --project apps/burrow-clock/api uvicorn burrow_clock_api.main:app --reload
```

On a POSIX shell, set the external environment with
`export UV_PROJECT_ENVIRONMENT="${TMPDIR:-/tmp}/commonroom-burrow-clock-api-venv"`
before running the same uv and Python commands. Uvicorn serves the health endpoint
at `http://127.0.0.1:8000/api/v1/health` by default. The dedicated API CI workflow
checks the toolchain, frozen workspace dependencies, health tests, repository
integrity, and working tree cleanliness without service containers or secrets.

## Deferred Functionality

- Identity/authentication, authorization, and users/accounts
- Friend relationships, consent domain model, and sharing permissions
- Sharing sessions, revocation, and expiry
- GPS permissions, foreground location collection, and background location collection
- Raw coordinate persistence
- Geofencing and presence computation
- WebSockets and realtime presence
- PostgreSQL/database persistence
- Maps
- Notifications
- Emergency/SOS functionality
- Background execution

The privacy invariants above govern future implementations. The mobile shell and
API health endpoint do not implement sharing or imply that any relationship or
sharing session exists.

