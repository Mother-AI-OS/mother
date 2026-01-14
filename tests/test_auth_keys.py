"""Tests for the multi-key authentication system."""

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from mother.auth.keys import APIKeyStore, _generate_api_key, _hash_key
from mother.auth.models import APIKey, IdentityContext, Role
from mother.auth.scopes import (
    capability_to_scope,
    check_scope,
    get_role_scopes,
    is_admin_scope,
    parse_scope,
    validate_scopes,
)


class TestAPIKeyGeneration:
    """Tests for API key generation utilities."""

    def test_generate_api_key_format(self):
        """Test that generated keys have correct format."""
        key = _generate_api_key()
        assert key.startswith("mk_")
        assert len(key) == 67  # mk_ + 64 hex chars

    def test_generate_api_key_unique(self):
        """Test that generated keys are unique."""
        keys = [_generate_api_key() for _ in range(100)]
        assert len(set(keys)) == 100

    def test_hash_key_consistent(self):
        """Test that hashing is consistent."""
        key = "mk_test123"
        hash1 = _hash_key(key)
        hash2 = _hash_key(key)
        assert hash1 == hash2

    def test_hash_key_different_for_different_keys(self):
        """Test that different keys produce different hashes."""
        key1 = "mk_test1"
        key2 = "mk_test2"
        assert _hash_key(key1) != _hash_key(key2)


class TestRole:
    """Tests for Role enum."""

    def test_role_values(self):
        """Test role enum values."""
        assert Role.ADMIN.value == "admin"
        assert Role.OPERATOR.value == "operator"
        assert Role.READONLY.value == "readonly"

    def test_role_from_string(self):
        """Test role creation from string."""
        assert Role("admin") == Role.ADMIN
        assert Role("operator") == Role.OPERATOR
        assert Role("readonly") == Role.READONLY

    def test_role_invalid_value(self):
        """Test invalid role value raises error."""
        with pytest.raises(ValueError):
            Role("invalid")


class TestAPIKey:
    """Tests for APIKey model."""

    def test_is_valid_active_key(self):
        """Test is_valid for an active key."""
        key = APIKey(
            id="test-id",
            name="test",
            key_hash="hash",
            role=Role.OPERATOR,
        )
        assert key.is_valid()

    def test_is_valid_revoked_key(self):
        """Test is_valid for a revoked key."""
        key = APIKey(
            id="test-id",
            name="test",
            key_hash="hash",
            role=Role.OPERATOR,
            revoked=True,
        )
        assert not key.is_valid()

    def test_is_valid_expired_key(self):
        """Test is_valid for an expired key."""
        key = APIKey(
            id="test-id",
            name="test",
            key_hash="hash",
            role=Role.OPERATOR,
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        assert not key.is_valid()

    def test_is_valid_not_yet_expired(self):
        """Test is_valid for a key not yet expired."""
        key = APIKey(
            id="test-id",
            name="test",
            key_hash="hash",
            role=Role.OPERATOR,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        assert key.is_valid()

    def test_to_dict_excludes_hash(self):
        """Test that to_dict excludes key_hash."""
        key = APIKey(
            id="test-id",
            name="test",
            key_hash="secret_hash",
            role=Role.OPERATOR,
        )
        d = key.to_dict()
        assert "key_hash" not in d
        assert d["id"] == "test-id"
        assert d["name"] == "test"
        assert d["role"] == "operator"


class TestIdentityContext:
    """Tests for IdentityContext model."""

    def test_has_scope_with_wildcard(self):
        """Test has_scope with admin wildcard."""
        ctx = IdentityContext(
            key_id="test",
            name="admin-key",
            role=Role.ADMIN,
            scopes=["*"],
        )
        assert ctx.has_scope("filesystem:read")
        assert ctx.has_scope("any:scope")
        assert ctx.has_scope("admin:anything")

    def test_has_scope_exact_match(self):
        """Test has_scope with exact match."""
        ctx = IdentityContext(
            key_id="test",
            name="op-key",
            role=Role.OPERATOR,
            scopes=["filesystem:read", "tasks:write"],
        )
        assert ctx.has_scope("filesystem:read")
        assert ctx.has_scope("tasks:write")
        assert not ctx.has_scope("filesystem:write")

    def test_has_scope_prefix_wildcard(self):
        """Test has_scope with prefix wildcard."""
        ctx = IdentityContext(
            key_id="test",
            name="op-key",
            role=Role.OPERATOR,
            scopes=["filesystem:*"],
        )
        assert ctx.has_scope("filesystem:read")
        assert ctx.has_scope("filesystem:write")
        assert ctx.has_scope("filesystem:delete")
        assert not ctx.has_scope("tasks:read")

    def test_is_admin(self):
        """Test is_admin method."""
        admin_ctx = IdentityContext(key_id="test", name="admin", role=Role.ADMIN, scopes=["*"])
        op_ctx = IdentityContext(key_id="test", name="op", role=Role.OPERATOR, scopes=[])
        assert admin_ctx.is_admin()
        assert not op_ctx.is_admin()

    def test_is_operator(self):
        """Test is_operator method."""
        op_ctx = IdentityContext(key_id="test", name="op", role=Role.OPERATOR, scopes=[])
        assert op_ctx.is_operator()

    def test_is_readonly(self):
        """Test is_readonly method."""
        ro_ctx = IdentityContext(key_id="test", name="ro", role=Role.READONLY, scopes=[])
        assert ro_ctx.is_readonly()


class TestAPIKeyStore:
    """Tests for APIKeyStore."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_keys.db"
            yield db_path

    @pytest.fixture
    def store(self, temp_db):
        """Create a store with temporary database."""
        store = APIKeyStore(db_path=temp_db)
        store.initialize()
        return store

    def test_initialize_creates_tables(self, temp_db):
        """Test that initialize creates necessary tables."""
        store = APIKeyStore(db_path=temp_db)
        store.initialize()
        assert temp_db.exists()

    def test_add_key_returns_key_and_raw(self, store):
        """Test adding a key returns the key object and raw key."""
        api_key, raw_key = store.add_key("test-key", Role.OPERATOR)

        assert api_key.name == "test-key"
        assert api_key.role == Role.OPERATOR
        assert raw_key.startswith("mk_")

    def test_add_key_duplicate_name_raises(self, store):
        """Test that adding duplicate name raises error."""
        store.add_key("unique-name", Role.OPERATOR)

        with pytest.raises(ValueError, match="already exists"):
            store.add_key("unique-name", Role.ADMIN)

    def test_add_key_with_scopes(self, store):
        """Test adding a key with custom scopes."""
        api_key, _ = store.add_key(
            "scoped-key",
            Role.OPERATOR,
            scopes=["filesystem:read", "tasks:*"],
        )

        assert api_key.scopes == ["filesystem:read", "tasks:*"]

    def test_add_key_with_expiration(self, store):
        """Test adding a key with expiration."""
        expires = datetime.now(UTC) + timedelta(days=30)
        api_key, _ = store.add_key(
            "expiring-key",
            Role.OPERATOR,
            expires_at=expires,
        )

        assert api_key.expires_at is not None
        # Allow for small time drift
        assert abs((api_key.expires_at - expires).total_seconds()) < 2

    def test_validate_key_success(self, store):
        """Test validating a valid key returns identity context."""
        api_key, raw_key = store.add_key("valid-key", Role.OPERATOR)

        identity = store.validate_key(raw_key)

        assert identity is not None
        assert identity.key_id == api_key.id
        assert identity.name == "valid-key"
        assert identity.role == Role.OPERATOR

    def test_validate_key_invalid(self, store):
        """Test validating an invalid key returns None."""
        identity = store.validate_key("mk_invalid_key_12345")
        assert identity is None

    def test_validate_key_revoked(self, store):
        """Test validating a revoked key returns None."""
        api_key, raw_key = store.add_key("revoked-key", Role.OPERATOR)
        store.revoke_key(api_key.id)

        identity = store.validate_key(raw_key)
        assert identity is None

    def test_validate_key_expired(self, store):
        """Test validating an expired key returns None."""
        expires = datetime.now(UTC) - timedelta(days=1)
        api_key, raw_key = store.add_key(
            "expired-key",
            Role.OPERATOR,
            expires_at=expires,
        )

        identity = store.validate_key(raw_key)
        assert identity is None

    def test_list_keys(self, store):
        """Test listing keys."""
        store.add_key("key1", Role.ADMIN)
        store.add_key("key2", Role.OPERATOR)
        store.add_key("key3", Role.READONLY)

        keys = store.list_keys()
        assert len(keys) == 3

    def test_list_keys_excludes_revoked_by_default(self, store):
        """Test that list_keys excludes revoked keys by default."""
        api_key, _ = store.add_key("key1", Role.OPERATOR)
        store.add_key("key2", Role.OPERATOR)
        store.revoke_key(api_key.id)

        keys = store.list_keys()
        assert len(keys) == 1

    def test_list_keys_includes_revoked_when_requested(self, store):
        """Test that list_keys includes revoked when requested."""
        api_key, _ = store.add_key("key1", Role.OPERATOR)
        store.add_key("key2", Role.OPERATOR)
        store.revoke_key(api_key.id)

        keys = store.list_keys(include_revoked=True)
        assert len(keys) == 2

    def test_revoke_key_success(self, store):
        """Test revoking a key."""
        api_key, _ = store.add_key("to-revoke", Role.OPERATOR)

        result = store.revoke_key(api_key.id)
        assert result is True

        key = store.get_key(api_key.id)
        assert key.revoked is True
        assert key.revoked_at is not None

    def test_revoke_key_not_found(self, store):
        """Test revoking non-existent key returns False."""
        result = store.revoke_key("non-existent-id")
        assert result is False

    def test_rotate_key_success(self, store):
        """Test rotating a key."""
        api_key, old_raw = store.add_key("to-rotate", Role.OPERATOR)

        result = store.rotate_key(api_key.id)
        assert result is not None

        new_key, new_raw = result
        # Name may have timestamp appended if there's a collision
        assert new_key.name.startswith("to-rotate")
        assert new_key.role == Role.OPERATOR
        assert new_raw != old_raw

        # Old key should be revoked
        old_key = store.get_key(api_key.id)
        assert old_key.revoked is True

    def test_rotate_key_not_found(self, store):
        """Test rotating non-existent key returns None."""
        result = store.rotate_key("non-existent-id")
        assert result is None

    def test_delete_key_success(self, store):
        """Test deleting a key."""
        api_key, _ = store.add_key("to-delete", Role.OPERATOR)

        result = store.delete_key(api_key.id)
        assert result is True

        key = store.get_key(api_key.id)
        assert key is None

    def test_delete_key_not_found(self, store):
        """Test deleting non-existent key returns False."""
        result = store.delete_key("non-existent-id")
        assert result is False

    def test_key_count(self, store):
        """Test key_count returns correct count."""
        assert store.key_count() == 0

        store.add_key("key1", Role.OPERATOR)
        assert store.key_count() == 1

        api_key, _ = store.add_key("key2", Role.OPERATOR)
        assert store.key_count() == 2

        store.revoke_key(api_key.id)
        assert store.key_count() == 1

    def test_get_key(self, store):
        """Test getting a key by ID."""
        api_key, _ = store.add_key("test-key", Role.OPERATOR)

        retrieved = store.get_key(api_key.id)
        assert retrieved is not None
        assert retrieved.name == "test-key"

    def test_get_key_by_name(self, store):
        """Test getting a key by name."""
        api_key, _ = store.add_key("named-key", Role.OPERATOR)

        retrieved = store.get_key_by_name("named-key")
        assert retrieved is not None
        assert retrieved.id == api_key.id

    def test_update_scopes(self, store):
        """Test updating scopes for a key."""
        api_key, _ = store.add_key("scoped-key", Role.OPERATOR, scopes=["filesystem:read"])

        result = store.update_scopes(api_key.id, ["filesystem:*", "tasks:*"])
        assert result is True

        updated = store.get_key(api_key.id)
        assert updated.scopes == ["filesystem:*", "tasks:*"]


class TestScopes:
    """Tests for scope utilities."""

    def test_get_role_scopes_admin(self):
        """Test admin gets all scopes."""
        scopes = get_role_scopes(Role.ADMIN)
        assert scopes == ["*"]

    def test_get_role_scopes_operator(self):
        """Test operator gets operational scopes."""
        scopes = get_role_scopes(Role.OPERATOR)
        assert "filesystem:read" in scopes
        assert "filesystem:write" in scopes
        assert "shell:execute" in scopes
        assert "policy:write" not in scopes

    def test_get_role_scopes_readonly(self):
        """Test readonly gets only read scopes."""
        scopes = get_role_scopes(Role.READONLY)
        assert "filesystem:read" in scopes
        assert "filesystem:write" not in scopes
        assert "shell:execute" not in scopes

    def test_capability_to_scope_filesystem(self):
        """Test filesystem capability mapping."""
        assert capability_to_scope("filesystem_read_file") == "filesystem:read"
        assert capability_to_scope("filesystem_write_file") == "filesystem:write"
        assert capability_to_scope("filesystem_list_directory") == "filesystem:read"
        assert capability_to_scope("filesystem_delete_file") == "filesystem:write"

    def test_capability_to_scope_tasks(self):
        """Test tasks capability mapping."""
        assert capability_to_scope("tasks_list") == "tasks:read"
        assert capability_to_scope("tasks_add") == "tasks:write"

    def test_capability_to_scope_shell(self):
        """Test shell capability mapping."""
        assert capability_to_scope("shell_run") == "shell:execute"
        assert capability_to_scope("shell_execute") == "shell:execute"

    def test_capability_to_scope_fallback(self):
        """Test fallback for unknown capabilities."""
        # Unknown capability with underscore should use prefix:read fallback
        scope = capability_to_scope("unknown_capability")
        assert scope == "unknown:read"

    def test_check_scope_legacy_mode(self):
        """Test scope check in legacy mode (no identity)."""
        allowed, reason = check_scope(None, "filesystem_read_file")
        assert allowed
        assert reason == "legacy_mode"

    def test_check_scope_granted(self):
        """Test scope check when scope is granted."""
        ctx = IdentityContext(
            key_id="test",
            name="op",
            role=Role.OPERATOR,
            scopes=["filesystem:read"],
        )
        allowed, reason = check_scope(ctx, "filesystem_read_file")
        assert allowed
        assert reason == "scope_granted"

    def test_check_scope_denied(self):
        """Test scope check when scope is denied."""
        ctx = IdentityContext(
            key_id="test",
            name="ro",
            role=Role.READONLY,
            scopes=["filesystem:read"],
        )
        allowed, reason = check_scope(ctx, "filesystem_write_file")
        assert not allowed
        assert "Missing scope" in reason

    def test_is_admin_scope(self):
        """Test admin-only scope detection."""
        assert is_admin_scope("*")
        assert is_admin_scope("policy:write")
        assert is_admin_scope("keys:manage")
        assert is_admin_scope("tor:access")
        assert not is_admin_scope("filesystem:read")
        assert not is_admin_scope("tasks:write")

    def test_validate_scopes_valid(self):
        """Test scope validation for valid scopes."""
        valid, reason = validate_scopes(["filesystem:read", "tasks:write"], Role.OPERATOR)
        assert valid

    def test_validate_scopes_admin_only_for_non_admin(self):
        """Test scope validation rejects admin scopes for non-admins."""
        valid, reason = validate_scopes(["*"], Role.OPERATOR)
        assert not valid
        assert "requires admin" in reason

        valid, reason = validate_scopes(["policy:write"], Role.READONLY)
        assert not valid
        assert "requires admin" in reason

    def test_validate_scopes_admin_can_have_any(self):
        """Test admins can have any scope."""
        valid, reason = validate_scopes(["*"], Role.ADMIN)
        assert valid

        valid, reason = validate_scopes(["policy:write", "keys:manage"], Role.ADMIN)
        assert valid

    def test_parse_scope(self):
        """Test scope parsing."""
        prefix, action = parse_scope("filesystem:read")
        assert prefix == "filesystem"
        assert action == "read"

        prefix, action = parse_scope("*")
        assert prefix == "*"
        assert action == "*"

    def test_parse_scope_invalid(self):
        """Test invalid scope parsing."""
        with pytest.raises(ValueError):
            parse_scope("invalid_scope")


class TestMultiKeyApiAuth:
    """Tests for multi-key API authentication functions."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_keys.db"
            yield db_path

    @pytest.mark.asyncio
    async def test_verify_api_key_multi_key_mode(self, temp_db):
        """Test verify_api_key in multi-key mode."""
        from mother.api.auth import verify_api_key

        store = APIKeyStore(db_path=temp_db)
        store.initialize()
        api_key, raw_key = store.add_key("test-key", Role.OPERATOR)

        mock_settings = MagicMock()
        mock_settings.require_auth = True

        with patch("mother.api.auth._is_multi_key_mode", return_value=True):
            with patch("mother.api.auth.get_key_store", return_value=store):
                with patch("mother.api.auth.get_settings", return_value=mock_settings):
                    result = await verify_api_key(api_key=raw_key)

        assert result == raw_key

    @pytest.mark.asyncio
    async def test_get_identity_context_multi_key_mode(self, temp_db):
        """Test get_identity_context in multi-key mode."""
        from mother.api.auth import get_identity_context

        store = APIKeyStore(db_path=temp_db)
        store.initialize()
        api_key, raw_key = store.add_key("test-key", Role.OPERATOR)

        mock_settings = MagicMock()
        mock_settings.require_auth = True

        with patch("mother.api.auth._is_multi_key_mode", return_value=True):
            with patch("mother.api.auth.get_key_store", return_value=store):
                with patch("mother.api.auth.get_settings", return_value=mock_settings):
                    identity = await get_identity_context(api_key=raw_key)

        assert identity is not None
        assert identity.name == "test-key"
        assert identity.role == Role.OPERATOR

    @pytest.mark.asyncio
    async def test_get_identity_context_invalid_key_raises_403(self, temp_db):
        """Test get_identity_context raises 403 for invalid key."""
        from mother.api.auth import get_identity_context

        store = APIKeyStore(db_path=temp_db)
        store.initialize()

        mock_settings = MagicMock()
        mock_settings.require_auth = True

        with patch("mother.api.auth._is_multi_key_mode", return_value=True):
            with patch("mother.api.auth.get_key_store", return_value=store):
                with patch("mother.api.auth.get_settings", return_value=mock_settings):
                    with pytest.raises(HTTPException) as exc_info:
                        await get_identity_context(api_key="mk_invalid_key")

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_require_admin_with_admin_key(self, temp_db):
        """Test require_admin passes for admin key."""
        from mother.api.auth import require_admin

        store = APIKeyStore(db_path=temp_db)
        store.initialize()
        api_key, raw_key = store.add_key("admin-key", Role.ADMIN)

        identity = IdentityContext(
            key_id=api_key.id,
            name="admin-key",
            role=Role.ADMIN,
            scopes=["*"],
        )

        result = await require_admin(identity)
        assert result.is_admin()

    @pytest.mark.asyncio
    async def test_require_admin_with_non_admin_raises_403(self, temp_db):
        """Test require_admin raises 403 for non-admin."""
        from mother.api.auth import require_admin

        identity = IdentityContext(
            key_id="test",
            name="operator-key",
            role=Role.OPERATOR,
            scopes=["filesystem:*"],
        )

        with pytest.raises(HTTPException) as exc_info:
            await require_admin(identity)

        assert exc_info.value.status_code == 403
        assert "Admin role required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_operator_with_operator_key(self, temp_db):
        """Test require_operator passes for operator key."""
        from mother.api.auth import require_operator

        identity = IdentityContext(
            key_id="test",
            name="operator-key",
            role=Role.OPERATOR,
            scopes=["filesystem:*"],
        )

        result = await require_operator(identity)
        assert result.is_operator()

    @pytest.mark.asyncio
    async def test_require_operator_with_readonly_raises_403(self):
        """Test require_operator raises 403 for readonly."""
        from mother.api.auth import require_operator

        identity = IdentityContext(
            key_id="test",
            name="readonly-key",
            role=Role.READONLY,
            scopes=["filesystem:read"],
        )

        with pytest.raises(HTTPException) as exc_info:
            await require_operator(identity)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_create_scope_dependency(self):
        """Test create_scope_dependency creates working dependency."""
        from mother.api.auth import create_scope_dependency

        require_fs_write = create_scope_dependency("filesystem:write")

        # Test with identity that has the scope
        identity_with_scope = IdentityContext(
            key_id="test",
            name="op-key",
            role=Role.OPERATOR,
            scopes=["filesystem:*"],
        )
        result = await require_fs_write(identity_with_scope)
        assert result == identity_with_scope

        # Test with identity that lacks the scope
        identity_without_scope = IdentityContext(
            key_id="test",
            name="ro-key",
            role=Role.READONLY,
            scopes=["filesystem:read"],
        )
        with pytest.raises(HTTPException) as exc_info:
            await require_fs_write(identity_without_scope)
        assert exc_info.value.status_code == 403
        assert "filesystem:write" in exc_info.value.detail


class TestExecutorScopeEnforcement:
    """Tests for scope enforcement in executors."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_keys.db"
            yield db_path

    def test_check_scope_allows_with_matching_scope(self):
        """Test that check_scope allows when identity has required scope."""
        from mother.plugins.executor import ExecutorBase

        # Create mock manifest
        mock_manifest = SimpleNamespace(plugin=SimpleNamespace(name="test_plugin"))

        class TestExecutor(ExecutorBase):
            async def initialize(self):
                pass

            async def execute(self, cap, params, identity=None):
                pass

        executor = TestExecutor(mock_manifest, {})

        identity = IdentityContext(
            key_id="test",
            name="op-key",
            role=Role.OPERATOR,
            scopes=["filesystem:read"],
        )

        # Should not raise
        executor.check_scope("filesystem_read_file", identity)

    def test_check_scope_denies_without_scope(self):
        """Test that check_scope denies when identity lacks required scope."""
        from mother.plugins.exceptions import PolicyViolationError
        from mother.plugins.executor import ExecutorBase

        mock_manifest = SimpleNamespace(plugin=SimpleNamespace(name="test_plugin"))

        class TestExecutor(ExecutorBase):
            async def initialize(self):
                pass

            async def execute(self, cap, params, identity=None):
                pass

        executor = TestExecutor(mock_manifest, {})

        identity = IdentityContext(
            key_id="test",
            name="ro-key",
            role=Role.READONLY,
            scopes=["filesystem:read"],
        )

        with pytest.raises(PolicyViolationError) as exc_info:
            executor.check_scope("filesystem_write_file", identity)

        assert "filesystem:write" in exc_info.value.reason

    def test_check_scope_allows_legacy_mode(self):
        """Test that check_scope allows in legacy mode (no identity)."""
        from mother.plugins.executor import ExecutorBase

        mock_manifest = SimpleNamespace(plugin=SimpleNamespace(name="test_plugin"))

        class TestExecutor(ExecutorBase):
            async def initialize(self):
                pass

            async def execute(self, cap, params, identity=None):
                pass

        executor = TestExecutor(mock_manifest, {})

        # Should not raise when identity is None (legacy mode)
        executor.check_scope("filesystem_write_file", None)

    def test_check_scope_allows_admin_wildcard(self):
        """Test that admin with wildcard scope can access anything."""
        from mother.plugins.executor import ExecutorBase

        mock_manifest = SimpleNamespace(plugin=SimpleNamespace(name="test_plugin"))

        class TestExecutor(ExecutorBase):
            async def initialize(self):
                pass

            async def execute(self, cap, params, identity=None):
                pass

        executor = TestExecutor(mock_manifest, {})

        admin_identity = IdentityContext(
            key_id="admin",
            name="admin-key",
            role=Role.ADMIN,
            scopes=["*"],
        )

        # Admin should be able to access any capability
        executor.check_scope("filesystem_write_file", admin_identity)
        executor.check_scope("shell_execute", admin_identity)
        executor.check_scope("policy_write", admin_identity)
