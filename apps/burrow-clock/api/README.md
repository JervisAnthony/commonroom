# The Burrow Clock API

The FastAPI API exposes public health and protected friendship, directional consent,
and finite sharing-session metadata workflows. Importing
`burrow_clock_api.main:app` requires no database URL, opens no connection, creates
no tables, runs no migrations, and performs no application filesystem writes.
The mobile shell is unchanged and is not connected to persistence.

Commit 21 adds product-local PostgreSQL 17 persistence using SQLAlchemy 2.x,
psycopg v3 and Alembic, on Python 3.13+ with the existing uv workspace. Persistence
stores authorization metadata only. It activates no GPS/location collection or
actual disclosure. Commit 23 connects metadata workflows to authenticated REST
boundaries that default to HTTP 401 until a real adapter exists. Credential verification,
OAuth/OIDC verification, user accounts, friend invitations, blocking workflows,
location streams, geofences, observations, maps and background workers remain deferred.

## Protected REST metadata workflows

`get_current_principal()` always raises **401 Authentication required** in production.
There is no development identity, header adapter, environment bypass or fake token.
The product-local frozen `AuthenticatedPrincipal` accepts only a UUID `user_id`
validated by a future trusted authentication adapter. Constructing it does not
perform authentication. `X-User-Id`, `X-Actor-Id`, arbitrary bearer strings and
body-supplied actors cannot establish a principal. Health remains public and unchanged.

All paths below are prefixed by `/api/v1`. Missing and inaccessible resources share
one generic 404 response. Protected responses include `Cache-Control: no-store`.

| Method and path | Request and authorized response |
| --- | --- |
| `GET /friendships/with/{other_user_id}` | Active relationship between the principal and that exact other user; returns friendship and both member UUIDs (200). |
| `DELETE /friendships/{friendship_id}` | Exact active member terminates the friendship and removes its sessions atomically (204); others, missing and already terminated relationships get 404. |
| `POST /friendships/{friendship_id}/permissions` | Body: `recipient_user_id`, `scope`, optional aware ISO 8601 `expires_at`. Principal is the sharer. Returns newly generated grant identity and consent metadata (201). |
| `GET /friendships/{friendship_id}/permissions/{recipient_user_id}` | Current exact-direction consent owned by the principal as sharer, including `permission_id`, friendship/party UUIDs, scope, grant time, optional expiry/revocation (200). Reverse and historical grants are not exposed. |
| `DELETE /permissions/{permission_id}` | Only the sharer of that exact current grant in an active friendship can withdraw it (204): cancel before activation, revoke at/after activation. Recipient/outsider/historical/missing grants return 404; an already revoked owned grant conflicts (409). |
| `POST /friendships/{friendship_id}/sessions` | Body: `recipient_user_id`, `requested_scope`, explicit integer `duration_seconds` of **60 to 86400 seconds, inclusive**. Principal is the sharer. Returns generated session UUID, friendship UUID, exact grant UUID, scope and server-computed UTC start/expiry (201). |
| `GET /sessions/{session_id}` | Required query: `sharer_user_id`, `requested_scope`. Recipient is always the principal. Re-evaluates current direction, friendship, grant identity, scope and time (200); missing/inaccessible/ended/expired/revoked/superseded/terminated sessions give 404. |
| `DELETE /sessions/{session_id}` | Only the sharer owning the session's exact permission can delete its metadata (204); recipient/outsider/missing sessions get 404. |

There is **no friendship creation route**. Trusted internal setup establishes
friendships; invitations and mutual acceptance remain deferred. A relationship ID,
grant ID or session ID is never a credential. Successful session reads return
permission metadata only, never a presence observation or location.

Write models forbid extra fields. Scopes use the stable string names `PRESENCE`,
`APPROXIMATE`, `PRECISE`, never numeric enum values. Write requests reject
client-controlled actor/sharer identity, `permission_id`, `session_id`, lifecycle
flags such as `is_current`, and server-owned grant/start/revocation timestamps.
Legitimate `recipient_user_id` UUID fields remain accepted in grant and session
creation requests, as does the optional aware `expires_at` on grant requests.
Recipient UUIDs, aware expiries and strict duration bounds are validated (422).
Expiry must be later than server grant creation; a session extending past finite consent expiry gives
409 rather than silently shortening a duration. Missing/inactive/wrong-direction
consent or excessive scope gives 404. Validation errors never echo input values.
Persistence configuration/SQLAlchemy failures return generic 503 without URLs,
credentials, SQL statements or internal exception details. Responses use explicit
Pydantic DTOs with UTC timestamps, not ORM serialization.

Server time comes from the injectable `get_now()` dependency. Grant/session
creation uses server UTC time; clients cannot choose evaluation times. Expiry and
revocation are exclusive: at or after the boundary access denies. Future-dated
internal grants deny before activation and can be cancelled immediately by their sharer. Re-grant immediately creates a new current
identity and removes old sessions; neither historical consent nor terminated
friendships reactivate. Re-friending requires a fresh friendship and fresh consent.
Session reads are snapshots, not durable capabilities or actual disclosure rights.

`get_current_permission()` adds a narrow `CurrentPermission` read value to carry
the generated grant UUID without changing the earlier `get_permission()` contract.
`terminate_friendship_as_member()`, `revoke_permission_as_sharer()` and
`end_session_as_sharer()` authorize locked database facts and mutate in the **same
transaction**, in `friendship -> permission -> session` lock order. Parent discovery
queries are not ownership checks. Grant/session creation uses existing locked
membership/directional-consent checks with the sharer taken from the principal.
No HTTP path does an ownership precheck followed by an unguarded ID-only mutation.

Persistence is lazy and application-owned: denied anonymous calls never initialize
storage. The first authenticated request creates one shared engine/session factory;
application lifespan shutdown disposes the engine. Import, startup and public
health do not inspect database configuration or connect, create tables or migrate.
No SQLite runtime fallback exists. Run Alembic explicitly before using PostgreSQL.

Tests override `get_current_principal`, `get_sharing_repository` and `get_now` with
synthetic trusted values, test repositories and fixed UTC instants. These overrides
exist only in tests, never in production configuration. HTTP behavior runs against
SQLite and, when configured, live PostgreSQL. Transaction-sensitive tests coordinate
real parent locks using events, covering cancellation/revoke/terminate versus session creation,
session end versus recipient read, and replacement versus a stale revoke precheck.
The existing PostgreSQL 17 CI workflow collects the complete suite and requires live
coverage with `BURROW_CLOCK_REQUIRE_POSTGRES_TESTS=1`.

## Schema and lifecycle

Burrow's independent initial Alembic revision `0001` is in `alembic/versions/`.
It creates only these tables, with UUID primary keys and no seed grants:

- `friendships`: UUID, canonical ascending UUID member pair, explicit `is_active`.
  A database check prevents self/noncanonical pairs; a partial unique index allows
  only one active relationship per unordered pair, including concurrent inserts.
  Termination retains an inactive relationship fact and deletes its session metadata.
  Inactive rows never reconstruct as an active `Friendship`. Re-friending requires
  a fresh friendship UUID; the old primary key cannot be reused by the writer.
- `sharing_permissions`: a distinct server-generated `permission_id` for each
  explicit grant, exact friendship/sharer/recipient, textual scope, timezone-aware
  grant/expiry/revocation timestamps, and explicit `is_current`. Generated
  `member_a_id`/`member_b_id` derive the canonical members from the direction solely
  to enforce membership through a composite FK; callers cannot set these fields.
  A partial unique index permits only one current record for each exact direction.
  A -> B never implies B -> A. Reverse consent requires a separate explicit grant.
- `sharing_sessions`: server-generated session UUID, friendship UUID, exact
  permission UUID, textual requested scope, timezone-aware start and finite expiry.
  A composite FK prevents binding a grant to another friendship. Sessions contain
  no duplicate sharer/recipient fields; those are retrieved from the exact grant.
  They contain no coordinates, device identifiers, observations or location history.

FK cascade deletes remove dependent consent/session records when their parent is
removed. Database checks also protect scope, grant timing and finite session timing.
Downgrade to base removes only Burrow's three tables and indexes.

The existing `FriendshipRepository` and `SharingPermissionRepository` read contracts
remain intact. `SharingSessionRepository` adds current session evaluation.
`SharingLifecycleRepository` describes internal trusted writes; the concrete
`PostgresSharingRepository` takes an explicit SQLAlchemy session factory.
Its operations create/terminate friendships, explicitly grant/revoke directional
consent, start/end sessions and clean up expired sessions. They are infrastructure
seams, not proof of end-user authentication. HTTP uses the narrow
`AuthorizedSharingRepository` port: actor-aware termination/revocation operations
verify membership or exact grant ownership inside the same transaction as mutation.
The earlier ID-only internal writer APIs remain intact and are never exposed directly.
UUIDs and session IDs are never authentication credentials.

## Privacy enforcement

Sharing remains default-off. Friendship, consent or a stored session alone cannot
authorize disclosure. Reconstruction validates the original immutable domain
contracts; malformed grants/sessions deny rather than becoming authorized facts.
Expired/revoked current permissions may be returned as consent facts for domain
evaluation, never as an allow decision. `get_permission` returns no historical or
reversed record and no permission for an inactive friendship.

Pre-activation **cancellation** in `revoke_permission_as_sharer()` is distinct from
ordinary revocation. After locking the active friendship and exact current grant,
the authenticated sharer can withdraw a pending grant by setting `is_current=False`
and deleting any sessions bound to that grant in the same transaction, in
`friendship -> permission -> session` order. `revoked_at` is left unchanged: no future
revocation timestamp is fabricated, and the `revoked_at >= granted_at` constraint
is preserved. Cancellation is permanent for that grant identity; it disappears
from current-consent reads and cannot activate later or authorize sessions.
Reverse-direction consent is unaffected. Repeated withdrawal of a cancelled grant
returns 404. New consent requires a new explicit grant identity; no old grant is
reactivated. Cleanup failure rolls back both cancellation and session deletion.

At or after activation, ordinary **revocation** retains the current grant identity
and records the exact supplied server UTC `revoked_at`, preserving historical
pre-boundary evaluation and denial at/after the boundary. Already-revoked grants
cannot be rewritten or cleared, including by supplying a pre-activation time.
The earlier trusted internal `revoke_permission()` retains its existing strict
timestamp contract; HTTP uses the actor-aware method above.

Revocation updates the exact grant UUID transactionally and never clears an existing
`revoked_at`; repeat revocation raises `ValueError`. Its exclusive boundary is
preserved: historical evaluation before the instant can allow, while evaluation
at or after it denies. A new explicit grant always gets a new UUID, permanently
supersedes the prior direction's current record, and deletes sessions bound to that
prior grant. Grant activation dates do not select a version: `is_current` does.
A future-dated replacement immediately supersedes its predecessor and denies until
its own activation; old grants do not become current again.

Starting a session locks and validates current friendship and matching consent,
uses the existing `is_friend_disclosure_allowed` policy, and enforces scope,
activation, expiry and revocation. Session expiry cannot exceed finite consent
expiry. Even an indefinite consent grant requires a finite session expiry.

`get_active_session(session_id, sharer_user_id, recipient_user_id, requested_scope,
at)` rechecks current trusted facts in one transaction: active friendship, current
exact grant identity/direction, consent scope/time boundaries, valid session start,
and the session's own interval/scope. A wrong direction, old grant, invalid fact,
terminated friendship, revoked consent or expired session returns `None`.
No allow decision is cached. Evaluation times must be explicit timezone-aware
instants and are not identity claims. UTC instants survive timezone-offset round trips.

Relationship-dependent transitions and active-session reads acquire row locks in
`friendship -> permission -> session` order. At PostgreSQL READ COMMITTED, a read
following committed termination/revocation observes denial. This does not promise
that a returned snapshot remains valid after another transaction commits: any future
actual disclosure must recheck immediately before disclosure.

Ending a session deletes it. Re-grant and friendship termination remove obsolete
session activity metadata. Revoked session records remain bound to revoked facts
until ended/expired, preserving exact evaluation boundaries. Call
`cleanup_expired_sessions(at)` to delete rows expiring at or before an explicit
instant. There is no scheduler or permanent session-history ledger; retention
cleanup should be invoked by future operational code. Expiry correctness always
comes from read-time evaluation, regardless of whether cleanup has run.

## Configuration and commands

Configure an external uv environment first. From the repository root in PowerShell:

```powershell
$env:UV_PROJECT_ENVIRONMENT = Join-Path $env:TEMP 'commonroom-burrow-clock-api-venv'
uv lock --check
uv sync --frozen --all-packages
uv run --frozen --project apps/burrow-clock/api pytest apps/burrow-clock/api/tests
```

Production configuration reads `BURROW_CLOCK_DATABASE_URL` only on the first
authenticated persistence-dependent call. It accepts `postgresql://` and `postgresql+psycopg://`,
normalizing to psycopg v3, and rejects other schemes without SQLite fallback.
Set a development database URL through your environment, migrate explicitly,
then start the API:

```sh
uv run --frozen --project apps/burrow-clock/api alembic -c apps/burrow-clock/api/alembic.ini upgrade head
uv run --frozen --project apps/burrow-clock/api uvicorn burrow_clock_api.main:app --reload
```

The public health endpoint is `http://127.0.0.1:8000/api/v1/health`; protected routes
return 401 until authentication is integrated, even if a database is configured.
For disposable schema teardown only, Alembic supports `downgrade base`.
Do not run downgrade against data you want to retain. No database URL or credentials
belong in committed configuration. Migrations never run automatically.

Live tests use only `BURROW_CLOCK_TEST_DATABASE_URL`, pointing to a dedicated
synthetic PostgreSQL test database. They never fall back to the production variable.
Tests and migration round trips delete test metadata, so this must be disposable.
Explicit Alembic URL configuration takes priority, then the test variable, then the
normal database variable. Never target a real user database for test migrations.

Fast repository checks run on SQLite and are labeled separately. They are useful
for domain mapping and rollback, but do not prove PostgreSQL timezone handling,
partial indexes or row locking. PostgreSQL cases exercise the same behaviors plus
migration, FK, timestamp and concurrency tests; without the test URL they skip with
an explicit reason. SQLite timestamp normalization exists only for the explicitly
supplied unit-test dialect, not production configuration.

Burrow's API CI independently runs PostgreSQL 17, upgrades `0001`, and runs the
complete suite. `BURROW_CLOCK_REQUIRE_POSTGRES_TESTS=1` makes missing or skipped live
coverage fail CI. Synthetic service credentials are for the disposable CI database.

Repository checks, from the root:

```sh
python scripts/validate_repository.py
python scripts/validate_toolchain.py
python scripts/validate_contract_schemas.py
python -m unittest discover -s scripts/tests
```

The mobile shell remains unconnected. Real authentication, accounts, invitations,
actual presence/location disclosure, GPS, geofencing, WebSockets, maps and background
cleanup remain deferred. No schema migration or new dependency is needed for Commit 23.
