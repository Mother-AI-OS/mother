"""Tests for the builtin filesystem plugin."""

import tempfile
from pathlib import Path

import pytest

from mother.plugins.builtin.filesystem import FilesystemPlugin, _create_manifest


class TestFilesystemManifest:
    """Tests for filesystem plugin manifest."""

    def test_create_manifest(self) -> None:
        """Test manifest creation."""
        manifest = _create_manifest()
        assert manifest.plugin.name == "filesystem"
        assert manifest.plugin.version == "1.0.0"
        assert len(manifest.capabilities) > 0

    def test_manifest_has_required_capabilities(self) -> None:
        """Test that required capabilities exist."""
        manifest = _create_manifest()
        cap_names = [c.name for c in manifest.capabilities]

        assert "read_file" in cap_names
        assert "write_file" in cap_names
        assert "list_directory" in cap_names
        assert "file_info" in cap_names
        assert "delete_file" in cap_names
        assert "exists" in cap_names

    def test_write_requires_confirmation(self) -> None:
        """Test that write_file requires confirmation."""
        manifest = _create_manifest()
        write_cap = manifest.get_capability("write_file")
        assert write_cap is not None
        assert write_cap.confirmation_required is True

    def test_delete_requires_confirmation(self) -> None:
        """Test that delete_file requires confirmation."""
        manifest = _create_manifest()
        delete_cap = manifest.get_capability("delete_file")
        assert delete_cap is not None
        assert delete_cap.confirmation_required is True


class TestFilesystemPlugin:
    """Tests for FilesystemPlugin execution."""

    @pytest.fixture
    def plugin(self) -> FilesystemPlugin:
        """Create a plugin instance for testing."""
        return FilesystemPlugin()

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_read_file_success(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test reading a file successfully."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")

        result = await plugin.execute("read_file", {"path": str(test_file)})

        assert result.success is True
        assert result.data["content"] == "Hello, World!"
        assert result.data["size"] == 13

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test reading a non-existent file."""
        result = await plugin.execute("read_file", {"path": str(temp_dir / "nonexistent.txt")})

        assert result.success is False
        assert result.error_code == "FILE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_read_file_not_a_file(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test reading a directory as file."""
        result = await plugin.execute("read_file", {"path": str(temp_dir)})

        assert result.success is False
        assert result.error_code == "NOT_A_FILE"

    @pytest.mark.asyncio
    async def test_read_file_too_large(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test reading a file exceeding max size."""
        test_file = temp_dir / "large.txt"
        test_file.write_text("X" * 100)

        result = await plugin.execute(
            "read_file",
            {"path": str(test_file), "max_size": 50},
        )

        assert result.success is False
        assert result.error_code == "FILE_TOO_LARGE"

    @pytest.mark.asyncio
    async def test_write_file_success(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test writing to a file."""
        test_file = temp_dir / "output.txt"

        result = await plugin.execute(
            "write_file",
            {"path": str(test_file), "content": "Test content"},
        )

        assert result.success is True
        assert result.data["action"] == "written"
        assert test_file.read_text() == "Test content"

    @pytest.mark.asyncio
    async def test_write_file_create_dirs(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test writing with create_dirs option."""
        test_file = temp_dir / "subdir" / "nested" / "file.txt"

        result = await plugin.execute(
            "write_file",
            {
                "path": str(test_file),
                "content": "Nested content",
                "create_dirs": True,
            },
        )

        assert result.success is True
        assert test_file.exists()
        assert test_file.read_text() == "Nested content"

    @pytest.mark.asyncio
    async def test_write_file_parent_not_found(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test writing when parent directory doesn't exist."""
        test_file = temp_dir / "nonexistent" / "file.txt"

        result = await plugin.execute(
            "write_file",
            {"path": str(test_file), "content": "Content"},
        )

        assert result.success is False
        assert result.error_code == "PARENT_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_append_file_success(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test appending to a file."""
        test_file = temp_dir / "append.txt"
        test_file.write_text("First\n")

        result = await plugin.execute(
            "append_file",
            {"path": str(test_file), "content": "Second\n"},
        )

        assert result.success is True
        assert result.data["action"] == "appended"
        assert test_file.read_text() == "First\nSecond\n"

    @pytest.mark.asyncio
    async def test_list_directory_success(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test listing directory contents."""
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.txt").write_text("content2")
        (temp_dir / "subdir").mkdir()

        result = await plugin.execute("list_directory", {"path": str(temp_dir)})

        assert result.success is True
        assert result.data["count"] == 3

        names = [e["name"] for e in result.data["entries"]]
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "subdir" in names

    @pytest.mark.asyncio
    async def test_list_directory_with_pattern(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test listing directory with pattern filter."""
        (temp_dir / "file1.txt").write_text("content")
        (temp_dir / "file2.py").write_text("content")
        (temp_dir / "file3.txt").write_text("content")

        result = await plugin.execute(
            "list_directory",
            {"path": str(temp_dir), "pattern": "*.txt"},
        )

        assert result.success is True
        assert result.data["count"] == 2

    @pytest.mark.asyncio
    async def test_list_directory_not_found(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test listing non-existent directory."""
        result = await plugin.execute(
            "list_directory",
            {"path": str(temp_dir / "nonexistent")},
        )

        assert result.success is False
        assert result.error_code == "DIR_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_list_directory_not_a_directory(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test listing a file as directory."""
        test_file = temp_dir / "file.txt"
        test_file.write_text("content")

        result = await plugin.execute("list_directory", {"path": str(test_file)})

        assert result.success is False
        assert result.error_code == "NOT_A_DIRECTORY"

    @pytest.mark.asyncio
    async def test_file_info_success(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test getting file info."""
        test_file = temp_dir / "info.txt"
        test_file.write_text("content")

        result = await plugin.execute("file_info", {"path": str(test_file)})

        assert result.success is True
        assert result.data["type"] == "file"
        assert result.data["size"] == 7
        assert "modified" in result.data
        assert "permissions" in result.data

    @pytest.mark.asyncio
    async def test_file_info_directory(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test getting directory info."""
        subdir = temp_dir / "subdir"
        subdir.mkdir()

        result = await plugin.execute("file_info", {"path": str(subdir)})

        assert result.success is True
        assert result.data["type"] == "directory"

    @pytest.mark.asyncio
    async def test_file_info_not_found(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test file info for non-existent path."""
        result = await plugin.execute(
            "file_info",
            {"path": str(temp_dir / "nonexistent")},
        )

        assert result.success is False
        assert result.error_code == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_delete_file_success(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test deleting a file."""
        test_file = temp_dir / "delete_me.txt"
        test_file.write_text("content")

        result = await plugin.execute("delete_file", {"path": str(test_file)})

        assert result.success is True
        assert result.data["action"] == "deleted"
        assert not test_file.exists()

    @pytest.mark.asyncio
    async def test_delete_empty_directory(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test deleting an empty directory."""
        subdir = temp_dir / "empty_dir"
        subdir.mkdir()

        result = await plugin.execute("delete_file", {"path": str(subdir)})

        assert result.success is True
        assert not subdir.exists()

    @pytest.mark.asyncio
    async def test_delete_non_empty_directory(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test deleting a non-empty directory (should fail)."""
        subdir = temp_dir / "non_empty"
        subdir.mkdir()
        (subdir / "file.txt").write_text("content")

        result = await plugin.execute("delete_file", {"path": str(subdir)})

        assert result.success is False
        assert result.error_code == "DIR_NOT_EMPTY"

    @pytest.mark.asyncio
    async def test_copy_file_success(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test copying a file."""
        src = temp_dir / "source.txt"
        dst = temp_dir / "destination.txt"
        src.write_text("original content")

        result = await plugin.execute(
            "copy_file",
            {"source": str(src), "destination": str(dst)},
        )

        assert result.success is True
        assert result.data["action"] == "copied"
        assert dst.exists()
        assert dst.read_text() == "original content"
        assert src.exists()  # Source should still exist

    @pytest.mark.asyncio
    async def test_copy_file_destination_exists(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test copying when destination exists (no overwrite)."""
        src = temp_dir / "source.txt"
        dst = temp_dir / "destination.txt"
        src.write_text("source")
        dst.write_text("destination")

        result = await plugin.execute(
            "copy_file",
            {"source": str(src), "destination": str(dst)},
        )

        assert result.success is False
        assert result.error_code == "DESTINATION_EXISTS"

    @pytest.mark.asyncio
    async def test_copy_file_with_overwrite(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test copying with overwrite."""
        src = temp_dir / "source.txt"
        dst = temp_dir / "destination.txt"
        src.write_text("new content")
        dst.write_text("old content")

        result = await plugin.execute(
            "copy_file",
            {"source": str(src), "destination": str(dst), "overwrite": True},
        )

        assert result.success is True
        assert dst.read_text() == "new content"

    @pytest.mark.asyncio
    async def test_move_file_success(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test moving a file."""
        src = temp_dir / "source.txt"
        dst = temp_dir / "destination.txt"
        src.write_text("content to move")

        result = await plugin.execute(
            "move_file",
            {"source": str(src), "destination": str(dst)},
        )

        assert result.success is True
        assert result.data["action"] == "moved"
        assert dst.exists()
        assert not src.exists()

    @pytest.mark.asyncio
    async def test_create_directory_success(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test creating a directory."""
        new_dir = temp_dir / "new_directory"

        result = await plugin.execute("create_directory", {"path": str(new_dir)})

        assert result.success is True
        assert result.data["action"] == "created"
        assert new_dir.exists()
        assert new_dir.is_dir()

    @pytest.mark.asyncio
    async def test_create_directory_with_parents(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test creating nested directories."""
        nested_dir = temp_dir / "a" / "b" / "c"

        result = await plugin.execute(
            "create_directory",
            {"path": str(nested_dir), "parents": True},
        )

        assert result.success is True
        assert nested_dir.exists()

    @pytest.mark.asyncio
    async def test_create_directory_already_exists(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test creating a directory that already exists."""
        existing_dir = temp_dir / "existing"
        existing_dir.mkdir()

        result = await plugin.execute("create_directory", {"path": str(existing_dir)})

        assert result.success is True
        assert result.data["action"] == "already_exists"

    @pytest.mark.asyncio
    async def test_exists_file(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test checking file existence."""
        test_file = temp_dir / "exists.txt"
        test_file.write_text("content")

        result = await plugin.execute("exists", {"path": str(test_file)})

        assert result.success is True
        assert result.data["exists"] is True
        assert result.data["is_file"] is True
        assert result.data["is_directory"] is False

    @pytest.mark.asyncio
    async def test_exists_directory(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test checking directory existence."""
        result = await plugin.execute("exists", {"path": str(temp_dir)})

        assert result.success is True
        assert result.data["exists"] is True
        assert result.data["is_file"] is False
        assert result.data["is_directory"] is True

    @pytest.mark.asyncio
    async def test_exists_not_found(self, plugin: FilesystemPlugin, temp_dir: Path) -> None:
        """Test checking non-existent path."""
        result = await plugin.execute(
            "exists",
            {"path": str(temp_dir / "nonexistent")},
        )

        assert result.success is True
        assert result.data["exists"] is False

    @pytest.mark.asyncio
    async def test_unknown_capability(self, plugin: FilesystemPlugin) -> None:
        """Test executing unknown capability."""
        result = await plugin.execute("unknown_capability", {})

        assert result.success is False
        assert result.error_code == "UNKNOWN_CAPABILITY"


class TestFilesystemPluginSecurity:
    """Tests for filesystem plugin security features."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_allowed_paths_config(self, temp_dir: Path) -> None:
        """Test configuring allowed paths."""
        allowed = temp_dir / "allowed"
        allowed.mkdir()

        plugin = FilesystemPlugin(config={"allowed_paths": [str(allowed)]})
        assert len(plugin._allowed_paths) == 1

    @pytest.mark.asyncio
    async def test_access_denied_outside_allowed(self, temp_dir: Path) -> None:
        """Test access denied for paths outside allowed."""
        allowed = temp_dir / "allowed"
        allowed.mkdir()
        (allowed / "test.txt").write_text("allowed content")

        forbidden = temp_dir / "forbidden"
        forbidden.mkdir()
        (forbidden / "secret.txt").write_text("secret content")

        plugin = FilesystemPlugin(config={"allowed_paths": [str(allowed)]})

        # Should work for allowed path
        result = await plugin.execute("read_file", {"path": str(allowed / "test.txt")})
        assert result.success is True

        # Should fail for forbidden path
        result = await plugin.execute("read_file", {"path": str(forbidden / "secret.txt")})
        assert result.success is False
        assert result.error_code == "ACCESS_DENIED"
