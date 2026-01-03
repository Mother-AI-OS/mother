#!/usr/bin/env python3
"""Mother Credentials Manager - Centralized credential management."""

import os
import sys
import re
from pathlib import Path
from typing import Optional


CREDENTIALS_FILE = Path.home() / ".config" / "mother" / "credentials.env"

# Category prefixes for grouping
CATEGORIES = {
    "AI API Keys": ["ANTHROPIC_", "OPENAI_", "CLAUDE_"],
    "Mother Agent": ["MOTHER_"],
    "Mailcraft": ["MAILCRAFT_", "BEA_", "LETTERXPRESS_"],
    "Taxlord": ["DATABASE_", "POSTGRES_", "ELSTER_", "DEFAULT_LEDGER"],
    "General": ["LOG_", "MAX_", "TOOL_"],
}


def ensure_file_exists():
    """Ensure the credentials file exists."""
    CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.touch(mode=0o600)
        print(f"Created credentials file: {CREDENTIALS_FILE}")


def read_credentials() -> dict[str, str]:
    """Read all credentials from the file."""
    ensure_file_exists()
    credentials = {}
    if CREDENTIALS_FILE.exists():
        with open(CREDENTIALS_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    credentials[key.strip()] = value.strip()
    return credentials


def write_credentials(credentials: dict[str, str]):
    """Write credentials to the file with proper categorization."""
    ensure_file_exists()

    with open(CREDENTIALS_FILE, "w") as f:
        f.write("# ============================================================\n")
        f.write("# Mother Central Credentials\n")
        f.write("# Managed via: mother credentials\n")
        f.write("# ============================================================\n\n")

        written_keys = set()

        for category, prefixes in CATEGORIES.items():
            category_items = []
            for key, value in credentials.items():
                if key in written_keys:
                    continue
                for prefix in prefixes:
                    if key.startswith(prefix) or key == prefix:
                        category_items.append((key, value))
                        written_keys.add(key)
                        break

            if category_items:
                f.write(f"# ============================================================\n")
                f.write(f"# {category}\n")
                f.write(f"# ============================================================\n")
                for key, value in sorted(category_items):
                    f.write(f"{key}={value}\n")
                f.write("\n")

        # Write any remaining uncategorized items
        remaining = [(k, v) for k, v in credentials.items() if k not in written_keys]
        if remaining:
            f.write("# ============================================================\n")
            f.write("# Other\n")
            f.write("# ============================================================\n")
            for key, value in sorted(remaining):
                f.write(f"{key}={value}\n")

    os.chmod(CREDENTIALS_FILE, 0o600)


def mask_value(value: str) -> str:
    """Mask a credential value for display."""
    if not value:
        return "(empty)"
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def list_credentials(show_values: bool = False):
    """List all credentials."""
    credentials = read_credentials()
    if not credentials:
        print("No credentials configured.")
        return

    print(f"\n{'Key':<45} {'Value':<50}")
    print("-" * 95)

    for key, value in sorted(credentials.items()):
        display_value = value if show_values else mask_value(value)
        print(f"{key:<45} {display_value:<50}")

    print(f"\nTotal: {len(credentials)} credentials")
    print(f"File: {CREDENTIALS_FILE}")


def get_credential(key: str) -> Optional[str]:
    """Get a specific credential."""
    credentials = read_credentials()
    return credentials.get(key)


def set_credential(key: str, value: str):
    """Set a credential."""
    credentials = read_credentials()
    old_value = credentials.get(key)
    credentials[key] = value
    write_credentials(credentials)

    if old_value:
        print(f"Updated: {key}")
    else:
        print(f"Added: {key}")


def delete_credential(key: str) -> bool:
    """Delete a credential."""
    credentials = read_credentials()
    if key in credentials:
        del credentials[key]
        write_credentials(credentials)
        print(f"Deleted: {key}")
        return True
    else:
        print(f"Key not found: {key}")
        return False


def search_credentials(pattern: str):
    """Search credentials by key pattern."""
    credentials = read_credentials()
    regex = re.compile(pattern, re.IGNORECASE)
    matches = {k: v for k, v in credentials.items() if regex.search(k)}

    if not matches:
        print(f"No credentials matching '{pattern}'")
        return

    print(f"\n{'Key':<45} {'Value (masked)':<50}")
    print("-" * 95)
    for key, value in sorted(matches.items()):
        print(f"{key:<45} {mask_value(value):<50}")
    print(f"\nFound: {len(matches)} matching credentials")


def interactive_edit():
    """Open credentials file in editor."""
    editor = os.environ.get("EDITOR", "nano")
    os.system(f"{editor} {CREDENTIALS_FILE}")


def print_usage():
    """Print usage information."""
    print("""
Mother Credentials Manager

Usage: mother credentials <command> [args]

Commands:
  list                  List all credentials (masked)
  list --show           List all credentials (unmasked)
  get <KEY>             Get a specific credential value
  set <KEY> <VALUE>     Set a credential
  delete <KEY>          Delete a credential
  search <PATTERN>      Search credentials by key pattern
  edit                  Open credentials file in editor
  path                  Show credentials file path

Examples:
  mother credentials list
  mother credentials set OPENAI_API_KEY sk-abc123...
  mother credentials get ANTHROPIC_API_KEY
  mother credentials search API_KEY
  mother credentials delete OLD_KEY
""")


def main():
    """Main entry point."""
    args = sys.argv[1:]

    if not args:
        print_usage()
        return

    command = args[0].lower()

    if command == "list":
        show_values = "--show" in args or "-s" in args
        list_credentials(show_values)

    elif command == "get":
        if len(args) < 2:
            print("Usage: mother credentials get <KEY>")
            return
        value = get_credential(args[1])
        if value:
            print(value)
        else:
            print(f"Key not found: {args[1]}")
            sys.exit(1)

    elif command == "set":
        if len(args) < 3:
            print("Usage: mother credentials set <KEY> <VALUE>")
            return
        set_credential(args[1], " ".join(args[2:]))

    elif command == "delete" or command == "rm":
        if len(args) < 2:
            print("Usage: mother credentials delete <KEY>")
            return
        if not delete_credential(args[1]):
            sys.exit(1)

    elif command == "search":
        if len(args) < 2:
            print("Usage: mother credentials search <PATTERN>")
            return
        search_credentials(args[1])

    elif command == "edit":
        interactive_edit()

    elif command == "path":
        print(CREDENTIALS_FILE)

    elif command == "--help" or command == "-h":
        print_usage()

    else:
        print(f"Unknown command: {command}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
