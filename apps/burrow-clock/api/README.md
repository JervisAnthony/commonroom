# The Burrow Clock API

The current FastAPI API is health-only: `GET /api/v1/health`. Importing
`burrow_clock_api.main:app` requires no database URL, opens no connection, creates
no tables, runs no migrations, and performs no application filesystem writes.
The mobile shell is unchanged and is not connected to persistence.

Commit 21 adds product-local PostgreSQL 17 persistence using SQLAlchemy 2.x,
psycopg v3 and Alembic, on Python 3.13+ with the existing uv workspace. Persistence
stores authorization metadata only. It activates no GPS/location collection or
actual disclosure, and exposes no public mutation routes. Authentication,
OAuth/OIDC verification, user accounts, friend invitations, blocking workflows,
location streams, geofences, observations, maps and background workers remain deferred.

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
seams, not proof of end-user authentication. Future public mutations must establish
a trusted principal and authorize the acting sharer before invoking these methods.
UUIDs and session IDs are never authentication credentials.

## Privacy enforcement

Sharing remains default-off. Friendship, consent or a stored session alone cannot
authorize disclosure. Reconstruction validates the original immutable domain
contracts; malformed grants/sessions deny rather than becoming authorized facts.
Expired/revoked current permissions may be returned as consent facts for domain
evaluation, never as an allow decision. `get_permission` returns no historical or
reversed record and no permission for an inactive friendship.

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
friendship -> permission -> session order. At PostgreSQL READ COMMITTED, a read
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

Production configuration reads `BURROW_CLOCK_DATABASE_URL` only when explicitly
constructing persistence. It accepts `postgresql://` and `postgresql+psycopg://`,
normalizing to psycopg v3, and rejects other schemes without SQLite fallback.
Set a development database URL through your environment, then run:

```sh
uv run --frozen --project apps/burrow-clock/api alembic -c apps/burrow-clock/api/alembic.ini upgrade head
uv run --frozen --project apps/burrow-clock/api alembic -c apps/burrow-clock/api/alembic.ini downgrade base
```

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
