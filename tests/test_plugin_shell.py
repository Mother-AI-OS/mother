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
    async def test_unknown_capability(self, plugin: ShellPlugin) -> None:
        """Test executing unknown capability."""
        result = await plugin.execute("unknown_capability", {})

        assert result.success is False
        assert result.error_code == "UNKNOWN_CAPABILITY"
