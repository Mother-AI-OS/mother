#!/usr/bin/env python3
"""Ecosystem scanner for Mother AI OS.

Scans a projects directory to identify Mother core and tool repos,
reporting their status and integration potential.

Usage:
    python scripts/ecosystem_scan.py
    MOTHER_PROJECTS_ROOT=/opt/projects python scripts/ecosystem_scan.py
    python scripts/ecosystem_scan.py --json
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal


# Known tool repos and their metadata
KNOWN_TOOL_REPOS = {
    "contentcraft": {
        "purpose": "AI content creation for social media, blogs, YouTube",
        "entrypoints": ["content", "contentcraft"],
        "integration": "CLI wrapper, Python plugin",
        "risk": "LOW",
    },
    "datacraft": {
        "purpose": "Document processing, embeddings, vector search",
        "entrypoints": ["datacraft"],
        "integration": "CLI wrapper, Python plugin",
        "risk": "LOW",
    },
    "mailcraft": {
        "purpose": "Email management with LLM categorization",
        "entrypoints": ["mailcraft"],
        "integration": "CLI wrapper, Python plugin",
        "risk": "MEDIUM",
    },
    "leadengine": {
        "purpose": "German tender and lead discovery",
        "entrypoints": ["leads"],
        "integration": "CLI wrapper, REST API",
        "risk": "MEDIUM",
    },
    "lawkraft-transmit": {
        "purpose": "Document transmission (email, fax, post, beA)",
        "entrypoints": [],
        "integration": "Python import",
        "risk": "MEDIUM",
    },
    "taxlord": {
        "purpose": "German tax and bookkeeping with ELSTER",
        "entrypoints": ["taxlord"],
        "integration": "HTTP service, CLI wrapper",
        "risk": "HIGH",
    },
    "acnjxn": {
        "purpose": "Task management with Google Tasks sync",
        "entrypoints": ["acnjxn"],
        "integration": "CLI wrapper, Python plugin",
        "risk": "LOW",
    },
    "helpers": {
        "purpose": "Utility scripts (pdf-merge, transmit)",
        "entrypoints": [],
        "integration": "CLI wrappers",
        "risk": "LOW",
    },
}


@dataclass
class RepoStatus:
    """Status of a repository."""

    name: str
    path: str | None
    present: bool
    is_git_repo: bool
    purpose: str
    entrypoints: list[str]
    integration: str
    risk: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanResult:
    """Result of ecosystem scan."""

    root: str
    mother_path: str | None
    mother_present: bool
    mother_is_git: bool
    tool_repos: list[RepoStatus]
    unknown_repos: list[str]

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "mother": {
                "path": self.mother_path,
                "present": self.mother_present,
                "is_git_repo": self.mother_is_git,
            },
            "tool_repos": [r.to_dict() for r in self.tool_repos],
            "unknown_repos": self.unknown_repos,
        }


def is_git_repo(path: Path) -> bool:
    """Check if a path is a git repository."""
    return (path / ".git").is_dir()


def detect_entrypoints(path: Path) -> list[str]:
    """Detect CLI entrypoints from pyproject.toml."""
    pyproject = path / "pyproject.toml"
    if not pyproject.exists():
        return []

    try:
        content = pyproject.read_text()
        # Simple parsing for [project.scripts] section
        entrypoints = []
        in_scripts = False
        for line in content.split("\n"):
            if "[project.scripts]" in line:
                in_scripts = True
                continue
            if in_scripts:
                if line.startswith("["):
                    break
                if "=" in line:
                    name = line.split("=")[0].strip()
                    if name:
                        entrypoints.append(name)
        return entrypoints
    except Exception:
        return []


def scan_ecosystem(root: Path) -> ScanResult:
    """Scan the ecosystem root for Mother and tool repos."""
    root = root.resolve()

    # Check for Mother
    mother_path = root / "mother"
    mother_present = mother_path.is_dir()
    mother_is_git = is_git_repo(mother_path) if mother_present else False

    # Scan for tool repos
    tool_repos: list[RepoStatus] = []
    unknown_repos: list[str] = []

    for item in sorted(root.iterdir()):
        if not item.is_dir():
            continue

        name = item.name

        # Skip mother (it's the core, not a tool)
        if name == "mother":
            continue

        # Skip hidden directories
        if name.startswith("."):
            continue

        # Check if it's a known tool repo
        if name in KNOWN_TOOL_REPOS:
            meta = KNOWN_TOOL_REPOS[name]
            detected_entrypoints = detect_entrypoints(item)

            tool_repos.append(
                RepoStatus(
                    name=name,
                    path=str(item) if item.is_dir() else None,
                    present=True,
                    is_git_repo=is_git_repo(item),
                    purpose=meta["purpose"],
                    entrypoints=detected_entrypoints or meta["entrypoints"],
                    integration=meta["integration"],
                    risk=meta["risk"],
                )
            )
        else:
            # Unknown repo - might be user's custom tool
            unknown_repos.append(name)

    # Add missing known repos
    found_names = {r.name for r in tool_repos}
    for name, meta in KNOWN_TOOL_REPOS.items():
        if name not in found_names:
            tool_repos.append(
                RepoStatus(
                    name=name,
                    path=None,
                    present=False,
                    is_git_repo=False,
                    purpose=meta["purpose"],
                    entrypoints=meta["entrypoints"],
                    integration=meta["integration"],
                    risk=meta["risk"],
                )
            )

    # Sort by name
    tool_repos.sort(key=lambda r: r.name)

    return ScanResult(
        root=str(root),
        mother_path=str(mother_path) if mother_present else None,
        mother_present=mother_present,
        mother_is_git=mother_is_git,
        tool_repos=tool_repos,
        unknown_repos=unknown_repos,
    )


def print_text_report(result: ScanResult) -> None:
    """Print a human-readable report."""
    print("=" * 60)
    print("Mother Ecosystem Scan")
    print("=" * 60)
    print()
    print(f"Root: {result.root}")
    print()

    # Mother status
    if result.mother_present:
        git_status = "(git repo)" if result.mother_is_git else "(not a git repo)"
        print(f"Mother Core: {result.mother_path} {git_status}")
    else:
        print("Mother Core: NOT FOUND")
        print("  Warning: Mother is not present in this directory.")
        print("  This scanner is designed to run from the Mother repo.")
    print()

    # Tool repos
    print("Tool Repos:")
    print("-" * 60)

    present_repos = [r for r in result.tool_repos if r.present]
    missing_repos = [r for r in result.tool_repos if not r.present]

    if present_repos:
        print()
        print("Found:")
        for repo in present_repos:
            git_marker = "*" if repo.is_git_repo else " "
            entrypoints = ", ".join(repo.entrypoints) if repo.entrypoints else "(library)"
            risk_color = {"LOW": "", "MEDIUM": "[!]", "HIGH": "[!!]"}.get(repo.risk, "")
            print(f"  {git_marker} {repo.name:<20} CLI: {entrypoints:<15} {risk_color}")
            print(f"      {repo.purpose}")
        print()
        print("  (* = git repository)")

    if missing_repos:
        print()
        print("Not Present (optional):")
        for repo in missing_repos:
            print(f"    {repo.name:<20} {repo.purpose}")

    if result.unknown_repos:
        print()
        print("Unknown Directories (not in catalog):")
        for name in result.unknown_repos:
            print(f"    {name}")

    print()
    print("-" * 60)
    print("Summary:")
    print(f"  Mother: {'Present' if result.mother_present else 'Missing'}")
    print(f"  Tool repos found: {len(present_repos)}/{len(result.tool_repos)}")
    print(f"  Unknown dirs: {len(result.unknown_repos)}")
    print()
    print("For integration details, see: docs/ecosystem/OVERVIEW.md")


def print_json_report(result: ScanResult) -> None:
    """Print a JSON report."""
    print(json.dumps(result.to_dict(), indent=2))


def main() -> int:
    """Main entry point."""
    # Get projects root from environment or default
    root_env = os.environ.get("MOTHER_PROJECTS_ROOT")
    if root_env:
        root = Path(root_env)
    else:
        # Default: parent of the mother repo (assuming script is in mother/scripts/)
        script_path = Path(__file__).resolve()
        mother_root = script_path.parent.parent
        root = mother_root.parent

    # Check for --json flag
    output_json = "--json" in sys.argv

    # Validate root exists
    if not root.is_dir():
        print(f"Error: Root directory does not exist: {root}", file=sys.stderr)
        return 1

    # Scan
    result = scan_ecosystem(root)

    # Output
    if output_json:
        print_json_report(result)
    else:
        print_text_report(result)

    # Return success even if repos are missing (they're optional)
    return 0


if __name__ == "__main__":
    sys.exit(main())
