"""Tests for PluginSandbox and Permission classes."""

import pytest

from mother.plugins.exceptions import PermissionError
from mother.plugins.sandbox import (
    Permission,
    PluginSandbox,
    SandboxManager,
)


class TestPermission:
    """Tests for Permission parsing and matching."""

    def test_parse_simple_permission(self) -> None:
        """Test parsing simple permission."""
        perm = Permission.parse("network")
        assert perm.type == "network"
        assert perm.scope is None

    def test_parse_scoped_permission(self) -> None:
        """Test parsing scoped permission."""
        perm = Permission.parse("filesystem:read")
        assert perm.type == "filesystem:read"
        assert perm.scope is None

    def test_parse_path_permission(self) -> None:
        """Test parsing permission with path scope."""
        perm = Permission.parse("filesystem:read:/home/user")
        assert perm.type == "filesystem:read"
        assert perm.scope == "/home/user"

    def test_matches_same_permission(self) -> None:
        """Test matching identical permissions."""
        perm1 = Permission(type="network")
        perm2 = Permission(type="network")
        assert perm1.matches(perm2)

    def test_matches_different_action(self) -> None:
        """Test non-matching different actions."""
        perm1 = Permission(type="network")
        perm2 = Permission(type="filesystem:read")
        assert not perm1.matches(perm2)

    def test_permission_str(self) -> None:
        """Test string representation."""
        perm = Permission(type="filesystem:write", scope="/tmp")
        assert str(perm) == "filesystem:write:/tmp"

        perm = Permission(type="network")
        assert str(perm) == "network"


class TestPluginSandbox:
    """Tests for PluginSandbox."""

    def test_sandbox_creation(self) -> None:
        """Test creating a sandbox."""
        sandbox = PluginSandbox(plugin_name="test-plugin")
        assert sandbox.plugin_name == "test-plugin"

    def test_sandbox_with_permissions(self) -> None:
        """Test sandbox with initial permissions."""
        sandbox = PluginSandbox(
            plugin_name="test-plugin",
            granted_permissions=[
                Permission(type="network"),
                Permission(type="filesystem:read"),
            ],
        )
        assert len(sandbox.granted_permissions) == 2

    def test_check_permission_granted(self) -> None:
        """Test checking granted permission."""
        sandbox = PluginSandbox(plugin_name="test-plugin", granted_permissions=[Permission(type="network")])
        assert sandbox.check_permission("network") is True

    def test_check_permission_denied(self) -> None:
        """Test checking denied permission."""
        sandbox = PluginSandbox(plugin_name="test-plugin")
        assert sandbox.check_permission("network") is False

    def test_require_permission_granted(self) -> None:
        """Test requiring granted permission (no exception)."""
        sandbox = PluginSandbox(plugin_name="test-plugin", granted_permissions=[Permission(type="network")])
        # Should not raise
        sandbox.require_permission("network")

    def test_require_permission_denied(self) -> None:
        """Test requiring denied permission (raises exception)."""
        sandbox = PluginSandbox(plugin_name="test-plugin")
        with pytest.raises(PermissionError):
            sandbox.require_permission("network")

    def test_from_manifest_permissions(self) -> None:
        """Test creating sandbox from manifest permission strings."""
        sandbox = PluginSandbox.from_manifest_permissions(
            plugin_name="manifest-plugin", permissions=["network", "filesystem:read"]
        )
        assert sandbox.check_permission("network") is True
        assert sandbox.check_permission("filesystem:read") is True


class TestSandboxManager:
    """Tests for SandboxManager."""

    def test_manager_creation(self) -> None:
        """Test creating sandbox manager."""
        manager = SandboxManager()
        assert manager is not None

    def test_create_sandbox(self) -> None:
        """Test creating a sandbox through manager."""
        manager = SandboxManager()
        sandbox = manager.create_sandbox(plugin_name="test-plugin", permissions=["network"])
        assert sandbox is not None
        assert sandbox.plugin_name == "test-plugin"
        assert sandbox.check_permission("network") is True

    def test_get_sandbox(self) -> None:
        """Test retrieving a sandbox."""
        manager = SandboxManager()
        manager.create_sandbox("test-plugin", ["network"])

        sandbox = manager.get_sandbox("test-plugin")
        assert sandbox is not None
        assert sandbox.plugin_name == "test-plugin"

    def test_get_nonexistent_sandbox(self) -> None:
        """Test retrieving non-existent sandbox."""
        manager = SandboxManager()
        sandbox = manager.get_sandbox("nonexistent")
        assert sandbox is None

    def test_remove_sandbox(self) -> None:
        """Test removing a sandbox."""
        manager = SandboxManager()
        manager.create_sandbox("test-plugin", [])

        assert manager.get_sandbox("test-plugin") is not None

        manager.remove_sandbox("test-plugin")

        assert manager.get_sandbox("test-plugin") is None

    def test_global_denial(self) -> None:
        """Test global denial list."""
        manager = SandboxManager()

        assert manager.check_global_denial("dangerous_action") is False

        manager.add_global_denial("dangerous_action")

        assert manager.check_global_denial("dangerous_action") is True


class TestPermissionMatching:
    """Tests for Permission scope matching."""

    def test_no_scope_grants_all(self) -> None:
        """Test that permission without scope grants access to any scope."""
        granted = Permission(type="filesystem:read", scope=None)
        required = Permission(type="filesystem:read", scope="/tmp/file.txt")
        assert granted.matches(required)

    def test_scope_exact_match(self) -> None:
        """Test exact scope match."""
        granted = Permission(type="filesystem:read", scope="/tmp")
        required = Permission(type="filesystem:read", scope="/tmp")
        assert granted.matches(required)

    def test_scope_path_containment(self) -> None:
        """Test path containment - granted covers subdirectories."""
        granted = Permission(type="filesystem:read", scope="/home")
        required = Permission(type="filesystem:read", scope="/home/user/file.txt")
        assert granted.matches(required)

    def test_scope_path_not_contained(self) -> None:
        """Test path not contained."""
        granted = Permission(type="filesystem:read", scope="/tmp")
        required = Permission(type="filesystem:read", scope="/home/user")
        assert not granted.matches(required)

    def test_scope_glob_pattern(self) -> None:
        """Test glob pattern matching."""
        granted = Permission(type="filesystem:read", scope="*.txt")
        required = Permission(type="filesystem:read", scope="file.txt")
        assert granted.matches(required)

    def test_required_no_scope(self) -> None:
        """Test when required has no scope but granted has scope."""
        granted = Permission(type="filesystem:read", scope="/tmp")
        required = Permission(type="filesystem:read", scope=None)
        assert granted.matches(required)

    def test_type_mismatch(self) -> None:
        """Test type mismatch with scope."""
        granted = Permission(type="filesystem:read", scope="/tmp")
        required = Permission(type="filesystem:write", scope="/tmp")
        assert not granted.matches(required)

    def test_broader_permission(self) -> None:
        """Test broader permission grants specific."""
        granted = Permission(type="filesystem")
        required = Permission(type="filesystem:read")
        assert granted.matches(required)


class TestPluginSandboxExtended:
    """Extended tests for PluginSandbox."""

    def test_check_permission_with_target(self) -> None:
        """Test checking permission with target."""
        sandbox = PluginSandbox(
            plugin_name="test-plugin",
            granted_permissions=[Permission(type="filesystem:read", scope="/tmp")],
        )
        assert sandbox.check_permission("filesystem:read", target="/tmp/file.txt")

    def test_check_permission_with_denied_target(self) -> None:
        """Test checking permission with denied target."""
        sandbox = PluginSandbox(
            plugin_name="test-plugin",
            granted_permissions=[Permission(type="filesystem:read", scope="/tmp")],
        )
        assert not sandbox.check_permission("filesystem:read", target="/home/user")

    def test_require_permission_with_target(self) -> None:
        """Test requiring permission with target."""
        sandbox = PluginSandbox(
            plugin_name="test-plugin",
            granted_permissions=[Permission(type="filesystem:read", scope="/tmp")],
        )
        # Should not raise
        sandbox.require_permission("filesystem:read", target="/tmp/file.txt")

    def test_require_permission_denied_target(self) -> None:
        """Test requiring permission with denied target."""
        sandbox = PluginSandbox(
            plugin_name="test-plugin",
            granted_permissions=[Permission(type="filesystem:read", scope="/tmp")],
        )
        with pytest.raises(PermissionError):
            sandbox.require_permission("filesystem:read", target="/etc/passwd")

    def test_grant_permission(self) -> None:
        """Test granting additional permission."""
        sandbox = PluginSandbox(plugin_name="test-plugin")
        assert not sandbox.check_permission("network")

        sandbox.grant_permission("network")

        assert sandbox.check_permission("network")

    def test_revoke_permission(self) -> None:
        """Test revoking permission."""
        sandbox = PluginSandbox(
            plugin_name="test-plugin",
            granted_permissions=[Permission(type="network")],
        )
        assert sandbox.check_permission("network")

        result = sandbox.revoke_permission("network")

        assert result is True
        assert not sandbox.check_permission("network")

    def test_revoke_nonexistent_permission(self) -> None:
        """Test revoking non-existent permission."""
        sandbox = PluginSandbox(plugin_name="test-plugin")

        result = sandbox.revoke_permission("network")

        assert result is False

    def test_list_permissions(self) -> None:
        """Test listing permissions."""
        sandbox = PluginSandbox(
            plugin_name="test-plugin",
            granted_permissions=[
                Permission(type="network"),
                Permission(type="filesystem:read", scope="/tmp"),
            ],
        )

        perms = sandbox.list_permissions()

        assert "network" in perms
        assert "filesystem:read:/tmp" in perms

    def test_audit_disabled(self) -> None:
        """Test with audit logging disabled."""
        sandbox = PluginSandbox(
            plugin_name="test-plugin",
            granted_permissions=[Permission(type="network")],
            audit_enabled=False,
        )

        # Should still work
        assert sandbox.check_permission("network")
        assert not sandbox.check_permission("filesystem:read")


class TestSandboxManagerExtended:
    """Extended tests for SandboxManager."""

    def test_multiple_sandboxes(self) -> None:
        """Test managing multiple sandboxes."""
        manager = SandboxManager()

        manager.create_sandbox("plugin1", ["network"])
        manager.create_sandbox("plugin2", ["filesystem:read"])

        s1 = manager.get_sandbox("plugin1")
        s2 = manager.get_sandbox("plugin2")

        assert s1 is not None
        assert s2 is not None
        assert s1.check_permission("network")
        assert not s1.check_permission("filesystem:read")
        assert s2.check_permission("filesystem:read")
        assert not s2.check_permission("network")

    def test_remove_nonexistent_sandbox(self) -> None:
        """Test removing non-existent sandbox."""
        manager = SandboxManager()

        # Should not raise
        manager.remove_sandbox("nonexistent")

    def test_add_multiple_global_denials(self) -> None:
        """Test adding multiple global denials."""
        manager = SandboxManager()

        manager.add_global_denial("action1")
        manager.add_global_denial("action2")

        assert manager.check_global_denial("action1")
        assert manager.check_global_denial("action2")
        assert not manager.check_global_denial("action3")
