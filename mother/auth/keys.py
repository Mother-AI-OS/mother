"""SQLite-backed API key store for multi-key authentication."""

import hashlib
import json
import logging
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import APIKey, IdentityContext, Role

logger = logging.getLogger("mother.auth.keys")

# Default database location
DEFAULT_DB_PATH = Path.home() / ".config" / "mother" / "keys.db"


def _hash_key(api_key: str) -> str:
    """Hash an API key using SHA-256.

    We use SHA-256 instead of bcrypt for performance since API keys
    are already high-entropy random strings.
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def _generate_api_key() -> str:
    """Generate a secure random API key.

    Format: mk_<32 random hex chars>
    The 'mk_' prefix indicates a multi-key system key.
    """
    return f"mk_{secrets.token_hex(32)}"


class APIKeyStore:
    """SQLite-backed API key management.

    This store manages API keys with roles and scopes. Keys are stored
    with SHA-256 hashes for security. The actual key is only shown once
    at creation time.

    Usage:
        store = APIKeyStore()
        store.initialize()  # Create tables if needed

        # Add a new key
        key, raw_key = store.add_key("my-service", Role.OPERATOR, ["filesystem:*"])
        print(f"Save this key: {raw_key}")  # Only shown once

        # Validate incoming request
        identity = store.validate_key(request_key)
        if identity:
            print(f"Authenticated as {identity.name}")
    """

    def __init__(self, db_path: Path | None = None):
        """Initialize the key store.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.config/mother/keys.db
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self._initialized = False

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        """Initialize the database schema.

        Creates the api_keys table if it doesn't exist.
        Safe to call multiple times.
        """
        if self._initialized:
            return

        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    key_hash TEXT NOT NULL UNIQUE,
                    role TEXT NOT NULL,
                    scopes TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    revoked INTEGER NOT NULL DEFAULT 0,
                    revoked_at TEXT,
                    last_used_at TEXT,
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash
                ON api_keys(key_hash)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_api_keys_name
                ON api_keys(name)
            """)
            conn.commit()
            self._initialized = True
            logger.info(f"API key store initialized at {self.db_path}")
        finally:
            conn.close()

    def add_key(
        self,
        name: str,
        role: Role,
        scopes: list[str] | None = None,
        expires_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[APIKey, str]:
        """Add a new API key.

        Args:
            name: Human-readable name for the key (must be unique).
            role: Role for the key (admin/operator/readonly).
            scopes: List of scope strings. Defaults to role-based scopes.
            expires_at: Optional expiration datetime.
            metadata: Optional metadata dictionary.

        Returns:
            Tuple of (APIKey object, raw key string).
            The raw key is only returned once and should be saved securely.

        Raises:
            ValueError: If name already exists.
            sqlite3.Error: On database errors.
        """
        self.initialize()

        # Generate key
        raw_key = _generate_api_key()
        key_hash = _hash_key(raw_key)
        key_id = secrets.token_hex(16)

        # Default scopes based on role if not provided
        if scopes is None:
            from .scopes import get_role_scopes

            scopes = get_role_scopes(role)

        now = datetime.utcnow()

        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO api_keys
                (id, name, key_hash, role, scopes, created_at, expires_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    key_id,
                    name,
                    key_hash,
                    role.value,
                    json.dumps(scopes),
                    now.isoformat(),
                    expires_at.isoformat() if expires_at else None,
                    json.dumps(metadata or {}),
                ),
            )
            conn.commit()

            api_key = APIKey(
                id=key_id,
                name=name,
                key_hash=key_hash,
                role=role,
                scopes=scopes,
                created_at=now,
                expires_at=expires_at,
                metadata=metadata or {},
            )

            logger.info(f"Created API key '{name}' with role '{role.value}'")
            return api_key, raw_key

        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: api_keys.name" in str(e):
                raise ValueError(f"API key with name '{name}' already exists") from e
            raise
        finally:
            conn.close()

    def get_key(self, key_id: str) -> APIKey | None:
        """Get an API key by its ID.

        Args:
            key_id: The key's unique ID.

        Returns:
            APIKey object or None if not found.
        """
        self.initialize()

        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM api_keys WHERE id = ?",
                (key_id,),
            ).fetchone()

            if row is None:
                return None

            return self._row_to_key(row)
        finally:
            conn.close()

    def get_key_by_name(self, name: str) -> APIKey | None:
        """Get an API key by its name.

        Args:
            name: The key's human-readable name.

        Returns:
            APIKey object or None if not found.
        """
        self.initialize()

        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM api_keys WHERE name = ?",
                (name,),
            ).fetchone()

            if row is None:
                return None

            return self._row_to_key(row)
        finally:
            conn.close()

    def validate_key(self, api_key: str) -> IdentityContext | None:
        """Validate an API key and return identity context.

        This is the main method used during request authentication.
        It validates the key, checks if it's not expired/revoked,
        and updates the last_used_at timestamp.

        Args:
            api_key: The raw API key string from the request.

        Returns:
            IdentityContext if valid, None otherwise.
        """
        self.initialize()

        key_hash = _hash_key(api_key)

        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM api_keys WHERE key_hash = ?",
                (key_hash,),
            ).fetchone()

            if row is None:
                return None

            key = self._row_to_key(row)

            # Check validity
            if not key.is_valid():
                logger.warning(f"Invalid key used: {key.name} (revoked or expired)")
                return None

            # Update last_used_at
            now = datetime.utcnow()
            conn.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
                (now.isoformat(), key.id),
            )
            conn.commit()

            return IdentityContext(
                key_id=key.id,
                name=key.name,
                role=key.role,
                scopes=key.scopes,
            )

        finally:
            conn.close()

    def list_keys(self, include_revoked: bool = False) -> list[APIKey]:
        """List all API keys.

        Args:
            include_revoked: Whether to include revoked keys.

        Returns:
            List of APIKey objects (without the actual key values).
        """
        self.initialize()

        conn = self._get_connection()
        try:
            if include_revoked:
                rows = conn.execute("SELECT * FROM api_keys ORDER BY created_at DESC").fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM api_keys WHERE revoked = 0 ORDER BY created_at DESC"
                ).fetchall()

            return [self._row_to_key(row) for row in rows]
        finally:
            conn.close()

    def revoke_key(self, key_id: str) -> bool:
        """Revoke an API key.

        Args:
            key_id: The key's unique ID.

        Returns:
            True if key was revoked, False if not found.
        """
        self.initialize()

        conn = self._get_connection()
        try:
            now = datetime.utcnow()
            result = conn.execute(
                "UPDATE api_keys SET revoked = 1, revoked_at = ? WHERE id = ? AND revoked = 0",
                (now.isoformat(), key_id),
            )
            conn.commit()

            if result.rowcount > 0:
                logger.info(f"Revoked API key: {key_id}")
                return True
            return False
        finally:
            conn.close()

    def rotate_key(self, key_id: str) -> tuple[APIKey, str] | None:
        """Rotate an API key (revoke old, create new with same settings).

        Args:
            key_id: The key's unique ID.

        Returns:
            Tuple of (new APIKey, new raw key string) or None if not found.
        """
        self.initialize()

        # Get existing key
        old_key = self.get_key(key_id)
        if old_key is None:
            return None

        # Revoke old key
        self.revoke_key(key_id)

        # Create new key with same settings
        # Append rotation timestamp to name to avoid collision
        new_name = f"{old_key.name}"
        if self.get_key_by_name(new_name) is not None:
            # Name collision, append timestamp
            new_name = f"{old_key.name}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        new_key, raw_key = self.add_key(
            name=new_name,
            role=old_key.role,
            scopes=old_key.scopes,
            expires_at=old_key.expires_at,
            metadata={**old_key.metadata, "rotated_from": old_key.id},
        )

        logger.info(f"Rotated API key: {old_key.id} -> {new_key.id}")
        return new_key, raw_key

    def delete_key(self, key_id: str) -> bool:
        """Permanently delete an API key.

        This is a hard delete. Use revoke_key() for soft delete.

        Args:
            key_id: The key's unique ID.

        Returns:
            True if key was deleted, False if not found.
        """
        self.initialize()

        conn = self._get_connection()
        try:
            result = conn.execute(
                "DELETE FROM api_keys WHERE id = ?",
                (key_id,),
            )
            conn.commit()

            if result.rowcount > 0:
                logger.info(f"Deleted API key: {key_id}")
                return True
            return False
        finally:
            conn.close()

    def update_scopes(self, key_id: str, scopes: list[str]) -> bool:
        """Update the scopes for an API key.

        Args:
            key_id: The key's unique ID.
            scopes: New list of scope strings.

        Returns:
            True if updated, False if not found.
        """
        self.initialize()

        conn = self._get_connection()
        try:
            result = conn.execute(
                "UPDATE api_keys SET scopes = ? WHERE id = ?",
                (json.dumps(scopes), key_id),
            )
            conn.commit()

            if result.rowcount > 0:
                logger.info(f"Updated scopes for API key: {key_id}")
                return True
            return False
        finally:
            conn.close()

    def key_count(self) -> int:
        """Get the count of active (non-revoked) keys."""
        self.initialize()

        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as count FROM api_keys WHERE revoked = 0"
            ).fetchone()
            return row["count"]
        finally:
            conn.close()

    def _row_to_key(self, row: sqlite3.Row) -> APIKey:
        """Convert a database row to an APIKey object."""
        return APIKey(
            id=row["id"],
            name=row["name"],
            key_hash=row["key_hash"],
            role=Role(row["role"]),
            scopes=json.loads(row["scopes"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            revoked=bool(row["revoked"]),
            revoked_at=datetime.fromisoformat(row["revoked_at"]) if row["revoked_at"] else None,
            last_used_at=(
                datetime.fromisoformat(row["last_used_at"]) if row["last_used_at"] else None
            ),
            metadata=json.loads(row["metadata"]),
        )


# Singleton instance
_store: APIKeyStore | None = None


def get_key_store() -> APIKeyStore:
    """Get the global API key store instance."""
    global _store
    if _store is None:
        _store = APIKeyStore()
    return _store
