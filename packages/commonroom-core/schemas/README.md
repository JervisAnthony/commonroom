# Commonroom Core Schemas

This directory contains the canonical, technology-neutral data contracts for the **Commonroom** ecosystem, authored in **JSON Schema Draft 2020-12**.

---

## 1. Dialect and Identification Conventions

- **Dialect**: `https://json-schema.org/draft/2020-12/schema`
- **Schema ID (`$id`) Namespace**: `urn:commonroom:schema:v1:<contract-name>`
  - Uses stable, domain-independent URN identifiers to ensure portable identification across environments.
- **Manifest**: [manifest.json](manifest.json) tracks all active contracts, relative file paths, titles, and schema IDs.

---

## 2. Versioning & Evolution Principles

1. **Namespace Versioning (`v1/`)**:
   - All initial contracts reside under the `v1/` directory and use the `v1` URN namespace.
2. **Backward-Compatible Evolution**:
   - Additive changes (e.g., adding an optional property with a default, broadening validation safely) may occur within the `v1` namespace following review.
3. **Breaking Changes**:
   - Structural breaking changes (e.g., removing fields, changing types, making optional fields required) must **never** silently overwrite existing contracts.
   - Breaking modifications require an explicit new versioned namespace (e.g., `v2/`) accompanied by an architectural migration plan.

---

## 3. Inclusion Criteria

To be accepted into `packages/commonroom-core/schemas/`:
1. **Multi-Product Consumer Requirement**: The concept must be actively consumed by at least two Commonroom applications.
2. **Technology Neutrality**: Schemas must not contain language-specific or vendor-specific constructs (e.g., no framework decorators, database column types, or proprietary provider fields).
3. **Zero Business Logic**: Schemas define data contracts only; domain logic, scoring algorithms, and geofence evaluations belong in application services.
4. **Privacy & Security Constraints**: Schemas must avoid embedding sensitive tokens, raw GPS coordinate streams, or unauthorized PII.
5. **IP Compliance**: Schemas must contain no copyrighted franchise text, narrative lore passages, character dialogue, or ripped media assets.

---

## 4. Current Schema Contracts (`v1/`)

| Contract Name | Schema File | `$id` | Description |
| :--- | :--- | :--- | :--- |
| **House** | [`v1/house.schema.json`](v1/house.schema.json) | `urn:commonroom:schema:v1:house` | Normalized enum identifier for Hogwarts house affiliation (`gryffindor`, `hufflepuff`, `ravenclaw`, `slytherin`). |
| **UserReference** | [`v1/user-reference.schema.json`](v1/user-reference.schema.json) | `urn:commonroom:schema:v1:user-reference` | Minimal cross-product user identity reference (`user_id` UUID and optional `display_name`). |
| **ApiError** | [`v1/api-error.schema.json`](v1/api-error.schema.json) | `urn:commonroom:schema:v1:api-error` | Standard error response envelope with machine `code`, safe `message`, and optional `correlation_id` / `details`. |

---

## 5. Automated Validation & Scope

- **Structural and Manifest Validation**: The automated validator [`scripts/validate_contract_schemas.py`](../../../scripts/validate_contract_schemas.py) performs repository-level structural checks, dialect header verification, path containment, and manifest-consistency validation without external dependencies.
- **Validation Scope**: This script performs repository-level structural and manifest-integrity checks; it does not implement the complete JSON Schema specification or replace formal Draft 2020-12 meta-schema validation.
- **Future Tooling**: Full semantic and meta-schema validation against the Draft 2020-12 specification may be integrated into project CI once workspace dependency tooling is established.

