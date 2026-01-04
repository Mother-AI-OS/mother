"""Built-in filesystem plugin for Mother AI OS.

Provides file and directory operations with security controls.
"""

from __future__ import annotations

import shutil
import stat
from datetime import datetime
from pathlib import Path
from typing import Any

from ..base import PluginBase, PluginResult
from ..manifest import (
    CapabilitySpec,
    ExecutionSpec,
    ExecutionType,
    ParameterSpec,
    ParameterType,
    PluginManifest,
    PluginMetadata,
    PythonExecutionSpec,
)


def _create_manifest() -> PluginManifest:
    """Create the filesystem plugin manifest programmatically."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="filesystem",
            version="1.0.0",
            description="File and directory operations for Mother AI OS",
            author="Mother",
            license="MIT",
        ),
        capabilities=[
            # Read file
            CapabilitySpec(
                name="read_file",
                description="Read the contents of a file. Returns text content for text files.",
                parameters=[
                    ParameterSpec(
                        name="path",
                        type=ParameterType.STRING,
                        description="Path to the file to read",
                        required=True,
                    ),
                    ParameterSpec(
                        name="encoding",
                        type=ParameterType.STRING,
                        description="Text encoding (default: utf-8)",
                        required=False,
                        default="utf-8",
                    ),
                    ParameterSpec(
                        name="max_size",
                        type=ParameterType.INTEGER,
                        description="Maximum file size in bytes (default: 10MB)",
                        required=False,
                        default=10 * 1024 * 1024,
                    ),
                ],
            ),
            # Write file
            CapabilitySpec(
                name="write_file",
                description="Write content to a file. Creates the file if it doesn't exist, overwrites if it does.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="path",
                        type=ParameterType.STRING,
                        description="Path to the file to write",
                        required=True,
                    ),
                    ParameterSpec(
                        name="content",
                        type=ParameterType.STRING,
                        description="Content to write to the file",
                        required=True,
                    ),
                    ParameterSpec(
                        name="encoding",
                        type=ParameterType.STRING,
                        description="Text encoding (default: utf-8)",
                        required=False,
                        default="utf-8",
                    ),
                    ParameterSpec(
                        name="create_dirs",
                        type=ParameterType.BOOLEAN,
                        description="Create parent directories if they don't exist",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            # Append to file
            CapabilitySpec(
                name="append_file",
                description="Append content to the end of a file. Creates the file if it doesn't exist.",
                parameters=[
                    ParameterSpec(
                        name="path",
                        type=ParameterType.STRING,
                        description="Path to the file to append to",
                        required=True,
                    ),
                    ParameterSpec(
                        name="content",
                        type=ParameterType.STRING,
                        description="Content to append",
                        required=True,
                    ),
                    ParameterSpec(
                        name="encoding",
                        type=ParameterType.STRING,
                        description="Text encoding (default: utf-8)",
                        required=False,
                        default="utf-8",
                    ),
                ],
            ),
            # List directory
            CapabilitySpec(
                name="list_directory",
                description="List files and directories in a path. Returns names, types, and sizes.",
                parameters=[
                    ParameterSpec(
                        name="path",
                        type=ParameterType.STRING,
                        description="Directory path to list",
                        required=True,
                    ),
                    ParameterSpec(
                        name="pattern",
                        type=ParameterType.STRING,
                        description="Glob pattern to filter files (e.g., '*.txt')",
                        required=False,
                    ),
                    ParameterSpec(
                        name="include_hidden",
                        type=ParameterType.BOOLEAN,
                        description="Include hidden files (starting with .)",
                        required=False,
                        default=False,
                    ),
                    ParameterSpec(
                        name="recursive",
                        type=ParameterType.BOOLEAN,
                        description="List files recursively",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            # File info
            CapabilitySpec(
                name="file_info",
                description="Get detailed information about a file or directory (size, modified time, permissions).",
                parameters=[
                    ParameterSpec(
                        name="path",
                        type=ParameterType.STRING,
                        description="Path to the file or directory",
                        required=True,
                    ),
                ],
            ),
            # Delete file
            CapabilitySpec(
                name="delete_file",
                description="Delete a file or empty directory. Use with caution.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="path",
                        type=ParameterType.STRING,
                        description="Path to the file or directory to delete",
                        required=True,
                    ),
                ],
            ),
            # Copy file
            CapabilitySpec(
                name="copy_file",
                description="Copy a file to a new location.",
                parameters=[
                    ParameterSpec(
                        name="source",
                        type=ParameterType.STRING,
                        description="Source file path",
                        required=True,
                    ),
                    ParameterSpec(
                        name="destination",
                        type=ParameterType.STRING,
                        description="Destination path",
                        required=True,
                    ),
                    ParameterSpec(
                        name="overwrite",
                        type=ParameterType.BOOLEAN,
                        description="Overwrite if destination exists",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            # Move file
            CapabilitySpec(
                name="move_file",
                description="Move or rename a file or directory.",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="source",
                        type=ParameterType.STRING,
                        description="Source path",
                        required=True,
                    ),
                    ParameterSpec(
                        name="destination",
                        type=ParameterType.STRING,
                        description="Destination path",
                        required=True,
                    ),
                    ParameterSpec(
                        name="overwrite",
                        type=ParameterType.BOOLEAN,
                        description="Overwrite if destination exists",
                        required=False,
                        default=False,
                    ),
                ],
            ),
            # Create directory
            CapabilitySpec(
                name="create_directory",
                description="Create a new directory. Can create parent directories if needed.",
                parameters=[
                    ParameterSpec(
                        name="path",
                        type=ParameterType.STRING,
                        description="Path of the directory to create",
                        required=True,
                    ),
                    ParameterSpec(
                        name="parents",
                        type=ParameterType.BOOLEAN,
                        description="Create parent directories if they don't exist",
                        required=False,
                        default=True,
                    ),
                ],
            ),
            # File exists
            CapabilitySpec(
                name="exists",
                description="Check if a file or directory exists.",
                parameters=[
                    ParameterSpec(
                        name="path",
                        type=ParameterType.STRING,
                        description="Path to check",
                        required=True,
                    ),
                ],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.filesystem",
                **{"class": "FilesystemPlugin"},
            ),
        ),
        permissions=[
            "filesystem:read",
            "filesystem:write",
        ],
    )


class FilesystemPlugin(PluginBase):
    """Built-in plugin for file and directory operations."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the filesystem plugin."""
        super().__init__(_create_manifest(), config)

        # Security: restrict to certain paths if configured
        self._allowed_paths: list[Path] = []
        if config and "allowed_paths" in config:
            self._allowed_paths = [Path(p).resolve() for p in config["allowed_paths"]]

    def _check_path_allowed(self, path: Path) -> bool:
        """Check if a path is allowed based on security config."""
        if not self._allowed_paths:
            return True  # No restrictions

        resolved = path.resolve()
        return any(resolved == allowed or allowed in resolved.parents for allowed in self._allowed_paths)

    def _resolve_path(self, path_str: str) -> Path:
        """Resolve and expand a path string."""
        path = Path(path_str).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute a filesystem capability."""
        handlers = {
            "read_file": self._read_file,
            "write_file": self._write_file,
            "append_file": self._append_file,
            "list_directory": self._list_directory,
            "file_info": self._file_info,
            "delete_file": self._delete_file,
            "copy_file": self._copy_file,
            "move_file": self._move_file,
            "create_directory": self._create_directory,
            "exists": self._exists,
        }

        handler = handlers.get(capability)
        if not handler:
            return PluginResult.error_result(
                f"Unknown capability: {capability}",
                code="UNKNOWN_CAPABILITY",
            )

        try:
            return await handler(**params)
        except PermissionError as e:
            return PluginResult.error_result(
                f"Permission denied: {e}",
                code="PERMISSION_DENIED",
            )
        except FileNotFoundError as e:
            return PluginResult.error_result(
                f"File not found: {e}",
                code="FILE_NOT_FOUND",
            )
        except Exception as e:
            return PluginResult.error_result(
                f"Error: {e}",
                code="FILESYSTEM_ERROR",
            )

    async def _read_file(
        self,
        path: str,
        encoding: str = "utf-8",
        max_size: int = 10 * 1024 * 1024,
    ) -> PluginResult:
        """Read file contents."""
        file_path = self._resolve_path(path)

        if not file_path.exists():
            return PluginResult.error_result(
                f"File not found: {path}",
                code="FILE_NOT_FOUND",
            )

        if not file_path.is_file():
            return PluginResult.error_result(
                f"Path is not a file: {path}",
                code="NOT_A_FILE",
            )

        if not self._check_path_allowed(file_path):
            return PluginResult.error_result(
                f"Access denied to path: {path}",
                code="ACCESS_DENIED",
            )

        # Check file size
        size = file_path.stat().st_size
        if size > max_size:
            return PluginResult.error_result(
                f"File too large ({size} bytes, max {max_size})",
                code="FILE_TOO_LARGE",
            )

        try:
            content = file_path.read_text(encoding=encoding)
            return PluginResult.success_result(
                data={
                    "path": str(file_path),
                    "content": content,
                    "size": size,
                    "encoding": encoding,
                }
            )
        except UnicodeDecodeError:
            return PluginResult.error_result(
                f"Cannot decode file as {encoding} (may be binary)",
                code="DECODE_ERROR",
            )

    async def _write_file(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8",
        create_dirs: bool = False,
    ) -> PluginResult:
        """Write content to a file."""
        file_path = self._resolve_path(path)

        if not self._check_path_allowed(file_path):
            return PluginResult.error_result(
                f"Access denied to path: {path}",
                code="ACCESS_DENIED",
            )

        # Create parent directories if requested
        if create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)
        elif not file_path.parent.exists():
            return PluginResult.error_result(
                f"Parent directory does not exist: {file_path.parent}",
                code="PARENT_NOT_FOUND",
            )

        file_path.write_text(content, encoding=encoding)

        return PluginResult.success_result(
            data={
                "path": str(file_path),
                "size": len(content.encode(encoding)),
                "action": "written",
            }
        )

    async def _append_file(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8",
    ) -> PluginResult:
        """Append content to a file."""
        file_path = self._resolve_path(path)

        if not self._check_path_allowed(file_path):
            return PluginResult.error_result(
                f"Access denied to path: {path}",
                code="ACCESS_DENIED",
            )

        with open(file_path, "a", encoding=encoding) as f:
            f.write(content)

        return PluginResult.success_result(
            data={
                "path": str(file_path),
                "appended_size": len(content.encode(encoding)),
                "action": "appended",
            }
        )

    async def _list_directory(
        self,
        path: str,
        pattern: str | None = None,
        include_hidden: bool = False,
        recursive: bool = False,
    ) -> PluginResult:
        """List directory contents."""
        dir_path = self._resolve_path(path)

        if not dir_path.exists():
            return PluginResult.error_result(
                f"Directory not found: {path}",
                code="DIR_NOT_FOUND",
            )

        if not dir_path.is_dir():
            return PluginResult.error_result(
                f"Path is not a directory: {path}",
                code="NOT_A_DIRECTORY",
            )

        if not self._check_path_allowed(dir_path):
            return PluginResult.error_result(
                f"Access denied to path: {path}",
                code="ACCESS_DENIED",
            )

        entries = []

        if pattern:
            if recursive:
                items = dir_path.rglob(pattern)
            else:
                items = dir_path.glob(pattern)
        else:
            if recursive:
                items = dir_path.rglob("*")
            else:
                items = dir_path.iterdir()

        for item in items:
            # Skip hidden files unless requested
            if not include_hidden and item.name.startswith("."):
                continue

            try:
                stat_info = item.stat()
                entries.append(
                    {
                        "name": item.name,
                        "path": str(item),
                        "type": "directory" if item.is_dir() else "file",
                        "size": stat_info.st_size if item.is_file() else None,
                        "modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                    }
                )
            except (PermissionError, OSError):
                # Skip files we can't access
                entries.append(
                    {
                        "name": item.name,
                        "path": str(item),
                        "type": "unknown",
                        "error": "permission denied",
                    }
                )

        return PluginResult.success_result(
            data={
                "path": str(dir_path),
                "count": len(entries),
                "entries": sorted(entries, key=lambda x: (x["type"] != "directory", x["name"].lower())),
            }
        )

    async def _file_info(self, path: str) -> PluginResult:
        """Get file information."""
        file_path = self._resolve_path(path)

        if not file_path.exists():
            return PluginResult.error_result(
                f"Path not found: {path}",
                code="NOT_FOUND",
            )

        if not self._check_path_allowed(file_path):
            return PluginResult.error_result(
                f"Access denied to path: {path}",
                code="ACCESS_DENIED",
            )

        stat_info = file_path.stat()

        # Get permission string
        mode = stat_info.st_mode
        perms = stat.filemode(mode)

        info = {
            "path": str(file_path),
            "name": file_path.name,
            "type": "directory" if file_path.is_dir() else ("symlink" if file_path.is_symlink() else "file"),
            "size": stat_info.st_size,
            "created": datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
            "accessed": datetime.fromtimestamp(stat_info.st_atime).isoformat(),
            "permissions": perms,
            "owner_uid": stat_info.st_uid,
            "group_gid": stat_info.st_gid,
        }

        if file_path.is_symlink():
            info["symlink_target"] = str(file_path.readlink())

        return PluginResult.success_result(data=info)

    async def _delete_file(self, path: str) -> PluginResult:
        """Delete a file or empty directory."""
        file_path = self._resolve_path(path)

        if not file_path.exists():
            return PluginResult.error_result(
                f"Path not found: {path}",
                code="NOT_FOUND",
            )

        if not self._check_path_allowed(file_path):
            return PluginResult.error_result(
                f"Access denied to path: {path}",
                code="ACCESS_DENIED",
            )

        if file_path.is_dir():
            try:
                file_path.rmdir()
            except OSError as e:
                return PluginResult.error_result(
                    f"Cannot delete directory (not empty?): {e}",
                    code="DIR_NOT_EMPTY",
                )
        else:
            file_path.unlink()

        return PluginResult.success_result(
            data={
                "path": str(file_path),
                "action": "deleted",
            }
        )

    async def _copy_file(
        self,
        source: str,
        destination: str,
        overwrite: bool = False,
    ) -> PluginResult:
        """Copy a file."""
        src_path = self._resolve_path(source)
        dst_path = self._resolve_path(destination)

        if not src_path.exists():
            return PluginResult.error_result(
                f"Source not found: {source}",
                code="SOURCE_NOT_FOUND",
            )

        if not src_path.is_file():
            return PluginResult.error_result(
                f"Source is not a file: {source}",
                code="NOT_A_FILE",
            )

        if not self._check_path_allowed(src_path) or not self._check_path_allowed(dst_path):
            return PluginResult.error_result(
                "Access denied to source or destination path",
                code="ACCESS_DENIED",
            )

        if dst_path.exists() and not overwrite:
            return PluginResult.error_result(
                f"Destination already exists: {destination}",
                code="DESTINATION_EXISTS",
            )

        shutil.copy2(src_path, dst_path)

        return PluginResult.success_result(
            data={
                "source": str(src_path),
                "destination": str(dst_path),
                "action": "copied",
            }
        )

    async def _move_file(
        self,
        source: str,
        destination: str,
        overwrite: bool = False,
    ) -> PluginResult:
        """Move or rename a file."""
        src_path = self._resolve_path(source)
        dst_path = self._resolve_path(destination)

        if not src_path.exists():
            return PluginResult.error_result(
                f"Source not found: {source}",
                code="SOURCE_NOT_FOUND",
            )

        if not self._check_path_allowed(src_path) or not self._check_path_allowed(dst_path):
            return PluginResult.error_result(
                "Access denied to source or destination path",
                code="ACCESS_DENIED",
            )

        if dst_path.exists() and not overwrite:
            return PluginResult.error_result(
                f"Destination already exists: {destination}",
                code="DESTINATION_EXISTS",
            )

        shutil.move(str(src_path), str(dst_path))

        return PluginResult.success_result(
            data={
                "source": str(src_path),
                "destination": str(dst_path),
                "action": "moved",
            }
        )

    async def _create_directory(
        self,
        path: str,
        parents: bool = True,
    ) -> PluginResult:
        """Create a directory."""
        dir_path = self._resolve_path(path)

        if not self._check_path_allowed(dir_path):
            return PluginResult.error_result(
                f"Access denied to path: {path}",
                code="ACCESS_DENIED",
            )

        if dir_path.exists():
            if dir_path.is_dir():
                return PluginResult.success_result(
                    data={
                        "path": str(dir_path),
                        "action": "already_exists",
                    }
                )
            else:
                return PluginResult.error_result(
                    f"Path exists but is not a directory: {path}",
                    code="NOT_A_DIRECTORY",
                )

        dir_path.mkdir(parents=parents, exist_ok=True)

        return PluginResult.success_result(
            data={
                "path": str(dir_path),
                "action": "created",
            }
        )

    async def _exists(self, path: str) -> PluginResult:
        """Check if a path exists."""
        file_path = self._resolve_path(path)

        exists = file_path.exists()
        is_file = file_path.is_file() if exists else None
        is_dir = file_path.is_dir() if exists else None

        return PluginResult.success_result(
            data={
                "path": str(file_path),
                "exists": exists,
                "is_file": is_file,
                "is_directory": is_dir,
            }
        )


# Export the plugin class and manifest
__all__ = ["FilesystemPlugin", "_create_manifest"]
