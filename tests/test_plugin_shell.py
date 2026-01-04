"""Tests for the builtin shell plugin."""

import pytest

from mother.plugins.builtin.shell import ShellPlugin, _create_manifest


class TestShellManifest:
    """Tests for shell plugin manifest."""

    def test_create_manifest(self) -> None:
        """Test manifest creation."""
        manifest = _create_manifest()
        assert manifest.plugin.name == "shell"
        assert manifest.plugin.version == "1.0.0"
        assert len(manifest.capabilities) > 0

    def test_manifest_has_required_capabilities(self) -> None:
        """Test that required capabilities exist."""
        manifest = _create_manifest()
        cap_names = [c.name for c in manifest.capabilities]

        assert "run_command" in cap_names

    def test_run_command_requires_confirmation(self) -> None:
        """Test that run_command requires confirmation."""
        manifest = _create_manifest()
        run_cap = manifest.get_capability("run_command")
        assert run_cap is not None
        assert run_cap.confirmation_required is True


class TestShellPlugin:
    """Tests for ShellPlugin execution."""

    @pytest.fixture
    def plugin(self) -> ShellPlugin:
        """Create a plugin instance for testing."""
        return ShellPlugin()

    @pytest.mark.asyncio
    async def test_run_command_echo(self, plugin: ShellPlugin) -> None:
        """Test running a simple echo command."""
        result = await plugin.execute("run_command", {"command": "echo hello"})

        assert result.success is True
        assert "hello" in result.raw_output

    @pytest.mark.asyncio
    async def test_run_command_with_output(self, plugin: ShellPlugin) -> None:
        """Test running a command with output."""
        result = await plugin.execute("run_command", {"command": "pwd"})

        assert result.success is True
        assert result.raw_output is not None
        assert len(result.raw_output) > 0

    @pytest.mark.asyncio
    async def test_run_command_nonzero_exit(self, plugin: ShellPlugin) -> None:
        """Test running a command with non-zero exit code."""
        result = await plugin.execute("run_command", {"command": "false"})

        # The plugin returns success=True but data["success"]=False for failed commands
        assert result.success is True
        assert result.data is not None
        assert result.data["success"] is False
        assert result.data["exit_code"] != 0

    @pytest.mark.asyncio
    async def test_run_command_not_found(self, plugin: ShellPlugin) -> None:
        """Test running a command that doesn't exist."""
        result = await plugin.execute(
            "run_command",
            {"command": "nonexistent_command_12345"},
        )

        # Command execution succeeds but the command itself fails
        assert result.success is True
        assert result.data is not None
        assert result.data["success"] is False

    @pytest.mark.asyncio
    async def test_system_info(self, plugin: ShellPlugin) -> None:
        """Test getting system info."""
        result = await plugin.execute("system_info", {})

        assert result.success is True
        assert result.data is not None
        # The system_info capability returns hostname, username, os keys
        assert "hostname" in result.data
        assert "username" in result.data
        assert "os" in result.data
        assert "python_version" in result.data

    @pytest.mark.asyncio
    async def test_which_command(self, plugin: ShellPlugin) -> None:
        """Test which command."""
        result = await plugin.execute("which", {"command": "python"})

        # Python might not be installed or might be python3
        # Just check the response is valid
        assert result.data is not None
        assert "command" in result.data
        assert "found" in result.data

    @pytest.mark.asyncio
    async def test_get_env_existing(self, plugin: ShellPlugin) -> None:
        """Test getting an existing environment variable."""
        result = await plugin.execute("get_env", {"name": "PATH"})

        assert result.success is True
        assert result.data["name"] == "PATH"
        assert result.data["exists"] is True
        assert result.data["value"] is not None

    @pytest.mark.asyncio
    async def test_get_env_nonexistent(self, plugin: ShellPlugin) -> None:
        """Test getting a non-existent environment variable."""
        result = await plugin.execute("get_env", {"name": "NONEXISTENT_VAR_12345"})

        assert result.success is True
        assert result.data["name"] == "NONEXISTENT_VAR_12345"
        assert result.data["exists"] is False
        assert result.data["value"] is None

    @pytest.mark.asyncio
    async def test_get_env_with_default(self, plugin: ShellPlugin) -> None:
        """Test getting env var with default value."""
        result = await plugin.execute(
            "get_env",
            {"name": "NONEXISTENT_VAR_12345", "default": "default_value"},
        )

        assert result.success is True
        assert result.data["value"] == "default_value"
        assert result.data["exists"] is False

    @pytest.mark.asyncio
    async def test_list_env(self, plugin: ShellPlugin) -> None:
        """Test listing environment variables."""
        result = await plugin.execute("list_env", {})

        assert result.success is True
        assert result.data["count"] > 0
        assert "variables" in result.data
        assert isinstance(result.data["variables"], dict)

    @pytest.mark.asyncio
    async def test_list_env_with_prefix(self, plugin: ShellPlugin) -> None:
        """Test listing env vars with prefix filter."""
        result = await plugin.execute("list_env", {"prefix": "PATH"})

        assert result.success is True
        assert result.data["prefix"] == "PATH"
        # All returned vars should start with PATH
        for key in result.data["variables"]:
            assert key.startswith("PATH")

    @pytest.mark.asyncio
    async def test_list_env_without_values(self, plugin: ShellPlugin) -> None:
        """Test listing env vars without values."""
        result = await plugin.execute("list_env", {"include_values": False})

        assert result.success is True
        # Values should be None
        for value in result.data["variables"].values():
            assert value is None

    @pytest.mark.asyncio
    async def test_get_cwd(self, plugin: ShellPlugin) -> None:
        """Test getting current working directory."""
        result = await plugin.execute("get_cwd", {})

        assert result.success is True
        assert "cwd" in result.data
        assert "path" in result.data
        assert len(result.data["cwd"]) > 0

    @pytest.mark.asyncio
    async def test_hostname(self, plugin: ShellPlugin) -> None:
        """Test getting hostname."""
        result = await plugin.execute("hostname", {})

        assert result.success is True
        assert "hostname" in result.data
        assert "fqdn" in result.data
        assert len(result.data["hostname"]) > 0

    @pytest.mark.asyncio
    async def test_whoami(self, plugin: ShellPlugin) -> None:
        """Test getting current user."""
        result = await plugin.execute("whoami", {})

        assert result.success is True
        assert "username" in result.data
        assert "uid" in result.data
        assert "gid" in result.data
        assert "home" in result.data

    @pytest.mark.asyncio
    async def test_command_exists_true(self, plugin: ShellPlugin) -> None:
        """Test checking if command exists (true case)."""
        result = await plugin.execute("command_exists", {"command": "ls"})

        assert result.success is True
        assert result.data["command"] == "ls"
        assert result.data["exists"] is True
        assert result.data["path"] is not None

    @pytest.mark.asyncio
    async def test_command_exists_false(self, plugin: ShellPlugin) -> None:
        """Test checking if command exists (false case)."""
        result = await plugin.execute("command_exists", {"command": "nonexistent_cmd_12345"})

        assert result.success is True
        assert result.data["command"] == "nonexistent_cmd_12345"
        assert result.data["exists"] is False
        assert result.data["path"] is None

    @pytest.mark.asyncio
    async def test_unknown_capability(self, plugin: ShellPlugin) -> None:
        """Test executing unknown capability."""
        result = await plugin.execute("unknown_capability", {})

        assert result.success is False
        assert result.error_code == "UNKNOWN_CAPABILITY"
