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
integration, and the mobile shell does not connect to it yet.

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

## Consent Domain Foundation

Commit 16 introduces pure, standard-library Python consent rules in
`api/src/burrow_clock_api/domain/consent.py`. Sharing is default-off: no explicit
grant means no disclosure. `SharingScope` defines presence, approximate, and
precise disclosure levels, in ascending sensitivity. An immutable `ConsentGrant`
acts as a maximum disclosure ceiling: it permits its own level and lower levels,
never a higher level. These scopes describe future permissions, not collected data.

Grants contain only `scope`, `granted_at`, optional `expires_at`, and optional
`revoked_at`. All timestamps, including explicitly supplied evaluation times,
must be timezone-aware. Evaluation is deterministic and never reads the current
clock. Comparisons use UTC instants, including across repeated local clock hours.
Consent begins at `granted_at`; earlier evaluation is denied. Expiry must
be strictly later than the grant and denies disclosure exactly at and after
`expires_at`. Without expiry, a grant does not automatically expire.

`revoke(at)` returns a new frozen grant without changing the original. Revocation
cannot precede the grant; disclosure is denied exactly at and after `revoked_at`.
Historical evaluation before revocation may still allow disclosure if otherwise
active. Repeat revocation raises `ValueError`; no automatic re-grant exists.
Invalid timestamps and scopes also raise `ValueError`.

The model contains no users, friends, coordinates, persistence, or API surface.
Expiry and revocation are executable domain semantics only: no scheduler,
revocation API, persistence, or user workflow exists yet. The application endpoint
remains `GET /api/v1/health` only. Run the focused deterministic tests with the
external Python environment configured as above:

```sh
uv run --frozen --project apps/burrow-clock/api pytest apps/burrow-clock/api/tests/test_consent_domain.py
```

## Relationship and Sharing Boundary

Commit 18 adds immutable, product-local relationship and permission facts.
`Friendship` contains only `friendship_id`, `user_a_id`, and `user_b_id`, all
UUIDs, with distinct members. It represents a currently active relationship
only. Participant order implies neither direction nor ownership; `contains_user`
and `connects` inspect membership, with `connects` accepting either order.

`SharingPermission` contains `friendship_id`, `sharer_user_id`,
`recipient_user_id`, and the existing `ConsentGrant` as `grant`. Identifiers
must be UUIDs and sharer and recipient must differ. It binds explicit consent
to one friendship and direction: A -> B never implies B -> A. Reverse sharing
requires an independent permission and grant. Invalid identifier/grant types
raise `TypeError`; identical participants raise `ValueError`.

`is_friend_disclosure_allowed(friendship, permission, sharer_user_id,
recipient_user_id, requested_scope, at)` is a pure default-deny policy. It
requires an active friendship with exactly the supplied parties and a permission
matching that exact friendship, sharer, and recipient. Friendship alone never
enables disclosure; consent or permission alone never enables disclosure.
Malformed structural objects and mismatches deny. Scope, activation, expiry,
and revocation remain delegated to `ConsentGrant` through
`is_disclosure_allowed`; invalid evaluation scope/time retains its `ValueError`
behavior when the relationship and permission match. Evaluation uses an
explicit time, never the current clock.

An absent active friendship denies even with a stale, otherwise active
permission. Future trusted storage must return no active `Friendship` after
removal, blocking, or unfriending, and authorization must retrieve both facts
on every evaluation. Relationship lifecycle and actual block/unfriend workflows
are not implemented; the policy does not mutate stale permissions.

`FriendshipRepository.get_active_friendship_between(user_a_id, user_b_id)`
looks up an active relationship independently of member order.
`SharingPermissionRepository.get_permission(friendship_id, sharer_user_id,
recipient_user_id)` looks up one exact direction. These runtime-checkable
protocols in `application/repositories.py` are read-side trusted-storage
boundaries only, with no mutation methods, repository adapters, or persistence.
UUIDs do not establish identity or authentication. The API remains
`GET /api/v1/health` only, and no location data exists.

Run the focused deterministic suite using the configured external environment:

```sh
uv run --frozen --project apps/burrow-clock/api pytest apps/burrow-clock/api/tests/test_friend_sharing.py
```

## Deferred Functionality

- Authentication, authorization integration with authenticated principals, and users/accounts
- Friendship invitations/requests and accept/reject/block/unfriend workflows
- Repository adapters and friendship/permission REST APIs
- Sharing sessions, revocation API/workflow, and expiry scheduling
- GPS permissions, foreground location collection, and background location collection
- Coordinates and raw coordinate persistence
- Geofencing and presence computation
- WebSockets and realtime presence
- PostgreSQL/database persistence and migrations
- Maps
- Notifications
- Emergency/SOS functionality
- Background execution

The privacy invariants above govern future implementations. The mobile shell and
API health endpoint do not collect or disclose location data. The pure domain
facts and policy do not implement sharing sessions or authenticated sharing.

