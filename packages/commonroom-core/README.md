# Commonroom Core (`commonroom-core`)

Shared data contracts, domain types, and cross-application primitives for the **Commonroom** ecosystem.

---

## 1. Role and Boundaries

`packages/commonroom-core` is the single source of truth for cross-product domain contracts shared between Hogwarts Trials, Pensieve, and The Burrow Clock.

### What Belongs Here
- Shared domain contracts justified by concrete active use in >= 2 applications.
  UserId now meets this threshold through active identity requirements in Hogwarts
  Trials and The Burrow Clock; speculative future reuse does not justify new
  extraction.
- Technology-neutral schema definitions and manifests under [`schemas/`](schemas/).

### What Explicitly Does NOT Belong Here
- ❌ Application-specific business logic (e.g., quiz grading algorithms, AI prompting logic, geofence computations).
- ❌ UI components or framework code.
- ❌ Database models, migrations, or ORM definitions.
- ❌ Direct dependencies on or imports from any `apps/*` directory.

---

## 2. Technology-Neutral Source of Truth

- **Canonical Format**: All domain contracts are authored as neutral **JSON Schema (Draft 2020-12)** documents located in [`schemas/v1/`](schemas/v1/).
- **Language Adapters**: Future language-specific representations (e.g., TypeScript types, Python Pydantic models) may be generated or adapted from these neutral schemas, but generated artifacts must **never** replace the JSON Schema files as the canonical source of truth.
- **Independent Consumption**: The permitted dependency direction is `apps/* -> packages/commonroom-core`. Current product UUID dataclasses remain product-local representations; neither Hogwarts Trials nor The Burrow Clock imports or executes the identity JSON Schemas at runtime. No generated language adapters exist yet. Applications must never directly access or modify peer applications' internal contracts.

### Minimal Identity and Privacy Extraction Boundary

[`UserId`](schemas/v1/user-id.schema.json) is the canonical minimal,
security-neutral user identifier: a UUID-formatted string at serialized
boundaries. Active UUID use in Hogwarts Trials (`AuthenticatedPrincipal.user_id`
and attempt `owner_user_id`) and The Burrow Clock (friendship members and
directional sharing parties) now justifies this shared primitive.

[`UserReference`](schemas/v1/user-reference.schema.json) remains the existing
user-facing cross-product reference envelope with required `user_id` and optional
`display_name`. Its v1 behavior is unchanged. `UserReference.user_id` follows the
same UUID identity semantics as `UserId`; the declaration remains inline to avoid
introducing cross-schema resolver requirements.

Possessing or presenting a user UUID does not authenticate anyone or authorize
access. UUID entropy is not authorization. A UserId is neither a token nor a
credential. `display_name` and profile metadata are presentation-only and must
never be used as authentication keys or for authorization decisions. Product
backends remain responsible for trusted authentication and authorization. Core
defines no global current-user state, roles, or permission logic.

The privacy boundary shares identity minimization only. These concepts remain
product-local:

- Burrow Clock `SharingScope`: PRESENCE / APPROXIMATE / PRECISE describe its
  product-specific disclosure semantics.
- Burrow Clock `ConsentGrant`: only this product currently requires this exact
  activation, expiry, and revocation model.
- Burrow Clock `Friendship`, `SharingPermission`, `is_disclosure_allowed`, and
  `is_friend_disclosure_allowed`: relationship and location-sharing semantics.
- Hogwarts Trials `AttemptOwnership`, `can_access_attempt`,
  `require_attempt_owner`, and `AttemptAccessDeniedError`: resource ownership
  policy, which is not equivalent to friendship or consent.
- Hogwarts Trials `AuthenticatedPrincipal`: an application-level trusted
  authentication value, not a neutral serialized identity schema.

No generic Permission, Consent, Principal, or Access model is extracted. Core
contains neutral data contracts and no product business logic.

---

## 3. Schema Directory & Manifest

All shared schemas are cataloged in the schema manifest:
- **Directory**: [`schemas/`](schemas/)
- **Manifest**: [`schemas/manifest.json`](schemas/manifest.json)
- **Schema Documentation**: [`schemas/README.md`](schemas/README.md)
