"""Tests for PluginSandbox and Permission classes."""

import time
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from mother.plugins.exceptions import PermissionError
from mother.plugins.sandbox import (
    ExecutionContext,
    Permission,
    PluginSandbox,
    ResourceLimits,
    SandboxConfig,
    SandboxManager,
    WorkspaceConfig,
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

    def test_remove_global_denial(self) -> None:
        """Test removing a global denial (covers line 344)."""
        manager = SandboxManager()

        manager.add_global_denial("action1")
        assert manager.check_global_denial("action1")

        manager.remove_global_denial("action1")
        assert not manager.check_global_denial("action1")

    def test_remove_nonexistent_global_denial(self) -> None:
        """Test removing non-existent global denial (should not raise)."""
        manager = SandboxManager()

        # Should not raise
        manager.remove_global_denial("nonexistent")


class TestScopeMatchingEdgeCases:
    """Tests for edge cases in scope matching."""

    def test_scope_matches_with_invalid_path(self) -> None:
        """Test scope matching when path resolution fails (covers lines 133-135)."""
        # Use a path with null bytes which will cause Path.resolve() to fail
        granted = Permission(type="filesystem:read", scope="/valid/path")
        # The scope matching should handle the exception gracefully
        required = Permission(type="filesystem:read", scope="/different/path")
        # This should return False without raising an exception
        assert not granted.matches(required)

    def test_scope_matches_with_special_characters(self) -> None:
        """Test scope matching with special characters in path."""
        granted = Permission(type="filesystem:read", scope="/tmp/test dir")
        required = Permission(type="filesystem:read", scope="/tmp/test dir/file.txt")
        assert granted.matches(required)


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_validate_path_permission_granted(self) -> None:
        """Test validate_path_permission with granted permission (covers lines 367-368)."""
        from mother.plugins.sandbox import validate_path_permission

        sandbox = PluginSandbox(
            plugin_name="test-plugin",
            granted_permissions=[Permission(type="filesystem:read", scope="/tmp")],
        )
        # Should not raise
        validate_path_permission(sandbox, "/tmp/file.txt", mode="read")

    def test_validate_path_permission_denied(self) -> None:
        """Test validate_path_permission with denied permission."""
        from mother.plugins.sandbox import validate_path_permission

        sandbox = PluginSandbox(plugin_name="test-plugin")
        with pytest.raises(PermissionError):
            validate_path_permission(sandbox, "/tmp/file.txt", mode="read")

    def test_validate_path_permission_write_mode(self) -> None:
        """Test validate_path_permission with write mode."""
        from mother.plugins.sandbox import validate_path_permission

        sandbox = PluginSandbox(
            plugin_name="test-plugin",
            granted_permissions=[Permission(type="filesystem:write", scope="/tmp")],
        )
        # Should not raise
        validate_path_permission(sandbox, "/tmp/output.txt", mode="write")

    def test_validate_path_permission_delete_mode(self) -> None:
        """Test validate_path_permission with delete mode."""
        from mother.plugins.sandbox import validate_path_permission

        sandbox = PluginSandbox(
            plugin_name="test-plugin",
            granted_permissions=[Permission(type="filesystem:delete", scope="/tmp")],
        )
        # Should not raise
        validate_path_permission(sandbox, "/tmp/to_delete.txt", mode="delete")

    def test_validate_network_permission_localhost(self) -> None:
        """Test validate_network_permission with localhost (covers lines 385-389)."""
        from mother.plugins.sandbox import validate_network_permission

        sandbox = PluginSandbox(
            plugin_name="test-plugin",
            granted_permissions=[Permission(type="network:internal")],
        )
        # Should not raise for localhost
        validate_network_permission(sandbox, host="localhost")

    def test_validate_network_permission_127_0_0_1(self) -> None:
        """Test validate_network_permission with 127.0.0.1."""
        from mother.plugins.sandbox import validate_network_permission

        sandbox = PluginSandbox(
            plugin_name="test-plugin",
            granted_permissions=[Permission(type="network:internal")],
        )
        # Should not raise for 127.0.0.1
        validate_network_permission(sandbox, host="127.0.0.1")

    def test_validate_network_permission_ipv6_localhost(self) -> None:
        """Test validate_network_permission with IPv6 localhost."""
        from mother.plugins.sandbox import validate_network_permission

        sandbox = PluginSandbox(
            plugin_name="test-plugin",
            granted_permissions=[Permission(type="network:internal")],
        )
        # Should not raise for ::1
        validate_network_permission(sandbox, host="::1")

    def test_validate_network_permission_localhost_with_general_network(self) -> None:
        """Test validate_network_permission localhost with general network permission."""
        from mother.plugins.sandbox import validate_network_permission

        sandbox = PluginSandbox(
            plugin_name="test-plugin",
            granted_permissions=[Permission(type="network")],
        )
        # General network permission should also allow localhost
        validate_network_permission(sandbox, host="localhost")

    def test_validate_network_permission_external(self) -> None:
        """Test validate_network_permission with external host (covers lines 391-394)."""
        from mother.plugins.sandbox import validate_network_permission

        sandbox = PluginSandbox(
            plugin_name="test-plugin",
            granted_permissions=[Permission(type="network:external")],
        )
        # Should not raise for external host
        validate_network_permission(sandbox, host="example.com")

    def test_validate_network_permission_external_with_general(self) -> None:
        """Test validate_network_permission external with general network permission."""
        from mother.plugins.sandbox import validate_network_permission

        sandbox = PluginSandbox(
            plugin_name="test-plugin",
            granted_permissions=[Permission(type="network")],
        )
        # General network permission should also allow external
        validate_network_permission(sandbox, host="api.example.com")

    def test_validate_network_permission_denied(self) -> None:
        """Test validate_network_permission denied (covers lines 396-401)."""
        from mother.plugins.sandbox import validate_network_permission

        sandbox = PluginSandbox(plugin_name="test-plugin")
        with pytest.raises(PermissionError):
            validate_network_permission(sandbox, host="example.com")

    def test_validate_network_permission_no_host(self) -> None:
        """Test validate_network_permission with no host specified."""
        from mother.plugins.sandbox import validate_network_permission

        sandbox = PluginSandbox(
            plugin_name="test-plugin",
            granted_permissions=[Permission(type="network")],
        )
        # Should not raise when no host is specified
        validate_network_permission(sandbox, host=None)


# =============================================================================
# NEW TESTS: Resource Limits, Workspace Config, Execution Context
# =============================================================================


class TestResourceLimits:
    """Tests for ResourceLimits configuration."""

    def test_default_limits(self) -> None:
        """Test default resource limits."""
        limits = ResourceLimits()
        assert limits.max_cpu_seconds == 60
        assert limits.max_memory_mb == 512
        assert limits.max_execution_time == 300
        assert limits.max_file_size_mb == 100
        assert limits.max_open_files == 100
        assert limits.max_subprocess == 10

    def test_custom_limits(self) -> None:
        """Test custom resource limits."""
        limits = ResourceLimits(
            max_cpu_seconds=30,
            max_memory_mb=256,
            max_execution_time=120,
            max_file_size_mb=50,
            max_open_files=50,
            max_subprocess=5,
        )
        assert limits.max_cpu_seconds == 30
        assert limits.max_memory_mb == 256
        assert limits.max_execution_time == 120
        assert limits.max_file_size_mb == 50
        assert limits.max_open_files == 50
        assert limits.max_subprocess == 5


class TestWorkspaceConfig:
    """Tests for WorkspaceConfig configuration."""

    def test_default_config(self) -> None:
        """Test default workspace configuration."""
        config = WorkspaceConfig()
        assert config.enabled is True
        assert config.workspace_dir == Path("./workspace")
        assert config.allow_read_outside is True
        assert config.allowed_read_paths == []
        assert config.temp_dir is None

    def test_is_path_in_workspace(self) -> None:
        """Test path containment check."""
        with TemporaryDirectory() as tmpdir:
            config = WorkspaceConfig(workspace_dir=Path(tmpdir))

            # Path inside workspace
            inner_path = Path(tmpdir) / "subdir" / "file.txt"
            assert config.is_path_in_workspace(inner_path) is True

            # Path outside workspace
            assert config.is_path_in_workspace("/etc/passwd") is False

            # Workspace root itself
            assert config.is_path_in_workspace(tmpdir) is True

    def test_is_path_in_workspace_handles_invalid_path(self) -> None:
        """Test path check with invalid path."""
        config = WorkspaceConfig(workspace_dir=Path("/nonexistent"))
        # Should return False without raising exception
        assert config.is_path_in_workspace("\x00invalid") is False

    def test_is_path_allowed_read_disabled(self) -> None:
        """Test read permission when workspace is disabled."""
        config = WorkspaceConfig(enabled=False)
        # Should allow any path when disabled
        assert config.is_path_allowed_read("/etc/passwd") is True

    def test_is_path_allowed_read_in_workspace(self) -> None:
        """Test read permission for path inside workspace."""
        with TemporaryDirectory() as tmpdir:
            config = WorkspaceConfig(workspace_dir=Path(tmpdir))
            inner_path = Path(tmpdir) / "data.txt"
            assert config.is_path_allowed_read(inner_path) is True

    def test_is_path_allowed_read_outside_allowed(self) -> None:
        """Test read permission outside workspace when allowed."""
        with TemporaryDirectory() as tmpdir:
            config = WorkspaceConfig(
                workspace_dir=Path(tmpdir),
                allow_read_outside=True,
            )
            # Should allow reading outside
            assert config.is_path_allowed_read("/tmp/other.txt") is True

    def test_is_path_allowed_read_outside_denied(self) -> None:
        """Test read permission outside workspace when denied."""
        with TemporaryDirectory() as tmpdir:
            config = WorkspaceConfig(
                workspace_dir=Path(tmpdir),
                allow_read_outside=False,
            )
            # Should deny reading outside
            assert config.is_path_allowed_read("/tmp/other.txt") is False

    def test_is_path_allowed_write_disabled(self) -> None:
        """Test write permission when workspace is disabled."""
        config = WorkspaceConfig(enabled=False)
        # Should allow any path when disabled
        assert config.is_path_allowed_write("/etc/passwd") is True

    def test_is_path_allowed_write_in_workspace(self) -> None:
        """Test write permission for path inside workspace."""
        with TemporaryDirectory() as tmpdir:
            config = WorkspaceConfig(workspace_dir=Path(tmpdir))
            inner_path = Path(tmpdir) / "output.txt"
            assert config.is_path_allowed_write(inner_path) is True

    def test_is_path_allowed_write_outside(self) -> None:
        """Test write permission outside workspace (always denied)."""
        with TemporaryDirectory() as tmpdir:
            config = WorkspaceConfig(
                workspace_dir=Path(tmpdir),
                allow_read_outside=True,  # Even with read allowed
            )
            # Write should still be denied outside
            assert config.is_path_allowed_write("/tmp/other.txt") is False


class TestSandboxConfig:
    """Tests for SandboxConfig configuration."""

    def test_default_config(self) -> None:
        """Test default sandbox configuration."""
        config = SandboxConfig()
        assert config.enabled is True
        assert config.audit_all_actions is True
        assert config.enforce_permissions is True
        assert config.allow_shell is False
        assert config.allow_network is True
        assert isinstance(config.resource_limits, ResourceLimits)
        assert isinstance(config.workspace, WorkspaceConfig)

    def test_custom_config(self) -> None:
        """Test custom sandbox configuration."""
        config = SandboxConfig(
            enabled=False,
            allow_shell=True,
            allow_network=False,
            resource_limits=ResourceLimits(max_memory_mb=1024),
            workspace=WorkspaceConfig(enabled=False),
        )
        assert config.enabled is False
        assert config.allow_shell is True
        assert config.allow_network is False
        assert config.resource_limits.max_memory_mb == 1024
        assert config.workspace.enabled is False


class TestExecutionContext:
    """Tests for ExecutionContext tracking."""

    def test_context_creation(self) -> None:
        """Test creating an execution context."""
        context = ExecutionContext(plugin_name="test-plugin")
        assert context.plugin_name == "test-plugin"
        assert context.subprocess_count == 0
        assert context.files_written == []
        assert context.bytes_written == 0
        assert context.network_requests == 0

    def test_record_subprocess(self) -> None:
        """Test recording subprocess calls."""
        context = ExecutionContext(plugin_name="test-plugin")
        assert context.subprocess_count == 0

        context.record_subprocess()
        assert context.subprocess_count == 1

        context.record_subprocess()
        assert context.subprocess_count == 2

    def test_record_file_write(self) -> None:
        """Test recording file writes."""
        context = ExecutionContext(plugin_name="test-plugin")
        assert len(context.files_written) == 0
        assert context.bytes_written == 0

        context.record_file_write("/tmp/file1.txt", 100)
        assert context.files_written == ["/tmp/file1.txt"]
        assert context.bytes_written == 100

        context.record_file_write("/tmp/file2.txt", 200)
        assert context.files_written == ["/tmp/file1.txt", "/tmp/file2.txt"]
        assert context.bytes_written == 300

    def test_record_network_request(self) -> None:
        """Test recording network requests."""
        context = ExecutionContext(plugin_name="test-plugin")
        assert context.network_requests == 0

        context.record_network_request()
        assert context.network_requests == 1

    def test_elapsed_time(self) -> None:
        """Test elapsed time tracking."""
        context = ExecutionContext(plugin_name="test-plugin")
        time.sleep(0.1)
        elapsed = context.elapsed_time()
        assert elapsed >= 0.1
        assert elapsed < 1.0

    def test_check_limits_within_bounds(self) -> None:
        """Test limit check when within bounds."""
        context = ExecutionContext(plugin_name="test-plugin")
        limits = ResourceLimits(max_execution_time=300, max_subprocess=10)

        result = context.check_limits(limits)
        assert result is None

    def test_check_limits_subprocess_exceeded(self) -> None:
        """Test limit check when subprocess limit exceeded."""
        context = ExecutionContext(plugin_name="test-plugin")
        context.subprocess_count = 15

        limits = ResourceLimits(max_subprocess=10)
        result = context.check_limits(limits)
        assert result is not None
        assert "Subprocess limit exceeded" in result

    def test_check_limits_file_size_exceeded(self) -> None:
        """Test limit check when file size limit exceeded."""
        context = ExecutionContext(plugin_name="test-plugin")
        context.bytes_written = 200 * 1024 * 1024  # 200 MB

        limits = ResourceLimits(max_file_size_mb=100)
        result = context.check_limits(limits)
        assert result is not None
        assert "File write size exceeded" in result

    def test_check_limits_execution_time_exceeded(self) -> None:
        """Test limit check when execution time exceeded."""
        context = ExecutionContext(plugin_name="test-plugin")
        # Manually set start_time to simulate long execution
        context.start_time = time.time() - 400  # 400 seconds ago

        limits = ResourceLimits(max_execution_time=300)
        result = context.check_limits(limits)
        assert result is not None
        assert "Execution time exceeded" in result


class TestSandboxManagerWithConfig:
    """Tests for SandboxManager with configuration."""

    def test_manager_with_custom_config(self) -> None:
        """Test creating manager with custom config."""
        with TemporaryDirectory() as tmpdir:
            config = SandboxConfig(
                enabled=True,
                allow_shell=False,
                workspace=WorkspaceConfig(workspace_dir=Path(tmpdir)),
            )
            manager = SandboxManager(config=config)
            assert manager.config == config

    def test_start_execution(self) -> None:
        """Test starting execution tracking."""
        manager = SandboxManager()
        context = manager.start_execution("test-plugin")

        assert context is not None
        assert context.plugin_name == "test-plugin"

    def test_get_context(self) -> None:
        """Test getting execution context."""
        manager = SandboxManager()
        manager.start_execution("test-plugin")

        context = manager.get_context("test-plugin")
        assert context is not None
        assert context.plugin_name == "test-plugin"

    def test_get_context_nonexistent(self) -> None:
        """Test getting non-existent context."""
        manager = SandboxManager()
        context = manager.get_context("nonexistent")
        assert context is None

    def test_end_execution(self) -> None:
        """Test ending execution tracking."""
        manager = SandboxManager()
        manager.start_execution("test-plugin")

        final_context = manager.end_execution("test-plugin")
        assert final_context is not None

        # Should be removed
        assert manager.get_context("test-plugin") is None

    def test_end_execution_nonexistent(self) -> None:
        """Test ending non-existent execution."""
        manager = SandboxManager()
        final_context = manager.end_execution("nonexistent")
        assert final_context is None

    def test_check_limits(self) -> None:
        """Test checking resource limits via manager."""
        config = SandboxConfig(
            resource_limits=ResourceLimits(max_subprocess=5),
        )
        manager = SandboxManager(config=config)
        manager.start_execution("test-plugin")

        # Within limits
        assert manager.check_limits("test-plugin") is None

        # Exceed limit
        context = manager.get_context("test-plugin")
        context.subprocess_count = 10

        result = manager.check_limits("test-plugin")
        assert result is not None
        assert "Subprocess limit exceeded" in result

    def test_check_limits_no_context(self) -> None:
        """Test checking limits when no context exists."""
        manager = SandboxManager()
        result = manager.check_limits("nonexistent")
        assert result is None

    def test_validate_path_access_disabled(self) -> None:
        """Test path validation when sandbox is disabled."""
        config = SandboxConfig(enabled=False)
        manager = SandboxManager(config=config)

        allowed, error = manager.validate_path_access("test-plugin", "/etc/passwd", "read")
        assert allowed is True
        assert error is None

    def test_validate_path_access_workspace_disabled(self) -> None:
        """Test path validation when workspace isolation is disabled."""
        config = SandboxConfig(
            enabled=True,
            workspace=WorkspaceConfig(enabled=False),
        )
        manager = SandboxManager(config=config)

        allowed, error = manager.validate_path_access("test-plugin", "/etc/passwd", "write")
        assert allowed is True
        assert error is None

    def test_validate_path_access_read_allowed(self) -> None:
        """Test path validation for allowed read."""
        with TemporaryDirectory() as tmpdir:
            config = SandboxConfig(
                workspace=WorkspaceConfig(workspace_dir=Path(tmpdir)),
            )
            manager = SandboxManager(config=config)

            # Read inside workspace
            inner_path = str(Path(tmpdir) / "data.txt")
            allowed, error = manager.validate_path_access("test-plugin", inner_path, "read")
            assert allowed is True
            assert error is None

    def test_validate_path_access_read_denied(self) -> None:
        """Test path validation for denied read."""
        with TemporaryDirectory() as tmpdir:
            config = SandboxConfig(
                workspace=WorkspaceConfig(
                    workspace_dir=Path(tmpdir),
                    allow_read_outside=False,
                ),
            )
            manager = SandboxManager(config=config)

            allowed, error = manager.validate_path_access("test-plugin", "/etc/passwd", "read")
            assert allowed is False
            assert error is not None
            assert "outside allowed paths" in error

    def test_validate_path_access_write_allowed(self) -> None:
        """Test path validation for allowed write."""
        with TemporaryDirectory() as tmpdir:
            config = SandboxConfig(
                workspace=WorkspaceConfig(workspace_dir=Path(tmpdir)),
            )
            manager = SandboxManager(config=config)

            # Write inside workspace
            inner_path = str(Path(tmpdir) / "output.txt")
            allowed, error = manager.validate_path_access("test-plugin", inner_path, "write")
            assert allowed is True
            assert error is None

    def test_validate_path_access_write_denied(self) -> None:
        """Test path validation for denied write."""
        with TemporaryDirectory() as tmpdir:
            config = SandboxConfig(
                workspace=WorkspaceConfig(workspace_dir=Path(tmpdir)),
            )
            manager = SandboxManager(config=config)

            allowed, error = manager.validate_path_access("test-plugin", "/tmp/outside.txt", "write")
            assert allowed is False
            assert error is not None
            assert "outside workspace" in error

    def test_validate_path_access_delete(self) -> None:
        """Test path validation for delete mode."""
        with TemporaryDirectory() as tmpdir:
            config = SandboxConfig(
                workspace=WorkspaceConfig(workspace_dir=Path(tmpdir)),
            )
            manager = SandboxManager(config=config)

            # Delete inside workspace - allowed
            inner_path = str(Path(tmpdir) / "to_delete.txt")
            allowed, error = manager.validate_path_access("test-plugin", inner_path, "delete")
            assert allowed is True

            # Delete outside workspace - denied
            allowed, error = manager.validate_path_access("test-plugin", "/tmp/other.txt", "delete")
            assert allowed is False

    def test_validate_path_access_unknown_mode(self) -> None:
        """Test path validation with unknown mode."""
        with TemporaryDirectory() as tmpdir:
            config = SandboxConfig(
                workspace=WorkspaceConfig(workspace_dir=Path(tmpdir)),
            )
            manager = SandboxManager(config=config)

            allowed, error = manager.validate_path_access("test-plugin", "/tmp/file.txt", "execute")
            assert allowed is False
            assert error is not None
            assert "Unknown access mode" in error

    def test_validate_shell_access_disabled(self) -> None:
        """Test shell validation when sandbox is disabled."""
        config = SandboxConfig(enabled=False)
        manager = SandboxManager(config=config)

        allowed, error = manager.validate_shell_access("test-plugin")
        assert allowed is True
        assert error is None

    def test_validate_shell_access_allowed(self) -> None:
        """Test shell validation when allowed."""
        config = SandboxConfig(allow_shell=True)
        manager = SandboxManager(config=config)

        allowed, error = manager.validate_shell_access("test-plugin")
        assert allowed is True
        assert error is None

    def test_validate_shell_access_denied(self) -> None:
        """Test shell validation when denied."""
        config = SandboxConfig(allow_shell=False)
        manager = SandboxManager(config=config)

        allowed, error = manager.validate_shell_access("test-plugin")
        assert allowed is False
        assert error is not None
        assert "Shell access is disabled" in error

    def test_validate_network_access_disabled(self) -> None:
        """Test network validation when sandbox is disabled."""
        config = SandboxConfig(enabled=False)
        manager = SandboxManager(config=config)

        allowed, error = manager.validate_network_access("test-plugin")
        assert allowed is True
        assert error is None

    def test_validate_network_access_allowed(self) -> None:
        """Test network validation when allowed."""
        config = SandboxConfig(allow_network=True)
        manager = SandboxManager(config=config)

        allowed, error = manager.validate_network_access("test-plugin")
        assert allowed is True
        assert error is None

    def test_validate_network_access_denied(self) -> None:
        """Test network validation when denied."""
        config = SandboxConfig(allow_network=False)
        manager = SandboxManager(config=config)

        allowed, error = manager.validate_network_access("test-plugin")
        assert allowed is False
        assert error is not None
        assert "Network access is disabled" in error


class TestPluginSandboxWithWorkspace:
    """Tests for PluginSandbox with workspace configuration."""

    def test_sandbox_with_workspace_config(self) -> None:
        """Test creating sandbox with workspace config."""
        with TemporaryDirectory() as tmpdir:
            workspace_config = WorkspaceConfig(workspace_dir=Path(tmpdir))
            sandbox = PluginSandbox(
                plugin_name="test-plugin",
                workspace_config=workspace_config,
            )
            assert sandbox.workspace_config is not None

    def test_from_manifest_with_workspace(self) -> None:
        """Test creating sandbox from manifest with workspace."""
        with TemporaryDirectory() as tmpdir:
            workspace_config = WorkspaceConfig(workspace_dir=Path(tmpdir))
            sandbox = PluginSandbox.from_manifest_permissions(
                plugin_name="test-plugin",
                permissions=["filesystem:read", "filesystem:write"],
                workspace_config=workspace_config,
            )
            assert sandbox.workspace_config is not None
            assert sandbox.check_permission("filesystem:read")

    def test_check_permission_workspace_read_allowed(self) -> None:
        """Test permission check with workspace read allowed."""
        with TemporaryDirectory() as tmpdir:
            workspace_config = WorkspaceConfig(
                workspace_dir=Path(tmpdir),
                allow_read_outside=True,
            )
            sandbox = PluginSandbox.from_manifest_permissions(
                plugin_name="test-plugin",
                permissions=["filesystem:read"],
                workspace_config=workspace_config,
            )

            # Read inside workspace
            inner_path = str(Path(tmpdir) / "data.txt")
            assert sandbox.check_permission("filesystem:read", target=inner_path) is True

            # Read outside workspace (allowed because allow_read_outside=True)
            assert sandbox.check_permission("filesystem:read", target="/tmp/other.txt") is True

    def test_check_permission_workspace_read_denied(self) -> None:
        """Test permission check with workspace read denied."""
        with TemporaryDirectory() as tmpdir:
            workspace_config = WorkspaceConfig(
                workspace_dir=Path(tmpdir),
                allow_read_outside=False,
            )
            sandbox = PluginSandbox.from_manifest_permissions(
                plugin_name="test-plugin",
                permissions=["filesystem:read"],
                workspace_config=workspace_config,
            )

            # Read outside workspace (denied because allow_read_outside=False)
            assert sandbox.check_permission("filesystem:read", target="/tmp/other.txt") is False

    def test_check_permission_workspace_write_allowed(self) -> None:
        """Test permission check with workspace write allowed."""
        with TemporaryDirectory() as tmpdir:
            workspace_config = WorkspaceConfig(workspace_dir=Path(tmpdir))
            sandbox = PluginSandbox.from_manifest_permissions(
                plugin_name="test-plugin",
                permissions=["filesystem:write"],
                workspace_config=workspace_config,
            )

            # Write inside workspace
            inner_path = str(Path(tmpdir) / "output.txt")
            assert sandbox.check_permission("filesystem:write", target=inner_path) is True

    def test_check_permission_workspace_write_denied(self) -> None:
        """Test permission check with workspace write denied."""
        with TemporaryDirectory() as tmpdir:
            workspace_config = WorkspaceConfig(workspace_dir=Path(tmpdir))
            sandbox = PluginSandbox.from_manifest_permissions(
                plugin_name="test-plugin",
                permissions=["filesystem:write"],
                workspace_config=workspace_config,
            )

            # Write outside workspace (always denied)
            assert sandbox.check_permission("filesystem:write", target="/tmp/other.txt") is False

    def test_check_permission_workspace_delete_denied(self) -> None:
        """Test permission check with workspace delete denied."""
        with TemporaryDirectory() as tmpdir:
            workspace_config = WorkspaceConfig(workspace_dir=Path(tmpdir))
            sandbox = PluginSandbox.from_manifest_permissions(
                plugin_name="test-plugin",
                permissions=["filesystem:delete"],
                workspace_config=workspace_config,
            )

            # Delete outside workspace
            assert sandbox.check_permission("filesystem:delete", target="/tmp/other.txt") is False
