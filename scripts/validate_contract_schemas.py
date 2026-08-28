#!/usr/bin/env python3
"""
scripts/validate_contract_schemas.py

Validates structural integrity, manifest consistency, and dialect compliance
of shared JSON Schema contracts in packages/commonroom-core.

Standard Library only; zero external dependencies.
Import-safe: does not execute automatically when imported.
"""

import json
import os
import sys
from typing import List, Dict, Any, Set

APPROVED_DIALECT = "https://json-schema.org/draft/2020-12/schema"
APPROVED_ID_PREFIX = "urn:commonroom:schema:v1:"


def get_repo_root() -> str:
    """Return the absolute path to the repository root directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(script_dir, ".."))


def validate_contract_schemas(repo_root: str) -> List[str]:
    """
    Perform structural integrity and consistency checks across shared contract schemas.
    Returns a list of failure strings. An empty list indicates successful validation.
    """
    failures: List[str] = []
    schemas_dir = os.path.join(repo_root, "packages", "commonroom-core", "schemas")
    manifest_path = os.path.join(schemas_dir, "manifest.json")

    # 1. Check manifest exists and is valid JSON
    if not os.path.exists(manifest_path):
        return [f"Missing schema manifest at: {os.path.relpath(manifest_path, repo_root)}"]

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except UnicodeDecodeError as e:
        return [f"Schema manifest is not valid UTF-8: {e}"]
    except json.JSONDecodeError as e:
        return [f"Schema manifest contains invalid JSON: {e}"]
    except Exception as e:
        return [f"Failed to read schema manifest: {e}"]

    # Validate manifest top-level fields
    if not isinstance(manifest, dict):
        return ["Schema manifest root must be a JSON object"]

    if manifest.get("$schema") != APPROVED_DIALECT:
        failures.append(
            f"Manifest '$schema' must be '{APPROVED_DIALECT}', got '{manifest.get('$schema')}'"
        )

    if manifest.get("dialect") != APPROVED_DIALECT:
        failures.append(
            f"Manifest 'dialect' must be '{APPROVED_DIALECT}', got '{manifest.get('dialect')}'"
        )

    schemas_list = manifest.get("schemas")
    if not isinstance(schemas_list, list) or len(schemas_list) == 0:
        failures.append("Manifest 'schemas' must be a non-empty list of schema descriptors")
        return failures

    manifest_names: Set[str] = set()
    manifest_paths: Set[str] = set()
    manifest_ids: Set[str] = set()
    manifest_referenced_relpaths: Set[str] = set()

    for idx, entry in enumerate(schemas_list):
        if not isinstance(entry, dict):
            failures.append(f"Manifest entry #{idx + 1} must be an object")
            continue

        name = entry.get("name")
        version = entry.get("version")
        entry_id = entry.get("id")
        rel_path = entry.get("path")
        title = entry.get("title")

        # Check required manifest entry fields
        if not name or not isinstance(name, str):
            failures.append(f"Manifest entry #{idx + 1} is missing a valid 'name'")
            continue

        if not version or not isinstance(version, str):
            failures.append(f"Manifest entry '{name}' is missing a valid 'version'")

        if not entry_id or not isinstance(entry_id, str):
            failures.append(f"Manifest entry '{name}' is missing a valid 'id'")
        elif not entry_id.startswith(APPROVED_ID_PREFIX):
            failures.append(
                f"Manifest entry '{name}' id '{entry_id}' does not use approved prefix '{APPROVED_ID_PREFIX}'"
            )

        if not title or not isinstance(title, str):
            failures.append(f"Manifest entry '{name}' is missing a valid 'title'")

        if not rel_path or not isinstance(rel_path, str):
            failures.append(f"Manifest entry '{name}' is missing a valid 'path'")
            continue

        # Prevent path traversal
        if ".." in rel_path.split("/") or ".." in rel_path.split("\\"):
            failures.append(f"Manifest entry '{name}' path contains forbidden traversal: '{rel_path}'")
            continue

        # Check for duplicates in manifest
        if name in manifest_names:
            failures.append(f"Duplicate contract name in manifest: '{name}'")
        manifest_names.add(name)

        if rel_path in manifest_paths:
            failures.append(f"Duplicate schema path in manifest: '{rel_path}'")
        manifest_paths.add(rel_path)

        if entry_id:
            if entry_id in manifest_ids:
                failures.append(f"Duplicate schema '$id' in manifest: '{entry_id}'")
            manifest_ids.add(entry_id)

        # Normalize relative path for disk check
        norm_rel_path = os.path.normpath(rel_path)
        manifest_referenced_relpaths.add(norm_rel_path)
        full_schema_path = os.path.join(schemas_dir, norm_rel_path)

        if not os.path.exists(full_schema_path):
            failures.append(f"Manifest-listed schema file does not exist: {rel_path}")
            continue

        # 2. Parse schema file
        try:
            with open(full_schema_path, "r", encoding="utf-8") as sf:
                schema_json = json.load(sf)
        except UnicodeDecodeError as e:
            failures.append(f"Schema file is not valid UTF-8 ({rel_path}): {e}")
            continue
        except json.JSONDecodeError as e:
            failures.append(f"Schema file contains invalid JSON ({rel_path}): {e}")
            continue
        except Exception as e:
            failures.append(f"Could not read schema file ({rel_path}): {e}")
            continue

        if not isinstance(schema_json, dict):
            failures.append(f"Schema root must be a JSON object ({rel_path})")
            continue

        # 3. Check schema properties and dialect
        schema_dialect = schema_json.get("$schema")
        if schema_dialect != APPROVED_DIALECT:
            failures.append(
                f"Schema '{rel_path}' declares invalid '$schema': expected '{APPROVED_DIALECT}', got '{schema_dialect}'"
            )

        schema_id = schema_json.get("$id")
        if not schema_id:
            failures.append(f"Schema '{rel_path}' is missing required '$id'")
        else:
            if not schema_id.startswith(APPROVED_ID_PREFIX):
                failures.append(
                    f"Schema '{rel_path}' '$id' '{schema_id}' does not use approved prefix '{APPROVED_ID_PREFIX}'"
                )
            if entry_id and schema_id != entry_id:
                failures.append(
                    f"Schema '{rel_path}' '$id' ('{schema_id}') does not match manifest id ('{entry_id}')"
                )

        schema_title = schema_json.get("title")
        if not schema_title:
            failures.append(f"Schema '{rel_path}' is missing required 'title'")

        schema_desc = schema_json.get("description")
        if not schema_desc:
            failures.append(f"Schema '{rel_path}' is missing required 'description'")

    # 4. Check for orphaned .schema.json files not tracked in manifest
    v1_dir = os.path.join(schemas_dir, "v1")
    if os.path.exists(v1_dir):
        for fname in os.listdir(v1_dir):
            if fname.endswith(".schema.json"):
                rel_v1_file = os.path.normpath(os.path.join("v1", fname))
                if rel_v1_file not in manifest_referenced_relpaths:
                    failures.append(
                        f"Schema file exists on disk but is omitted from manifest: {rel_v1_file}"
                    )

    return failures


def main() -> int:
    repo_root = get_repo_root()
    print("=" * 60)
    print(" Commonroom Shared Contract Schema Validation")
    print(f" Root: {repo_root}")
    print("=" * 60)

    failures = validate_contract_schemas(repo_root)

    if not failures:
        print("[PASS] Shared Contract Schemas Integrity")
        print("-" * 60)
        print("[SUCCESS] All shared contract schemas are valid and consistent.")
        return 0
    else:
        print("[FAIL] Shared Contract Schemas Integrity")
        for err in failures:
            print(f"       - {err}")
        print("-" * 60)
        print(f"[FAILURE] Contract validation failed with {len(failures)} error(s).")
        return 1


if __name__ == "__main__":
    sys.exit(main())

