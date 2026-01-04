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
