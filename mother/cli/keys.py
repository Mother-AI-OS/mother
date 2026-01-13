"""API Key Management CLI.

Commands for managing API keys in multi-key authentication mode.
"""

import json
import sys
from datetime import datetime, timedelta

from ..auth.keys import APIKeyStore, get_key_store
from ..auth.models import Role
from ..auth.scopes import get_role_scopes, validate_scopes


def _format_datetime(dt: datetime | None) -> str:
    """Format datetime for display."""
    if dt is None:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _format_scopes(scopes: list[str], max_display: int = 3) -> str:
    """Format scopes list for display."""
    if not scopes:
        return "-"
    if scopes == ["*"]:
        return "* (all)"
    if len(scopes) <= max_display:
        return ", ".join(scopes)
    return f"{', '.join(scopes[:max_display])} (+{len(scopes) - max_display} more)"


def cmd_init(json_output: bool = False) -> int:
    """Initialize the API key store.

    Creates the SQLite database and tables if they don't exist.
    """
    store = get_key_store()
    store.initialize()

    if json_output:
        print(json.dumps({"status": "initialized", "path": str(store.db_path)}))
    else:
        print(f"API key store initialized at: {store.db_path}")

    return 0


def cmd_add(
    name: str,
    role: str = "operator",
    scopes: list[str] | None = None,
    expires_days: int | None = None,
    json_output: bool = False,
) -> int:
    """Add a new API key.

    Args:
        name: Human-readable name for the key (must be unique).
        role: Role for the key (admin/operator/readonly).
        scopes: Optional list of scopes. Defaults to role-based scopes.
        expires_days: Optional number of days until expiration.
        json_output: Output as JSON.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    # Validate role
    try:
        role_enum = Role(role.lower())
    except ValueError:
        valid_roles = ", ".join(r.value for r in Role)
        if json_output:
            print(json.dumps({"error": f"Invalid role: {role}. Must be one of: {valid_roles}"}))
        else:
            print(f"Error: Invalid role '{role}'. Must be one of: {valid_roles}")
        return 1

    # Validate scopes if provided
    if scopes:
        valid, reason = validate_scopes(scopes, role_enum)
        if not valid:
            if json_output:
                print(json.dumps({"error": reason}))
            else:
                print(f"Error: {reason}")
            return 1

    # Calculate expiration
    expires_at = None
    if expires_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_days)

    # Add the key
    store = get_key_store()
    try:
        api_key, raw_key = store.add_key(
            name=name,
            role=role_enum,
            scopes=scopes,
            expires_at=expires_at,
        )
    except ValueError as e:
        if json_output:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error: {e}")
        return 1

    if json_output:
        print(
            json.dumps(
                {
                    "id": api_key.id,
                    "name": api_key.name,
                    "role": api_key.role.value,
                    "scopes": api_key.scopes,
                    "key": raw_key,
                    "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
                }
            )
        )
    else:
        print(f"\nAPI key created successfully!")
        print(f"  Name: {api_key.name}")
        print(f"  Role: {api_key.role.value}")
        print(f"  Scopes: {_format_scopes(api_key.scopes)}")
        if expires_at:
            print(f"  Expires: {_format_datetime(expires_at)}")
        print(f"\n  API Key: {raw_key}")
        print(f"\n  IMPORTANT: Save this key now. It cannot be retrieved later.")

    return 0


def cmd_list(include_revoked: bool = False, json_output: bool = False) -> int:
    """List all API keys.

    Args:
        include_revoked: Include revoked keys in the list.
        json_output: Output as JSON.

    Returns:
        Exit code (0 for success).
    """
    store = get_key_store()
    keys = store.list_keys(include_revoked=include_revoked)

    if json_output:
        print(json.dumps([k.to_dict() for k in keys]))
        return 0

    if not keys:
        print("No API keys found.")
        print("\nUse 'mother keys add <name>' to create one.")
        return 0

    print(f"\nAPI Keys ({len(keys)} total):\n")
    print(f"{'Name':<20} {'Role':<10} {'Status':<10} {'Last Used':<20} {'ID':<16}")
    print("-" * 80)

    for key in keys:
        status = "revoked" if key.revoked else ("expired" if not key.is_valid() else "active")
        last_used = _format_datetime(key.last_used_at)
        print(f"{key.name:<20} {key.role.value:<10} {status:<10} {last_used:<20} {key.id[:16]}")

    return 0


def cmd_info(identifier: str, json_output: bool = False) -> int:
    """Show detailed information about an API key.

    Args:
        identifier: Key ID or name.
        json_output: Output as JSON.

    Returns:
        Exit code (0 for success, 1 if not found).
    """
    store = get_key_store()

    # Try to find by ID first, then by name
    key = store.get_key(identifier)
    if key is None:
        key = store.get_key_by_name(identifier)

    if key is None:
        if json_output:
            print(json.dumps({"error": f"Key not found: {identifier}"}))
        else:
            print(f"Error: Key not found: {identifier}")
        return 1

    if json_output:
        print(json.dumps(key.to_dict()))
        return 0

    print(f"\nAPI Key: {key.name}")
    print("-" * 40)
    print(f"  ID:         {key.id}")
    print(f"  Role:       {key.role.value}")
    print(f"  Status:     {'revoked' if key.revoked else ('expired' if not key.is_valid() else 'active')}")
    print(f"  Created:    {_format_datetime(key.created_at)}")
    print(f"  Expires:    {_format_datetime(key.expires_at)}")
    print(f"  Last Used:  {_format_datetime(key.last_used_at)}")
    if key.revoked:
        print(f"  Revoked:    {_format_datetime(key.revoked_at)}")
    print(f"\n  Scopes:")
    for scope in key.scopes:
        print(f"    - {scope}")
    if key.metadata:
        print(f"\n  Metadata:")
        for k, v in key.metadata.items():
            print(f"    {k}: {v}")

    return 0


def cmd_revoke(identifier: str, yes: bool = False, json_output: bool = False) -> int:
    """Revoke an API key.

    Args:
        identifier: Key ID or name.
        yes: Skip confirmation.
        json_output: Output as JSON.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    store = get_key_store()

    # Try to find by ID first, then by name
    key = store.get_key(identifier)
    if key is None:
        key = store.get_key_by_name(identifier)

    if key is None:
        if json_output:
            print(json.dumps({"error": f"Key not found: {identifier}"}))
        else:
            print(f"Error: Key not found: {identifier}")
        return 1

    if key.revoked:
        if json_output:
            print(json.dumps({"error": "Key is already revoked"}))
        else:
            print(f"Error: Key '{key.name}' is already revoked.")
        return 1

    # Confirm unless --yes
    if not yes and not json_output:
        confirm = input(f"Revoke key '{key.name}'? This cannot be undone. [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Cancelled.")
            return 1

    success = store.revoke_key(key.id)

    if success:
        if json_output:
            print(json.dumps({"status": "revoked", "id": key.id, "name": key.name}))
        else:
            print(f"Key '{key.name}' has been revoked.")
        return 0
    else:
        if json_output:
            print(json.dumps({"error": "Failed to revoke key"}))
        else:
            print("Error: Failed to revoke key.")
        return 1


def cmd_rotate(identifier: str, yes: bool = False, json_output: bool = False) -> int:
    """Rotate an API key (revoke old, create new with same settings).

    Args:
        identifier: Key ID or name.
        yes: Skip confirmation.
        json_output: Output as JSON.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    store = get_key_store()

    # Try to find by ID first, then by name
    key = store.get_key(identifier)
    if key is None:
        key = store.get_key_by_name(identifier)

    if key is None:
        if json_output:
            print(json.dumps({"error": f"Key not found: {identifier}"}))
        else:
            print(f"Error: Key not found: {identifier}")
        return 1

    if key.revoked:
        if json_output:
            print(json.dumps({"error": "Cannot rotate a revoked key"}))
        else:
            print(f"Error: Cannot rotate a revoked key. Create a new one instead.")
        return 1

    # Confirm unless --yes
    if not yes and not json_output:
        print(f"\nRotating key '{key.name}' will:")
        print("  1. Revoke the current key immediately")
        print("  2. Create a new key with the same settings")
        print("\nAny systems using the old key will need to be updated.")
        confirm = input("\nProceed? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Cancelled.")
            return 1

    result = store.rotate_key(key.id)

    if result is None:
        if json_output:
            print(json.dumps({"error": "Failed to rotate key"}))
        else:
            print("Error: Failed to rotate key.")
        return 1

    new_key, raw_key = result

    if json_output:
        print(
            json.dumps(
                {
                    "status": "rotated",
                    "old_id": key.id,
                    "new_id": new_key.id,
                    "name": new_key.name,
                    "key": raw_key,
                }
            )
        )
    else:
        print(f"\nKey rotated successfully!")
        print(f"  Old key '{key.id[:16]}...' has been revoked.")
        print(f"  New key created with ID: {new_key.id[:16]}...")
        print(f"\n  New API Key: {raw_key}")
        print(f"\n  IMPORTANT: Update your systems with this new key.")

    return 0


def cmd_delete(identifier: str, yes: bool = False, json_output: bool = False) -> int:
    """Permanently delete an API key.

    Args:
        identifier: Key ID or name.
        yes: Skip confirmation.
        json_output: Output as JSON.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    store = get_key_store()

    # Try to find by ID first, then by name
    key = store.get_key(identifier)
    if key is None:
        key = store.get_key_by_name(identifier)

    if key is None:
        if json_output:
            print(json.dumps({"error": f"Key not found: {identifier}"}))
        else:
            print(f"Error: Key not found: {identifier}")
        return 1

    # Confirm unless --yes
    if not yes and not json_output:
        print(f"\nWARNING: This will permanently delete key '{key.name}'.")
        print("This action cannot be undone. Consider using 'revoke' instead.")
        confirm = input("\nType the key name to confirm: ").strip()
        if confirm != key.name:
            print("Cancelled.")
            return 1

    success = store.delete_key(key.id)

    if success:
        if json_output:
            print(json.dumps({"status": "deleted", "id": key.id, "name": key.name}))
        else:
            print(f"Key '{key.name}' has been permanently deleted.")
        return 0
    else:
        if json_output:
            print(json.dumps({"error": "Failed to delete key"}))
        else:
            print("Error: Failed to delete key.")
        return 1
