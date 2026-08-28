#!/usr/bin/env python3
"""
scripts/validate_repository.py

Technology-neutral repository validator for the Commonroom ecosystem.
Validates required foundation paths, relative markdown links, absence of
forbidden sensitive files, and cross-application boundary invariants.

Standard Library only; zero external dependencies.
"""

import os
import re
import sys
from typing import List, Tuple

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from validate_contract_schemas import validate_contract_schemas
from validate_toolchain import validate_toolchain

# Core apps recognized in the ecosystem
ECOSYSTEM_APPS = ["hogwarts-trials", "pensieve", "burrow-clock"]

# Required repository paths for the ecosystem foundation
REQUIRED_PATHS = [
    ".node-version",
    ".python-version",
    "package.json",
    "pnpm-workspace.yaml",
    "pnpm-lock.yaml",
    "pyproject.toml",
    "uv.lock",
    "AGENTS.md",
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    os.path.join("apps", "hogwarts-trials"),
    os.path.join("apps", "pensieve"),
    os.path.join("apps", "burrow-clock"),
    os.path.join("packages", "commonroom-core"),
    os.path.join("packages", "commonroom-core", "README.md"),
    os.path.join("packages", "commonroom-core", "schemas", "README.md"),
    os.path.join("packages", "commonroom-core", "schemas", "manifest.json"),
    os.path.join("packages", "commonroom-core", "schemas", "v1", "house.schema.json"),
    os.path.join("packages", "commonroom-core", "schemas", "v1", "user-reference.schema.json"),
    os.path.join("packages", "commonroom-core", "schemas", "v1", "api-error.schema.json"),
    os.path.join("docs", "architecture.md"),
    os.path.join("docs", "technology-architecture.md"),
    os.path.join("docs", "product-vision.md"),
    os.path.join("docs", "ip-and-content-boundaries.md"),
    os.path.join("docs", "development-toolchain.md"),
    os.path.join("docs", "adr", "README.md"),
    os.path.join("docs", "adr", "0001-client-platforms.md"),
    os.path.join("docs", "adr", "0002-backend-and-api.md"),
    os.path.join("docs", "adr", "0003-data-and-retrieval.md"),
    os.path.join("docs", "adr", "0004-monorepo-and-shared-contracts.md"),
    os.path.join("scripts", "validate_contract_schemas.py"),
    os.path.join("scripts", "validate_toolchain.py"),
    os.path.join(".github", "workflows", "toolchain-validation.yml"),
]

# Sensitive / forbidden filenames and patterns
FORBIDDEN_EXACT_FILENAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.staging",
}

FORBIDDEN_EXTENSIONS = {
    ".pem",
    ".key",
}

# Whitelisted safe template patterns
ALLOWED_TEMPLATE_SUFFIXES = (
    ".example",
    ".sample",
    ".template",
)


def get_repo_root() -> str:
    """Return the absolute path to the repository root directory."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(script_dir, ".."))


def check_required_paths(repo_root: str) -> List[str]:
    """Validate that all foundational files and directories exist."""
    failures = []
    for rel_path in REQUIRED_PATHS:
        full_path = os.path.join(repo_root, rel_path)
        if not os.path.exists(full_path):
            failures.append(f"Missing required path: {rel_path}")
    return failures


def check_forbidden_files(repo_root: str) -> List[str]:
    """Ensure no forbidden secret, key, or local env files exist in the repository."""
    failures = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        # Skip git directory
        if ".git" in dirpath.split(os.sep):
            continue

        for fname in filenames:
            rel_path = os.path.relpath(os.path.join(dirpath, fname), repo_root)
            lower_name = fname.lower()

            # Check exact forbidden file names (ignoring safe templates like .env.example)
            if lower_name in FORBIDDEN_EXACT_FILENAMES:
                failures.append(f"Forbidden sensitive file found: {rel_path}")
                continue

            # Check forbidden extensions, unless safe template suffix
            is_template = any(lower_name.endswith(sfx) for sfx in ALLOWED_TEMPLATE_SUFFIXES)
            if not is_template:
                _, ext = os.path.splitext(lower_name)
                if ext in FORBIDDEN_EXTENSIONS:
                    failures.append(f"Forbidden sensitive key/cert file found: {rel_path}")

    return failures


def check_markdown_links(repo_root: str) -> List[str]:
    """Validate local relative links in all markdown files."""
    failures = []
    link_pattern = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

    for dirpath, dirnames, filenames in os.walk(repo_root):
        if ".git" in dirpath.split(os.sep):
            continue

        for fname in filenames:
            if not fname.endswith(".md"):
                continue

            fpath = os.path.join(dirpath, fname)
            rel_fpath = os.path.relpath(fpath, repo_root)

            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                failures.append(f"Could not read markdown file {rel_fpath}: {e}")
                continue

            for match in link_pattern.finditer(content):
                target_raw = match.group(2).strip()

                # Skip web protocols, mailto, and pure in-page anchors
                if target_raw.startswith(("http://", "https://", "mailto:", "#")):
                    continue

                # Strip anchor and query strings if present
                clean_target = target_raw.split("#")[0].split("?")[0].strip()
                if not clean_target:
                    continue

                # Resolve relative to current markdown file
                resolved_target = os.path.normpath(os.path.join(dirpath, clean_target))
                if not os.path.exists(resolved_target):
                    failures.append(
                        f"Broken link in {rel_fpath}: '{target_raw}' -> target not found ({os.path.relpath(resolved_target, repo_root)})"
                    )

    return failures


def check_cross_app_boundaries(repo_root: str) -> List[str]:
    """
    Ensure application files do not create direct relative path dependencies
    into other applications' private internal directories.
    """
    failures = []
    apps_dir = os.path.join(repo_root, "apps")
    if not os.path.exists(apps_dir):
        return failures

    for app_name in ECOSYSTEM_APPS:
        app_path = os.path.join(apps_dir, app_name)
        if not os.path.exists(app_path):
            continue

        other_apps = [a for a in ECOSYSTEM_APPS if a != app_name]

        for dirpath, _, filenames in os.walk(app_path):
            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                rel_fpath = os.path.relpath(fpath, repo_root)

                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                except Exception:
                    continue

                for line_idx, line in enumerate(lines, 1):
                    for other in other_apps:
                        # Detect direct relative directory references or cross-app relative imports
                        # e.g., ../pensieve or apps/pensieve
                        if f"../{other}" in line or f"apps/{other}" in line:
                            failures.append(
                                f"Boundary violation in {rel_fpath}:{line_idx}: direct reference to forbidden peer app '{other}'"
                            )

    return failures


def main() -> int:
    repo_root = get_repo_root()
    print("=" * 60)
    print(" Commonroom Repository Validation")
    print(f" Root: {repo_root}")
    print("=" * 60)

    checks: List[Tuple[str, callable]] = [
        ("Required Foundation Paths", lambda: check_required_paths(repo_root)),
        ("Forbidden / Secret Files", lambda: check_forbidden_files(repo_root)),
        ("Relative Markdown Links", lambda: check_markdown_links(repo_root)),
        ("Cross-Application Boundary Invariants", lambda: check_cross_app_boundaries(repo_root)),
        ("Shared Contract Schemas", lambda: validate_contract_schemas(repo_root)),
        ("Toolchain Baseline", lambda: validate_toolchain(repo_root)),
    ]

    total_failures = 0

    for check_name, check_fn in checks:
        failures = check_fn()
        if not failures:
            print(f"[PASS] {check_name}")
        else:
            print(f"[FAIL] {check_name}")
            for err in failures:
                print(f"       - {err}")
            total_failures += len(failures)

    print("-" * 60)
    if total_failures == 0:
        print("[SUCCESS] All repository validation checks passed.")
        return 0
    else:
        print(f"[FAILURE] Repository validation failed with {total_failures} error(s).")
        return 1


if __name__ == "__main__":
    sys.exit(main())

