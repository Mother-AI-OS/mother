"""Tests for the built-in shell plugin."""

import os
from unittest.mock import patch

import pytest

from mother.plugins.builtin.shell import ShellPlugin, _create_manifest


class TestCreateManifest:
    """Tests for _create_manifest function."""

    def test_creates_valid_manifest(self):
        """Test that manifest is created correctly."""
        manifest = _create_manifest()

        assert manifest.plugin.name == "shell"
        assert manifest.plugin.version == "1.0.0"
        assert len(manifest.capabilities) > 0

    def test_manifest_has_expected_capabilities(self):
        """Test manifest has expected capabilities."""
        manifest = _create_manifest()
        cap_names = [c.name for c in manifest.capabilities]

        assert "run_command" in cap_names
        assert "run_script" in cap_names
        assert "get_env" in cap_names
        assert "list_env" in cap_names
        assert "which" in cap_names
        assert "get_cwd" in cap_names
        assert "hostname" in cap_names
        assert "whoami" in cap_names
        assert "command_exists" in cap_names
        assert "system_info" in cap_names


class TestShellPluginInit:
    """Tests for ShellPlugin initialization."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        plugin = ShellPlugin()

        assert plugin._blocked_commands == []
        assert plugin._allowed_cwd == []

    def test_init_with_blocked_commands(self):
        """Test initialization with blocked commands."""
        config = {"blocked_commands": ["rm", "sudo"]}
        plugin = ShellPlugin(config=config)

        assert plugin._blocked_commands == ["rm", "sudo"]

    def test_init_with_allowed_cwd(self, tmp_path):
        """Test initialization with allowed cwd."""
        config = {"allowed_cwd": [str(tmp_path)]}
        plugin = ShellPlugin(config=config)

        assert len(plugin._allowed_cwd) == 1
        assert plugin._allowed_cwd[0] == tmp_path.resolve()


class TestShellPluginSecurityChecks:
    """Tests for security check methods."""

    def test_check_command_allowed_basic(self):
        """Test basic command is allowed."""
        plugin = ShellPlugin()

        allowed, error = plugin._check_command_allowed("echo hello")
        assert allowed is True
        assert error is None

    def test_check_command_blocked(self):
        """Test blocked command is rejected."""
        plugin = ShellPlugin(config={"blocked_commands": ["rm"]})

        allowed, error = plugin._check_command_allowed("rm -rf /tmp/test")
        assert allowed is False
        assert "blocked" in error.lower()

    def test_check_command_dangerous_rm_rf_root(self):
        """Test rm -rf / is blocked."""
        plugin = ShellPlugin()

        allowed, error = plugin._check_command_allowed("rm -rf /")
        assert allowed is False
        assert "dangerous" in error.lower()

    def test_check_command_dangerous_rm_rf_star(self):
        """Test rm -rf /* is blocked."""
        plugin = ShellPlugin()

        allowed, error = plugin._check_command_allowed("rm -rf /*")
        assert allowed is False

    def test_check_command_dangerous_fork_bomb(self):
        """Test fork bomb is blocked."""
        plugin = ShellPlugin()

        allowed, error = plugin._check_command_allowed(":(){:|:&};:")
        assert allowed is False

    def test_check_command_dangerous_dd(self):
        """Test dd if= is blocked."""
        plugin = ShellPlugin()

        allowed, error = plugin._check_command_allowed("dd if=/dev/zero of=/dev/sda")
        assert allowed is False

    def test_check_cwd_allowed_no_restrictions(self):
        """Test cwd allowed when no restrictions."""
        plugin = ShellPlugin()

        assert plugin._check_cwd_allowed("/any/path") is True

    def test_check_cwd_allowed_in_list(self, tmp_path):
        """Test cwd allowed when in allowed list."""
        plugin = ShellPlugin(config={"allowed_cwd": [str(tmp_path)]})

        assert plugin._check_cwd_allowed(str(tmp_path)) is True

    def test_check_cwd_allowed_subdirectory(self, tmp_path):
        """Test cwd allowed for subdirectory of allowed path."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        plugin = ShellPlugin(config={"allowed_cwd": [str(tmp_path)]})

        assert plugin._check_cwd_allowed(str(subdir)) is True

    def test_check_cwd_not_allowed(self, tmp_path):
        """Test cwd not allowed when not in list."""
        plugin = ShellPlugin(config={"allowed_cwd": [str(tmp_path)]})

        assert plugin._check_cwd_allowed("/other/path") is False


class TestShellPluginExecute:
    """Tests for execute method."""

    @pytest.mark.asyncio
    async def test_execute_unknown_capability(self):
        """Test execute with unknown capability."""
        plugin = ShellPlugin()

        result = await plugin.execute("unknown_cap", {})
        assert result.success is False
        assert result.error_code == "UNKNOWN_CAPABILITY"

    @pytest.mark.asyncio
    async def test_execute_handler_exception(self):
        """Test execute handles handler exception."""
        plugin = ShellPlugin()

        # Mock a handler that raises an exception
        with patch.object(plugin, "_get_env", side_effect=Exception("Test error")):
            result = await plugin.execute("get_env", {"name": "TEST"})

        assert result.success is False
        assert result.error_code == "SHELL_ERROR"


class TestShellPluginRunCommand:
    """Tests for run_command capability."""

    @pytest.mark.asyncio
    async def test_run_command_success(self):
        """Test successful command execution."""
        plugin = ShellPlugin()

        result = await plugin.execute("run_command", {"command": "echo hello"})

        assert result.success is True
        assert result.data["exit_code"] == 0
        assert "hello" in result.data["stdout"]

    @pytest.mark.asyncio
    async def test_run_command_blocked(self):
        """Test blocked command."""
        plugin = ShellPlugin(config={"blocked_commands": ["echo"]})

        result = await plugin.execute("run_command", {"command": "echo hello"})

        assert result.success is False
        assert result.error_code == "COMMAND_BLOCKED"

    @pytest.mark.asyncio
    async def test_run_command_cwd_not_allowed(self, tmp_path):
        """Test command with disallowed cwd."""
        plugin = ShellPlugin(config={"allowed_cwd": [str(tmp_path)]})

        result = await plugin.execute("run_command", {"command": "ls", "cwd": "/tmp/other"})

        assert result.success is False
        assert result.error_code == "CWD_NOT_ALLOWED"

    @pytest.mark.asyncio
    async def test_run_command_with_env(self):
        """Test command with custom environment."""
        plugin = ShellPlugin()

        result = await plugin.execute(
            "run_command",
            {"command": "echo $MY_VAR", "env": {"MY_VAR": "test_value"}},
        )

        assert result.success is True
        assert "test_value" in result.data["stdout"]

    @pytest.mark.asyncio
    async def test_run_command_with_cwd(self, tmp_path):
        """Test command with custom working directory."""
        plugin = ShellPlugin()

        result = await plugin.execute("run_command", {"command": "pwd", "cwd": str(tmp_path)})

        assert result.success is True
        assert str(tmp_path) in result.data["stdout"]

    @pytest.mark.asyncio
    async def test_run_command_timeout(self):
        """Test command timeout."""
        plugin = ShellPlugin()

        result = await plugin.execute("run_command", {"command": "sleep 10", "timeout": 1})

        assert result.success is False
        assert "timed out" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_run_command_nonzero_exit(self):
        """Test command with non-zero exit code."""
        plugin = ShellPlugin()

        result = await plugin.execute("run_command", {"command": "exit 1"})

        assert result.success is True  # Execution succeeded
        assert result.data["exit_code"] == 1
        assert result.data["success"] is False


class TestShellPluginRunScript:
    """Tests for run_script capability."""

    @pytest.mark.asyncio
    async def test_run_script_success(self):
        """Test successful script execution."""
        plugin = ShellPlugin()
        script = """
echo "Line 1"
echo "Line 2"
"""
        result = await plugin.execute("run_script", {"script": script})

        assert result.success is True
        assert result.data["exit_code"] == 0
        assert "Line 1" in result.data["stdout"]
        assert "Line 2" in result.data["stdout"]

    @pytest.mark.asyncio
    async def test_run_script_shell_not_found(self):
        """Test script with non-existent shell."""
        plugin = ShellPlugin()

        result = await plugin.execute("run_script", {"script": "echo hello", "shell": "/nonexistent/shell"})

        assert result.success is False
        assert result.error_code == "SHELL_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_run_script_cwd_not_allowed(self, tmp_path):
        """Test script with disallowed cwd."""
        plugin = ShellPlugin(config={"allowed_cwd": [str(tmp_path)]})

        result = await plugin.execute("run_script", {"script": "pwd", "cwd": "/tmp/other"})

        assert result.success is False
        assert result.error_code == "CWD_NOT_ALLOWED"

    @pytest.mark.asyncio
    async def test_run_script_timeout(self):
        """Test script timeout."""
        plugin = ShellPlugin()

        result = await plugin.execute("run_script", {"script": "sleep 10", "timeout": 1})

        assert result.success is False
        assert "timed out" in result.error_message.lower()


class TestShellPluginEnv:
    """Tests for environment-related capabilities."""

    @pytest.mark.asyncio
    async def test_get_env_exists(self):
        """Test getting existing env variable."""
        plugin = ShellPlugin()

        result = await plugin.execute("get_env", {"name": "PATH"})

        assert result.success is True
        assert result.data["exists"] is True
        assert result.data["value"] is not None

    @pytest.mark.asyncio
    async def test_get_env_not_exists(self):
        """Test getting non-existent env variable."""
        plugin = ShellPlugin()

        result = await plugin.execute("get_env", {"name": "NONEXISTENT_VAR_12345"})

        assert result.success is True
        assert result.data["exists"] is False
        assert result.data["value"] is None

    @pytest.mark.asyncio
    async def test_get_env_with_default(self):
        """Test getting env variable with default."""
        plugin = ShellPlugin()

        result = await plugin.execute("get_env", {"name": "NONEXISTENT_VAR_12345", "default": "default_value"})

        assert result.success is True
        assert result.data["value"] == "default_value"

    @pytest.mark.asyncio
    async def test_list_env(self):
        """Test listing env variables."""
        plugin = ShellPlugin()

        result = await plugin.execute("list_env", {})

        assert result.success is True
        assert result.data["count"] > 0
        assert "PATH" in result.data["variables"]

    @pytest.mark.asyncio
    async def test_list_env_with_prefix(self):
        """Test listing env variables with prefix filter."""
        plugin = ShellPlugin()

        result = await plugin.execute("list_env", {"prefix": "PATH"})

        assert result.success is True
        for key in result.data["variables"]:
            assert key.startswith("PATH")

    @pytest.mark.asyncio
    async def test_list_env_without_values(self):
        """Test listing env variables without values."""
        plugin = ShellPlugin()

        result = await plugin.execute("list_env", {"include_values": False})

        assert result.success is True
        for value in result.data["variables"].values():
            assert value is None


class TestShellPluginUtilities:
    """Tests for utility capabilities."""

    @pytest.mark.asyncio
    async def test_which_found(self):
        """Test which finds existing command."""
        plugin = ShellPlugin()

        result = await plugin.execute("which", {"command": "python3"})

        assert result.success is True
        assert result.data["found"] is True
        assert result.data["path"] is not None

    @pytest.mark.asyncio
    async def test_which_not_found(self):
        """Test which with non-existent command."""
        plugin = ShellPlugin()

        result = await plugin.execute("which", {"command": "nonexistent_cmd_xyz"})

        assert result.success is True
        assert result.data["found"] is False
        assert result.data["path"] is None

    @pytest.mark.asyncio
    async def test_get_cwd(self):
        """Test get_cwd capability."""
        plugin = ShellPlugin()

        result = await plugin.execute("get_cwd", {})

        assert result.success is True
        assert result.data["cwd"] == os.getcwd()

    @pytest.mark.asyncio
    async def test_hostname(self):
        """Test hostname capability."""
        plugin = ShellPlugin()

        result = await plugin.execute("hostname", {})

        assert result.success is True
        assert "hostname" in result.data
        assert "fqdn" in result.data

    @pytest.mark.asyncio
    async def test_whoami(self):
        """Test whoami capability."""
        plugin = ShellPlugin()

        result = await plugin.execute("whoami", {})

        assert result.success is True
        assert "username" in result.data
        assert "uid" in result.data
        assert "gid" in result.data
        assert "home" in result.data

    @pytest.mark.asyncio
    async def test_command_exists_true(self):
        """Test command_exists for existing command."""
        plugin = ShellPlugin()

        result = await plugin.execute("command_exists", {"command": "python3"})

        assert result.success is True
        assert result.data["exists"] is True

    @pytest.mark.asyncio
    async def test_command_exists_false(self):
        """Test command_exists for non-existent command."""
        plugin = ShellPlugin()

        result = await plugin.execute("command_exists", {"command": "nonexistent_xyz"})

        assert result.success is True
        assert result.data["exists"] is False

    @pytest.mark.asyncio
    async def test_system_info(self):
        """Test system_info capability."""
        plugin = ShellPlugin()

        result = await plugin.execute("system_info", {})

        assert result.success is True
        assert "os" in result.data
        assert "architecture" in result.data
        assert "python_version" in result.data
        assert "hostname" in result.data
        assert "username" in result.data
