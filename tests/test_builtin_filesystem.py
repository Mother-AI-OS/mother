"""Tests for the built-in filesystem plugin."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from mother.plugins.builtin.filesystem import FilesystemPlugin, _create_manifest


class TestCreateManifest:
    """Tests for _create_manifest function."""

    def test_creates_valid_manifest(self):
        """Test that manifest is created correctly."""
        manifest = _create_manifest()

        assert manifest.plugin.name == "filesystem"
        assert manifest.plugin.version == "1.0.0"
        assert len(manifest.capabilities) > 0

    def test_manifest_has_expected_capabilities(self):
        """Test manifest has expected capabilities."""
        manifest = _create_manifest()
        cap_names = [c.name for c in manifest.capabilities]

        assert "read_file" in cap_names
        assert "write_file" in cap_names
        assert "append_file" in cap_names
        assert "list_directory" in cap_names
        assert "file_info" in cap_names
        assert "delete_file" in cap_names
        assert "copy_file" in cap_names
        assert "move_file" in cap_names
        assert "create_directory" in cap_names
        assert "exists" in cap_names


class TestFilesystemPluginInit:
    """Tests for FilesystemPlugin initialization."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        plugin = FilesystemPlugin()

        assert plugin._allowed_paths == []

    def test_init_with_allowed_paths(self, tmp_path):
        """Test initialization with allowed paths."""
        config = {"allowed_paths": [str(tmp_path)]}
        plugin = FilesystemPlugin(config=config)

        assert len(plugin._allowed_paths) == 1
        assert plugin._allowed_paths[0] == tmp_path.resolve()


class TestCheckPathAllowed:
    """Tests for _check_path_allowed method."""

    def test_no_restrictions_allows_all(self, tmp_path):
        """Test that all paths are allowed when no restrictions."""
        plugin = FilesystemPlugin()

        assert plugin._check_path_allowed(tmp_path) is True
        assert plugin._check_path_allowed(Path("/any/path")) is True

    def test_allowed_path_exact_match(self, tmp_path):
        """Test exact path match is allowed."""
        plugin = FilesystemPlugin(config={"allowed_paths": [str(tmp_path)]})

        assert plugin._check_path_allowed(tmp_path) is True

    def test_allowed_path_subdirectory(self, tmp_path):
        """Test subdirectory of allowed path is allowed."""
        plugin = FilesystemPlugin(config={"allowed_paths": [str(tmp_path)]})
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        assert plugin._check_path_allowed(subdir) is True

    def test_disallowed_path_rejected(self, tmp_path):
        """Test path outside allowed paths is rejected."""
        plugin = FilesystemPlugin(config={"allowed_paths": [str(tmp_path)]})

        assert plugin._check_path_allowed(Path("/other/path")) is False


class TestResolvePath:
    """Tests for _resolve_path method."""

    def test_absolute_path(self, tmp_path):
        """Test absolute path is resolved."""
        plugin = FilesystemPlugin()

        result = plugin._resolve_path(str(tmp_path))

        assert result == tmp_path.resolve()

    def test_relative_path(self, tmp_path):
        """Test relative path is resolved against cwd."""
        plugin = FilesystemPlugin()

        # Change to tmp_path and use relative path
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = plugin._resolve_path("subdir")
            assert result == (tmp_path / "subdir").resolve()
        finally:
            os.chdir(original_cwd)

    def test_expanduser(self):
        """Test ~ is expanded."""
        plugin = FilesystemPlugin()

        result = plugin._resolve_path("~/testfile")

        assert "~" not in str(result)
        assert str(Path.home()) in str(result)


class TestExecute:
    """Tests for execute method."""

    @pytest.mark.asyncio
    async def test_unknown_capability(self):
        """Test execute with unknown capability."""
        plugin = FilesystemPlugin()

        result = await plugin.execute("unknown_cap", {})

        assert result.success is False
        assert result.error_code == "UNKNOWN_CAPABILITY"

    @pytest.mark.asyncio
    async def test_permission_error_handling(self, tmp_path):
        """Test execute handles PermissionError."""
        plugin = FilesystemPlugin()

        with patch.object(plugin, "_read_file", side_effect=PermissionError("access denied")):
            result = await plugin.execute("read_file", {"path": str(tmp_path / "file.txt")})

        assert result.success is False
        assert result.error_code == "PERMISSION_DENIED"

    @pytest.mark.asyncio
    async def test_file_not_found_error_handling(self, tmp_path):
        """Test execute handles FileNotFoundError."""
        plugin = FilesystemPlugin()

        with patch.object(plugin, "_read_file", side_effect=FileNotFoundError("not found")):
            result = await plugin.execute("read_file", {"path": str(tmp_path / "file.txt")})

        assert result.success is False
        assert result.error_code == "FILE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_generic_error_handling(self, tmp_path):
        """Test execute handles generic exceptions."""
        plugin = FilesystemPlugin()

        with patch.object(plugin, "_read_file", side_effect=Exception("unexpected error")):
            result = await plugin.execute("read_file", {"path": str(tmp_path / "file.txt")})

        assert result.success is False
        assert result.error_code == "FILESYSTEM_ERROR"


class TestReadFile:
    """Tests for read_file capability."""

    @pytest.mark.asyncio
    async def test_read_file_success(self, tmp_path):
        """Test successful file read."""
        plugin = FilesystemPlugin()
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        result = await plugin.execute("read_file", {"path": str(test_file)})

        assert result.success is True
        assert result.data["content"] == "Hello, World!"
        assert result.data["size"] == 13

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, tmp_path):
        """Test read non-existent file."""
        plugin = FilesystemPlugin()

        result = await plugin.execute("read_file", {"path": str(tmp_path / "nonexistent.txt")})

        assert result.success is False
        assert result.error_code == "FILE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_read_directory_fails(self, tmp_path):
        """Test reading a directory fails."""
        plugin = FilesystemPlugin()

        result = await plugin.execute("read_file", {"path": str(tmp_path)})

        assert result.success is False
        assert result.error_code == "NOT_A_FILE"

    @pytest.mark.asyncio
    async def test_read_file_access_denied(self, tmp_path):
        """Test read file with access denied."""
        plugin = FilesystemPlugin(config={"allowed_paths": [str(tmp_path / "allowed")]})
        test_file = tmp_path / "forbidden" / "test.txt"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("secret")

        result = await plugin.execute("read_file", {"path": str(test_file)})

        assert result.success is False
        assert result.error_code == "ACCESS_DENIED"

    @pytest.mark.asyncio
    async def test_read_file_too_large(self, tmp_path):
        """Test read file that exceeds max size."""
        plugin = FilesystemPlugin()
        test_file = tmp_path / "large.txt"
        test_file.write_text("x" * 1000)

        result = await plugin.execute("read_file", {"path": str(test_file), "max_size": 100})

        assert result.success is False
        assert result.error_code == "FILE_TOO_LARGE"

    @pytest.mark.asyncio
    async def test_read_file_binary_decode_error(self, tmp_path):
        """Test read binary file with text encoding."""
        plugin = FilesystemPlugin()
        test_file = tmp_path / "binary.bin"
        test_file.write_bytes(b"\x00\x01\x02\xff\xfe")

        result = await plugin.execute("read_file", {"path": str(test_file)})

        assert result.success is False
        assert result.error_code == "DECODE_ERROR"


class TestWriteFile:
    """Tests for write_file capability."""

    @pytest.mark.asyncio
    async def test_write_file_success(self, tmp_path):
        """Test successful file write."""
        plugin = FilesystemPlugin()
        test_file = tmp_path / "output.txt"

        result = await plugin.execute(
            "write_file",
            {"path": str(test_file), "content": "Hello, World!"},
        )

        assert result.success is True
        assert result.data["action"] == "written"
        assert test_file.read_text() == "Hello, World!"

    @pytest.mark.asyncio
    async def test_write_file_access_denied(self, tmp_path):
        """Test write file with access denied."""
        plugin = FilesystemPlugin(config={"allowed_paths": [str(tmp_path / "allowed")]})

        result = await plugin.execute(
            "write_file",
            {"path": str(tmp_path / "forbidden.txt"), "content": "test"},
        )

        assert result.success is False
        assert result.error_code == "ACCESS_DENIED"

    @pytest.mark.asyncio
    async def test_write_file_parent_not_found(self, tmp_path):
        """Test write file when parent directory doesn't exist."""
        plugin = FilesystemPlugin()

        result = await plugin.execute(
            "write_file",
            {"path": str(tmp_path / "nonexistent" / "file.txt"), "content": "test"},
        )

        assert result.success is False
        assert result.error_code == "PARENT_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_write_file_create_dirs(self, tmp_path):
        """Test write file with create_dirs=True."""
        plugin = FilesystemPlugin()
        test_file = tmp_path / "nested" / "dirs" / "file.txt"

        result = await plugin.execute(
            "write_file",
            {"path": str(test_file), "content": "test", "create_dirs": True},
        )

        assert result.success is True
        assert test_file.exists()
        assert test_file.read_text() == "test"


class TestAppendFile:
    """Tests for append_file capability."""

    @pytest.mark.asyncio
    async def test_append_file_success(self, tmp_path):
        """Test successful file append."""
        plugin = FilesystemPlugin()
        test_file = tmp_path / "append.txt"
        test_file.write_text("Hello")

        result = await plugin.execute(
            "append_file",
            {"path": str(test_file), "content": ", World!"},
        )

        assert result.success is True
        assert result.data["action"] == "appended"
        assert test_file.read_text() == "Hello, World!"

    @pytest.mark.asyncio
    async def test_append_file_creates_new(self, tmp_path):
        """Test append creates file if it doesn't exist."""
        plugin = FilesystemPlugin()
        test_file = tmp_path / "new.txt"

        result = await plugin.execute(
            "append_file",
            {"path": str(test_file), "content": "New content"},
        )

        assert result.success is True
        assert test_file.read_text() == "New content"

    @pytest.mark.asyncio
    async def test_append_file_access_denied(self, tmp_path):
        """Test append file with access denied."""
        plugin = FilesystemPlugin(config={"allowed_paths": [str(tmp_path / "allowed")]})

        result = await plugin.execute(
            "append_file",
            {"path": str(tmp_path / "forbidden.txt"), "content": "test"},
        )

        assert result.success is False
        assert result.error_code == "ACCESS_DENIED"


class TestListDirectory:
    """Tests for list_directory capability."""

    @pytest.mark.asyncio
    async def test_list_directory_success(self, tmp_path):
        """Test successful directory listing."""
        plugin = FilesystemPlugin()
        (tmp_path / "file1.txt").write_text("test")
        (tmp_path / "file2.txt").write_text("test")
        (tmp_path / "subdir").mkdir()

        result = await plugin.execute("list_directory", {"path": str(tmp_path)})

        assert result.success is True
        assert result.data["count"] == 3
        names = [e["name"] for e in result.data["entries"]]
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "subdir" in names

    @pytest.mark.asyncio
    async def test_list_directory_not_found(self, tmp_path):
        """Test list non-existent directory."""
        plugin = FilesystemPlugin()

        result = await plugin.execute("list_directory", {"path": str(tmp_path / "nonexistent")})

        assert result.success is False
        assert result.error_code == "DIR_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_list_directory_not_a_dir(self, tmp_path):
        """Test list on a file fails."""
        plugin = FilesystemPlugin()
        test_file = tmp_path / "file.txt"
        test_file.write_text("test")

        result = await plugin.execute("list_directory", {"path": str(test_file)})

        assert result.success is False
        assert result.error_code == "NOT_A_DIRECTORY"

    @pytest.mark.asyncio
    async def test_list_directory_access_denied(self, tmp_path):
        """Test list directory with access denied."""
        plugin = FilesystemPlugin(config={"allowed_paths": [str(tmp_path / "allowed")]})

        result = await plugin.execute("list_directory", {"path": str(tmp_path)})

        assert result.success is False
        assert result.error_code == "ACCESS_DENIED"

    @pytest.mark.asyncio
    async def test_list_directory_with_pattern(self, tmp_path):
        """Test list directory with glob pattern."""
        plugin = FilesystemPlugin()
        (tmp_path / "file1.txt").write_text("test")
        (tmp_path / "file2.py").write_text("test")
        (tmp_path / "file3.txt").write_text("test")

        result = await plugin.execute(
            "list_directory",
            {"path": str(tmp_path), "pattern": "*.txt"},
        )

        assert result.success is True
        assert result.data["count"] == 2
        names = [e["name"] for e in result.data["entries"]]
        assert "file1.txt" in names
        assert "file3.txt" in names
        assert "file2.py" not in names

    @pytest.mark.asyncio
    async def test_list_directory_recursive(self, tmp_path):
        """Test recursive directory listing."""
        plugin = FilesystemPlugin()
        (tmp_path / "file1.txt").write_text("test")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "file2.txt").write_text("test")

        result = await plugin.execute(
            "list_directory",
            {"path": str(tmp_path), "recursive": True},
        )

        assert result.success is True
        names = [e["name"] for e in result.data["entries"]]
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "subdir" in names

    @pytest.mark.asyncio
    async def test_list_directory_recursive_with_pattern(self, tmp_path):
        """Test recursive directory listing with pattern."""
        plugin = FilesystemPlugin()
        (tmp_path / "file1.txt").write_text("test")
        (tmp_path / "file1.py").write_text("test")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "file2.txt").write_text("test")

        result = await plugin.execute(
            "list_directory",
            {"path": str(tmp_path), "pattern": "*.txt", "recursive": True},
        )

        assert result.success is True
        names = [e["name"] for e in result.data["entries"]]
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "file1.py" not in names

    @pytest.mark.asyncio
    async def test_list_directory_hidden_files(self, tmp_path):
        """Test hidden files are excluded by default."""
        plugin = FilesystemPlugin()
        (tmp_path / "visible.txt").write_text("test")
        (tmp_path / ".hidden.txt").write_text("test")

        result = await plugin.execute("list_directory", {"path": str(tmp_path)})

        assert result.success is True
        names = [e["name"] for e in result.data["entries"]]
        assert "visible.txt" in names
        assert ".hidden.txt" not in names

    @pytest.mark.asyncio
    async def test_list_directory_include_hidden(self, tmp_path):
        """Test hidden files are included when requested."""
        plugin = FilesystemPlugin()
        (tmp_path / "visible.txt").write_text("test")
        (tmp_path / ".hidden.txt").write_text("test")

        result = await plugin.execute(
            "list_directory",
            {"path": str(tmp_path), "include_hidden": True},
        )

        assert result.success is True
        names = [e["name"] for e in result.data["entries"]]
        assert "visible.txt" in names
        assert ".hidden.txt" in names

    @pytest.mark.asyncio
    async def test_list_directory_permission_error_handling(self, tmp_path):
        """Test directory listing handles permission errors on items."""
        plugin = FilesystemPlugin()
        test_file = tmp_path / "accessible.txt"
        test_file.write_text("test")

        # Mock Path.stat to raise PermissionError for specific file
        original_stat = Path.stat

        def mock_stat(self, *args, **kwargs):
            if "accessible" in str(self):
                raise PermissionError("access denied")
            return original_stat(self, *args, **kwargs)

        with patch.object(Path, "stat", mock_stat):
            result = await plugin.execute("list_directory", {"path": str(tmp_path)})

        assert result.success is True
        # Should still have entries, but with error info
        entries_with_error = [e for e in result.data["entries"] if "error" in e]
        assert len(entries_with_error) > 0


class TestFileInfo:
    """Tests for file_info capability."""

    @pytest.mark.asyncio
    async def test_file_info_success(self, tmp_path):
        """Test successful file info."""
        plugin = FilesystemPlugin()
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello")

        result = await plugin.execute("file_info", {"path": str(test_file)})

        assert result.success is True
        assert result.data["name"] == "test.txt"
        assert result.data["type"] == "file"
        assert result.data["size"] == 5
        assert "permissions" in result.data
        assert "modified" in result.data

    @pytest.mark.asyncio
    async def test_file_info_directory(self, tmp_path):
        """Test file info for directory."""
        plugin = FilesystemPlugin()

        result = await plugin.execute("file_info", {"path": str(tmp_path)})

        assert result.success is True
        assert result.data["type"] == "directory"

    @pytest.mark.asyncio
    async def test_file_info_not_found(self, tmp_path):
        """Test file info for non-existent path."""
        plugin = FilesystemPlugin()

        result = await plugin.execute("file_info", {"path": str(tmp_path / "nonexistent")})

        assert result.success is False
        assert result.error_code == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_file_info_access_denied(self, tmp_path):
        """Test file info with access denied."""
        plugin = FilesystemPlugin(config={"allowed_paths": [str(tmp_path / "allowed")]})
        test_file = tmp_path / "forbidden.txt"
        test_file.write_text("test")

        result = await plugin.execute("file_info", {"path": str(test_file)})

        assert result.success is False
        assert result.error_code == "ACCESS_DENIED"

    @pytest.mark.asyncio
    async def test_file_info_symlink(self, tmp_path):
        """Test file info for symlink.

        Note: The current implementation resolves paths, so symlinks
        are followed and the target's info is returned. The 'symlink'
        type detection only works for paths that remain symlinks after
        resolve() (which doesn't happen for valid symlinks).
        """
        plugin = FilesystemPlugin()
        target = tmp_path / "target.txt"
        target.write_text("test")
        link = tmp_path / "link.txt"
        link.symlink_to(target)

        result = await plugin.execute("file_info", {"path": str(link)})

        assert result.success is True
        # Due to path resolution, symlink is followed and target info is returned
        assert result.data["type"] == "file"
        assert result.data["size"] == 4  # "test" is 4 bytes


class TestDeleteFile:
    """Tests for delete_file capability."""

    @pytest.mark.asyncio
    async def test_delete_file_success(self, tmp_path):
        """Test successful file deletion."""
        plugin = FilesystemPlugin()
        test_file = tmp_path / "delete_me.txt"
        test_file.write_text("test")

        result = await plugin.execute("delete_file", {"path": str(test_file)})

        assert result.success is True
        assert result.data["action"] == "deleted"
        assert not test_file.exists()

    @pytest.mark.asyncio
    async def test_delete_empty_directory(self, tmp_path):
        """Test delete empty directory."""
        plugin = FilesystemPlugin()
        empty_dir = tmp_path / "empty_dir"
        empty_dir.mkdir()

        result = await plugin.execute("delete_file", {"path": str(empty_dir)})

        assert result.success is True
        assert not empty_dir.exists()

    @pytest.mark.asyncio
    async def test_delete_non_empty_directory(self, tmp_path):
        """Test delete non-empty directory fails."""
        plugin = FilesystemPlugin()
        non_empty = tmp_path / "non_empty"
        non_empty.mkdir()
        (non_empty / "file.txt").write_text("test")

        result = await plugin.execute("delete_file", {"path": str(non_empty)})

        assert result.success is False
        assert result.error_code == "DIR_NOT_EMPTY"

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, tmp_path):
        """Test delete non-existent file."""
        plugin = FilesystemPlugin()

        result = await plugin.execute("delete_file", {"path": str(tmp_path / "nonexistent")})

        assert result.success is False
        assert result.error_code == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_delete_file_access_denied(self, tmp_path):
        """Test delete file with access denied."""
        plugin = FilesystemPlugin(config={"allowed_paths": [str(tmp_path / "allowed")]})
        test_file = tmp_path / "forbidden.txt"
        test_file.write_text("test")

        result = await plugin.execute("delete_file", {"path": str(test_file)})

        assert result.success is False
        assert result.error_code == "ACCESS_DENIED"


class TestCopyFile:
    """Tests for copy_file capability."""

    @pytest.mark.asyncio
    async def test_copy_file_success(self, tmp_path):
        """Test successful file copy."""
        plugin = FilesystemPlugin()
        source = tmp_path / "source.txt"
        source.write_text("Hello")
        dest = tmp_path / "dest.txt"

        result = await plugin.execute(
            "copy_file",
            {"source": str(source), "destination": str(dest)},
        )

        assert result.success is True
        assert result.data["action"] == "copied"
        assert dest.read_text() == "Hello"
        assert source.exists()  # Original still exists

    @pytest.mark.asyncio
    async def test_copy_file_source_not_found(self, tmp_path):
        """Test copy with non-existent source."""
        plugin = FilesystemPlugin()

        result = await plugin.execute(
            "copy_file",
            {"source": str(tmp_path / "nonexistent"), "destination": str(tmp_path / "dest")},
        )

        assert result.success is False
        assert result.error_code == "SOURCE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_copy_directory_fails(self, tmp_path):
        """Test copying a directory fails."""
        plugin = FilesystemPlugin()
        source_dir = tmp_path / "source_dir"
        source_dir.mkdir()

        result = await plugin.execute(
            "copy_file",
            {"source": str(source_dir), "destination": str(tmp_path / "dest")},
        )

        assert result.success is False
        assert result.error_code == "NOT_A_FILE"

    @pytest.mark.asyncio
    async def test_copy_file_access_denied(self, tmp_path):
        """Test copy file with access denied."""
        plugin = FilesystemPlugin(config={"allowed_paths": [str(tmp_path / "allowed")]})
        source = tmp_path / "source.txt"
        source.write_text("test")

        result = await plugin.execute(
            "copy_file",
            {"source": str(source), "destination": str(tmp_path / "dest.txt")},
        )

        assert result.success is False
        assert result.error_code == "ACCESS_DENIED"

    @pytest.mark.asyncio
    async def test_copy_file_destination_exists(self, tmp_path):
        """Test copy when destination exists."""
        plugin = FilesystemPlugin()
        source = tmp_path / "source.txt"
        source.write_text("source content")
        dest = tmp_path / "dest.txt"
        dest.write_text("existing")

        result = await plugin.execute(
            "copy_file",
            {"source": str(source), "destination": str(dest)},
        )

        assert result.success is False
        assert result.error_code == "DESTINATION_EXISTS"

    @pytest.mark.asyncio
    async def test_copy_file_overwrite(self, tmp_path):
        """Test copy with overwrite=True."""
        plugin = FilesystemPlugin()
        source = tmp_path / "source.txt"
        source.write_text("new content")
        dest = tmp_path / "dest.txt"
        dest.write_text("old content")

        result = await plugin.execute(
            "copy_file",
            {"source": str(source), "destination": str(dest), "overwrite": True},
        )

        assert result.success is True
        assert dest.read_text() == "new content"


class TestMoveFile:
    """Tests for move_file capability."""

    @pytest.mark.asyncio
    async def test_move_file_success(self, tmp_path):
        """Test successful file move."""
        plugin = FilesystemPlugin()
        source = tmp_path / "source.txt"
        source.write_text("Hello")
        dest = tmp_path / "dest.txt"

        result = await plugin.execute(
            "move_file",
            {"source": str(source), "destination": str(dest)},
        )

        assert result.success is True
        assert result.data["action"] == "moved"
        assert dest.read_text() == "Hello"
        assert not source.exists()  # Source should be gone

    @pytest.mark.asyncio
    async def test_move_file_source_not_found(self, tmp_path):
        """Test move with non-existent source."""
        plugin = FilesystemPlugin()

        result = await plugin.execute(
            "move_file",
            {"source": str(tmp_path / "nonexistent"), "destination": str(tmp_path / "dest")},
        )

        assert result.success is False
        assert result.error_code == "SOURCE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_move_file_access_denied(self, tmp_path):
        """Test move file with access denied."""
        plugin = FilesystemPlugin(config={"allowed_paths": [str(tmp_path / "allowed")]})
        source = tmp_path / "source.txt"
        source.write_text("test")

        result = await plugin.execute(
            "move_file",
            {"source": str(source), "destination": str(tmp_path / "dest.txt")},
        )

        assert result.success is False
        assert result.error_code == "ACCESS_DENIED"

    @pytest.mark.asyncio
    async def test_move_file_destination_exists(self, tmp_path):
        """Test move when destination exists."""
        plugin = FilesystemPlugin()
        source = tmp_path / "source.txt"
        source.write_text("source")
        dest = tmp_path / "dest.txt"
        dest.write_text("existing")

        result = await plugin.execute(
            "move_file",
            {"source": str(source), "destination": str(dest)},
        )

        assert result.success is False
        assert result.error_code == "DESTINATION_EXISTS"

    @pytest.mark.asyncio
    async def test_move_file_overwrite(self, tmp_path):
        """Test move with overwrite=True."""
        plugin = FilesystemPlugin()
        source = tmp_path / "source.txt"
        source.write_text("new content")
        dest = tmp_path / "dest.txt"
        dest.write_text("old content")

        result = await plugin.execute(
            "move_file",
            {"source": str(source), "destination": str(dest), "overwrite": True},
        )

        assert result.success is True
        assert dest.read_text() == "new content"
        assert not source.exists()


class TestCreateDirectory:
    """Tests for create_directory capability."""

    @pytest.mark.asyncio
    async def test_create_directory_success(self, tmp_path):
        """Test successful directory creation."""
        plugin = FilesystemPlugin()
        new_dir = tmp_path / "new_dir"

        result = await plugin.execute("create_directory", {"path": str(new_dir)})

        assert result.success is True
        assert result.data["action"] == "created"
        assert new_dir.is_dir()

    @pytest.mark.asyncio
    async def test_create_directory_with_parents(self, tmp_path):
        """Test create nested directories."""
        plugin = FilesystemPlugin()
        nested = tmp_path / "a" / "b" / "c"

        result = await plugin.execute(
            "create_directory",
            {"path": str(nested), "parents": True},
        )

        assert result.success is True
        assert nested.is_dir()

    @pytest.mark.asyncio
    async def test_create_directory_already_exists(self, tmp_path):
        """Test create directory that already exists."""
        plugin = FilesystemPlugin()
        existing = tmp_path / "existing"
        existing.mkdir()

        result = await plugin.execute("create_directory", {"path": str(existing)})

        assert result.success is True
        assert result.data["action"] == "already_exists"

    @pytest.mark.asyncio
    async def test_create_directory_path_is_file(self, tmp_path):
        """Test create directory when path is a file."""
        plugin = FilesystemPlugin()
        existing_file = tmp_path / "file.txt"
        existing_file.write_text("test")

        result = await plugin.execute("create_directory", {"path": str(existing_file)})

        assert result.success is False
        assert result.error_code == "NOT_A_DIRECTORY"

    @pytest.mark.asyncio
    async def test_create_directory_access_denied(self, tmp_path):
        """Test create directory with access denied."""
        plugin = FilesystemPlugin(config={"allowed_paths": [str(tmp_path / "allowed")]})

        result = await plugin.execute(
            "create_directory",
            {"path": str(tmp_path / "forbidden")},
        )

        assert result.success is False
        assert result.error_code == "ACCESS_DENIED"


class TestExists:
    """Tests for exists capability."""

    @pytest.mark.asyncio
    async def test_exists_file(self, tmp_path):
        """Test exists for file."""
        plugin = FilesystemPlugin()
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        result = await plugin.execute("exists", {"path": str(test_file)})

        assert result.success is True
        assert result.data["exists"] is True
        assert result.data["is_file"] is True
        assert result.data["is_directory"] is False

    @pytest.mark.asyncio
    async def test_exists_directory(self, tmp_path):
        """Test exists for directory."""
        plugin = FilesystemPlugin()

        result = await plugin.execute("exists", {"path": str(tmp_path)})

        assert result.success is True
        assert result.data["exists"] is True
        assert result.data["is_file"] is False
        assert result.data["is_directory"] is True

    @pytest.mark.asyncio
    async def test_exists_not_found(self, tmp_path):
        """Test exists for non-existent path."""
        plugin = FilesystemPlugin()

        result = await plugin.execute("exists", {"path": str(tmp_path / "nonexistent")})

        assert result.success is True
        assert result.data["exists"] is False
        assert result.data["is_file"] is None
        assert result.data["is_directory"] is None
