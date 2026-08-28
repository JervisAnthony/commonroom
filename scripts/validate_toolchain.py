#!/usr/bin/env python3
"""
scripts/validate_toolchain.py

Validates repository toolchain configuration, runtime pins, package manager
metadata, workspace definitions, and lockfile presence.

Standard Library only; zero external dependencies.
Compatible with Python 3.12+ (uses tomllib and json).
Import-safe: does not execute automatically when imported.
"""

import json
import os
import sys
import tomllib
from typing import List, Set

EXPECTED_NODE_VERSION = "24.20.0"
EXPECTED_PYTHON_VERSION = "3.13"
EXPECTED_PACKAGE_MANAGER = "pnpm@11.21.0"
EXPECTED_NODE_ENGINE = ">=24 <25"
EXPECTED_PNPM_ENGINE = ">=11 <12"
EXPECTED_UV_REQUIRED_VERSION = ">=0.12,<0.13"
EXPECTED_UV_REQUIRES_PYTHON = ">=3.13"
EXPECTED_UV_WORKSPACE_MEMBERS = ["apps/*/api"]
EXPECTED_PNPM_WORKSPACE_PACKAGES = {"apps/*/web", "apps/*/mobile", "packages/*"}

FORBIDDEN_ORCHESTRATOR_FILES = [
    "turbo.json",
    "nx.json",
    "pants.toml",
    "BUILD",
    "BUILD.bazel",
]


def get_repo_root() -> str:
    """Return the absolute path to the repository root directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(script_dir, ".."))


def validate_toolchain(repo_root: str) -> List[str]:
    """
    Perform structural and convention checks for the monorepo toolchain.
    Returns a list of failure strings. An empty list indicates successful validation.
    """
    failures: List[str] = []

    # A. .node-version
    node_version_path = os.path.join(repo_root, ".node-version")
    if not os.path.exists(node_version_path):
        failures.append("Missing .node-version file at repository root")
    else:
        try:
            with open(node_version_path, "r", encoding="utf-8") as f:
                node_ver = f.read().strip()
            if node_ver != EXPECTED_NODE_VERSION:
                failures.append(
                    f".node-version must be exactly '{EXPECTED_NODE_VERSION}', got '{node_ver}'"
                )
        except Exception as e:
            failures.append(f"Failed to read .node-version: {e}")

    # B. .python-version
    python_version_path = os.path.join(repo_root, ".python-version")
    if not os.path.exists(python_version_path):
        failures.append("Missing .python-version file at repository root")
    else:
        try:
            with open(python_version_path, "r", encoding="utf-8") as f:
                py_ver = f.read().strip()
            if py_ver != EXPECTED_PYTHON_VERSION:
                failures.append(
                    f".python-version must be exactly '{EXPECTED_PYTHON_VERSION}', got '{py_ver}'"
                )
        except Exception as e:
            failures.append(f"Failed to read .python-version: {e}")

    # C. package.json
    pkg_json_path = os.path.join(repo_root, "package.json")
    if not os.path.exists(pkg_json_path):
        failures.append("Missing package.json file at repository root")
    else:
        try:
            with open(pkg_json_path, "r", encoding="utf-8") as f:
                pkg_data = json.load(f)

            if not isinstance(pkg_data, dict):
                failures.append("package.json root must be an object")
            else:
                if pkg_data.get("name") != "commonroom":
                    failures.append(
                        f"package.json 'name' must be 'commonroom', got '{pkg_data.get('name')}'"
                    )

                if pkg_data.get("private") is not True:
                    failures.append("package.json 'private' must be true")

                if pkg_data.get("packageManager") != EXPECTED_PACKAGE_MANAGER:
                    failures.append(
                        f"package.json 'packageManager' must be '{EXPECTED_PACKAGE_MANAGER}', got '{pkg_data.get('packageManager')}'"
                    )

                engines = pkg_data.get("engines", {})
                if not isinstance(engines, dict):
                    failures.append("package.json 'engines' must be an object")
                else:
                    if engines.get("node") != EXPECTED_NODE_ENGINE:
                        failures.append(
                            f"package.json engines.node must be '{EXPECTED_NODE_ENGINE}', got '{engines.get('node')}'"
                        )
                    if engines.get("pnpm") != EXPECTED_PNPM_ENGINE:
                        failures.append(
                            f"package.json engines.pnpm must be '{EXPECTED_PNPM_ENGINE}', got '{engines.get('pnpm')}'"
                        )

                if pkg_data.get("dependencies"):
                    failures.append(
                        "Root package.json must not declare runtime dependencies during toolchain bootstrap"
                    )

                if pkg_data.get("devDependencies"):
                    failures.append(
                        "Root package.json must not declare devDependencies during toolchain bootstrap"
                    )

                scripts = pkg_data.get("scripts", {})
                if not isinstance(scripts, dict):
                    failures.append("package.json 'scripts' must be an object")
                else:
                    for req_script in ["validate", "validate:contracts", "validate:toolchain"]:
                        if req_script not in scripts:
                            failures.append(f"package.json is missing required script '{req_script}'")
        except UnicodeDecodeError as e:
            failures.append(f"package.json is not valid UTF-8: {e}")
        except json.JSONDecodeError as e:
            failures.append(f"package.json contains invalid JSON: {e}")
        except Exception as e:
            failures.append(f"Failed to read package.json: {e}")

    # D. pnpm-workspace.yaml
    pnpm_workspace_path = os.path.join(repo_root, "pnpm-workspace.yaml")
    if not os.path.exists(pnpm_workspace_path):
        failures.append("Missing pnpm-workspace.yaml at repository root")
    else:
        try:
            with open(pnpm_workspace_path, "r", encoding="utf-8") as f:
                content = f.read()
            # Simple line-based extraction of listed package globs
            extracted_packages: Set[str] = set()
            in_packages_section = False
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("packages:"):
                    in_packages_section = True
                    continue
                if in_packages_section:
                    if stripped.startswith("-"):
                        raw_glob = stripped.lstrip("-").strip().strip('"').strip("'")
                        extracted_packages.add(raw_glob)
                    elif stripped and not stripped.startswith("#"):
                        # Reached next top-level key
                        in_packages_section = False

            if extracted_packages != EXPECTED_PNPM_WORKSPACE_PACKAGES:
                failures.append(
                    f"pnpm-workspace.yaml packages must match {sorted(EXPECTED_PNPM_WORKSPACE_PACKAGES)}, got {sorted(extracted_packages)}"
                )
        except Exception as e:
            failures.append(f"Failed to read pnpm-workspace.yaml: {e}")

    # E. pnpm-lock.yaml
    pnpm_lock_path = os.path.join(repo_root, "pnpm-lock.yaml")
    if not os.path.exists(pnpm_lock_path):
        failures.append("Missing pnpm-lock.yaml at repository root")
    else:
        if os.path.getsize(pnpm_lock_path) == 0:
            failures.append("pnpm-lock.yaml exists but is empty")

    # F. pyproject.toml
    pyproject_path = os.path.join(repo_root, "pyproject.toml")
    if not os.path.exists(pyproject_path):
        failures.append("Missing pyproject.toml at repository root")
    else:
        try:
            with open(pyproject_path, "rb") as f:
                pyproject_data = tomllib.load(f)

            project_table = pyproject_data.get("project", {})
            if not isinstance(project_table, dict):
                failures.append("pyproject.toml must declare a [project] table")
            else:
                if project_table.get("name") != "commonroom-workspace":
                    failures.append(
                        f"pyproject.toml project.name must be 'commonroom-workspace', got '{project_table.get('name')}'"
                    )
                if project_table.get("version") != "0.0.0":
                    failures.append(
                        f"pyproject.toml project.version must be '0.0.0', got '{project_table.get('version')}'"
                    )
                if project_table.get("requires-python") != EXPECTED_UV_REQUIRES_PYTHON:
                    failures.append(
                        f"pyproject.toml project.requires-python must be '{EXPECTED_UV_REQUIRES_PYTHON}', got '{project_table.get('requires-python')}'"
                    )
                if project_table.get("dependencies") != []:
                    failures.append(
                        "pyproject.toml project.dependencies must be empty in root workspace"
                    )

            tool_uv = pyproject_data.get("tool", {}).get("uv", {})
            if not isinstance(tool_uv, dict):
                failures.append("pyproject.toml must declare a [tool.uv] table")
            else:
                if tool_uv.get("package") is not False:
                    failures.append("pyproject.toml tool.uv.package must be false (virtual workspace root)")
                if tool_uv.get("required-version") != EXPECTED_UV_REQUIRED_VERSION:
                    failures.append(
                        f"pyproject.toml tool.uv.required-version must be '{EXPECTED_UV_REQUIRED_VERSION}', got '{tool_uv.get('required-version')}'"
                    )
                workspace_members = tool_uv.get("workspace", {}).get("members")
                if workspace_members != EXPECTED_UV_WORKSPACE_MEMBERS:
                    failures.append(
                        f"pyproject.toml tool.uv.workspace.members must be {EXPECTED_UV_WORKSPACE_MEMBERS}, got {workspace_members}"
                    )

            if "build-system" in pyproject_data:
                failures.append(
                    "pyproject.toml must not declare a [build-system] table in virtual workspace root"
                )
        except tomllib.TOMLDecodeError as e:
            failures.append(f"pyproject.toml contains invalid TOML: {e}")
        except Exception as e:
            failures.append(f"Failed to read pyproject.toml: {e}")

    # G. uv.lock
    uv_lock_path = os.path.join(repo_root, "uv.lock")
    if not os.path.exists(uv_lock_path):
        failures.append("Missing uv.lock at repository root")
    else:
        if os.path.getsize(uv_lock_path) == 0:
            failures.append("uv.lock exists but is empty")

    # H. Forbidden heavy orchestrator files at root
    for forbidden in FORBIDDEN_ORCHESTRATOR_FILES:
        forbidden_path = os.path.join(repo_root, forbidden)
        if os.path.exists(forbidden_path):
            failures.append(
                f"Forbidden orchestrator file '{forbidden}' detected at repository root"
            )

    return failures


def main() -> int:
    repo_root = get_repo_root()
    print("=" * 60)
    print(" Commonroom Monorepo Toolchain Validation")
    print(f" Root: {repo_root}")
    print("=" * 60)

    failures = validate_toolchain(repo_root)

    if not failures:
        print("[PASS] Monorepo Toolchain Baseline")
        print("-" * 60)
        print("[SUCCESS] All toolchain configurations and lockfiles are valid.")
        return 0
    else:
        print("[FAIL] Monorepo Toolchain Baseline")
        for err in failures:
            print(f"       - {err}")
        print("-" * 60)
        print(f"[FAILURE] Toolchain validation failed with {len(failures)} error(s).")
        return 1


if __name__ == "__main__":
    sys.exit(main())

