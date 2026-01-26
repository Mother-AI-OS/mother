"""Built-in SSH plugin for Mother AI OS.

Provides SSH access to remote VMs for command execution and file operations.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from mother.utils.ssh_client import SSHConnectionPool, VMRegistry

from ...base import PluginBase, PluginResult
from ...manifest import (
    CapabilitySpec,
    ExecutionSpec,
    ExecutionType,
    ParameterSpec,
    ParameterType,
    PluginManifest,
    PluginMetadata,
    PythonExecutionSpec,
)

logger = logging.getLogger(__name__)


def _create_manifest() -> PluginManifest:
    """Create the SSH plugin manifest programmatically."""
    return PluginManifest(
        schema_version="1.0",
        plugin=PluginMetadata(
            name="ssh",
            version="1.0.0",
            description="SSH access to remote VMs: execute commands, read files, transfer files",
            author="Mother",
            license="MIT",
        ),
        capabilities=[
            # Connect to VM
            CapabilitySpec(
                name="connect",
                description="Test SSH connection to a VM and get basic system info",
                parameters=[
                    ParameterSpec(
                        name="vm_name",
                        type=ParameterType.STRING,
                        description="VM name (projects, trading, or uapk)",
                        required=True,
                    ),
                ],
            ),
            # Run command
            CapabilitySpec(
                name="run_command",
                description="Execute a command on a remote VM",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="vm_name",
                        type=ParameterType.STRING,
                        description="VM name (projects, trading, or uapk)",
                        required=True,
                    ),
                    ParameterSpec(
                        name="command",
                        type=ParameterType.STRING,
                        description="Command to execute",
                        required=True,
                    ),
                    ParameterSpec(
                        name="timeout",
                        type=ParameterType.INTEGER,
                        description="Command timeout in seconds (default: 30)",
                        required=False,
                        default=30,
                    ),
                ],
            ),
            # Read file
            CapabilitySpec(
                name="read_file",
                description="Read a file from a remote VM",
                parameters=[
                    ParameterSpec(
                        name="vm_name",
                        type=ParameterType.STRING,
                        description="VM name (projects, trading, or uapk)",
                        required=True,
                    ),
                    ParameterSpec(
                        name="remote_path",
                        type=ParameterType.STRING,
                        description="Path to file on remote VM",
                        required=True,
                    ),
                    ParameterSpec(
                        name="max_size",
                        type=ParameterType.INTEGER,
                        description="Maximum file size in bytes (default: 1MB)",
                        required=False,
                        default=1024 * 1024,
                    ),
                ],
            ),
            # List directory
            CapabilitySpec(
                name="list_directory",
                description="List contents of a directory on a remote VM",
                parameters=[
                    ParameterSpec(
                        name="vm_name",
                        type=ParameterType.STRING,
                        description="VM name (projects, trading, or uapk)",
                        required=True,
                    ),
                    ParameterSpec(
                        name="remote_path",
                        type=ParameterType.STRING,
                        description="Path to directory on remote VM",
                        required=True,
                    ),
                ],
            ),
            # Download file
            CapabilitySpec(
                name="download_file",
                description="Download a file from a remote VM to local system",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="vm_name",
                        type=ParameterType.STRING,
                        description="VM name (projects, trading, or uapk)",
                        required=True,
                    ),
                    ParameterSpec(
                        name="remote_path",
                        type=ParameterType.STRING,
                        description="Path to file on remote VM",
                        required=True,
                    ),
                    ParameterSpec(
                        name="local_path",
                        type=ParameterType.STRING,
                        description="Local destination path",
                        required=True,
                    ),
                ],
            ),
            # Upload file
            CapabilitySpec(
                name="upload_file",
                description="Upload a file from local system to a remote VM",
                confirmation_required=True,
                parameters=[
                    ParameterSpec(
                        name="vm_name",
                        type=ParameterType.STRING,
                        description="VM name (projects, trading, or uapk)",
                        required=True,
                    ),
                    ParameterSpec(
                        name="local_path",
                        type=ParameterType.STRING,
                        description="Local file path",
                        required=True,
                    ),
                    ParameterSpec(
                        name="remote_path",
                        type=ParameterType.STRING,
                        description="Destination path on remote VM",
                        required=True,
                    ),
                ],
            ),
            # List VMs
            CapabilitySpec(
                name="list_vms",
                description="List all configured VMs and their connection status",
                parameters=[],
            ),
            # List projects
            CapabilitySpec(
                name="list_projects",
                description="List all projects on a specific VM",
                parameters=[
                    ParameterSpec(
                        name="vm_name",
                        type=ParameterType.STRING,
                        description="VM name (projects, trading, or uapk)",
                        required=True,
                    ),
                ],
            ),
        ],
        execution=ExecutionSpec(
            type=ExecutionType.PYTHON,
            python=PythonExecutionSpec(
                module="mother.plugins.builtin.ssh",
                **{"class": "SSHPlugin"},
            ),
        ),
        permissions=[],
    )


class SSHPlugin(PluginBase):
    """Built-in plugin for SSH access to remote VMs."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the SSH plugin."""
        super().__init__(_create_manifest(), config)

        # Load VM registry
        config_path = Path.home() / ".config/mother/vms.yaml"
        try:
            self.vm_registry = VMRegistry.load_from_yaml(config_path)
            self.connection_pool = SSHConnectionPool(self.vm_registry)
            logger.info(
                f"SSH plugin initialized with {len(self.vm_registry.list_vm_names())} VMs"
            )
        except Exception as e:
            logger.error(f"Failed to load VM configuration: {e}")
            self.vm_registry = None
            self.connection_pool = None

    async def execute(self, capability: str, params: dict[str, Any]) -> PluginResult:
        """Execute an SSH capability."""
        # Check if VM registry loaded
        if not self.vm_registry or not self.connection_pool:
            return PluginResult.error_result(
                "VM configuration not loaded. Check ~/.config/mother/vms.yaml",
                code="CONFIG_ERROR",
            )

        handlers = {
            "connect": self._connect,
            "run_command": self._run_command,
            "read_file": self._read_file,
            "list_directory": self._list_directory,
            "download_file": self._download_file,
            "upload_file": self._upload_file,
            "list_vms": self._list_vms,
            "list_projects": self._list_projects,
        }

        handler = handlers.get(capability)
        if not handler:
            return PluginResult.error_result(
                f"Unknown capability: {capability}",
                code="UNKNOWN_CAPABILITY",
            )

        try:
            return await handler(**params)
        except KeyError as e:
            return PluginResult.error_result(
                f"VM not found: {e}",
                code="VM_NOT_FOUND",
            )
        except FileNotFoundError as e:
            return PluginResult.error_result(
                f"File not found: {e}",
                code="FILE_NOT_FOUND",
            )
        except ConnectionError as e:
            return PluginResult.error_result(
                f"Connection failed: {e}",
                code="CONNECTION_ERROR",
            )
        except Exception as e:
            logger.exception(f"SSH operation failed: {e}")
            return PluginResult.error_result(
                f"SSH operation failed: {e}",
                code="SSH_ERROR",
            )

    async def _connect(self, vm_name: str) -> PluginResult:
        """Test connection to a VM."""
        conn = self.connection_pool.get_connection(vm_name)
        config = self.vm_registry.get_vm(vm_name)

        # Get system info
        result = conn.run_command("hostname && uptime", timeout=10)

        if not result.success:
            return PluginResult.error_result(
                f"Failed to get system info: {result.stderr}",
                code="COMMAND_ERROR",
            )

        return PluginResult.success_result(
            message=f"Connected to VM '{vm_name}' at {config.host}",
            data={
                "vm_name": vm_name,
                "host": config.host,
                "user": config.user,
                "connected": True,
                "system_info": result.stdout.strip(),
            },
        )

    async def _run_command(
        self, vm_name: str, command: str, timeout: int = 30
    ) -> PluginResult:
        """Execute a command on a VM."""
        conn = self.connection_pool.get_connection(vm_name)
        result = conn.run_command(command, timeout=timeout)

        return PluginResult.success_result(
            message=f"Command executed on '{vm_name}' with exit code {result.exit_code}",
            data={
                "vm_name": vm_name,
                "command": command,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
                "success": result.success,
            },
        )

    async def _read_file(
        self, vm_name: str, remote_path: str, max_size: int = 1024 * 1024
    ) -> PluginResult:
        """Read a file from a VM."""
        conn = self.connection_pool.get_connection(vm_name)
        content = conn.read_file(remote_path, max_size=max_size)

        return PluginResult.success_result(
            message=f"Read {len(content)} bytes from {remote_path} on '{vm_name}'",
            data={
                "vm_name": vm_name,
                "remote_path": remote_path,
                "content": content,
                "size": len(content),
            },
        )

    async def _list_directory(self, vm_name: str, remote_path: str) -> PluginResult:
        """List directory contents on a VM."""
        conn = self.connection_pool.get_connection(vm_name)
        files = conn.list_directory(remote_path)

        files_data = [
            {
                "name": f.name,
                "path": f.path,
                "size": f.size,
                "mtime": f.mtime.isoformat(),
                "is_dir": f.is_dir,
            }
            for f in files
        ]

        return PluginResult.success_result(
            message=f"Listed {len(files)} items in {remote_path} on '{vm_name}'",
            data={
                "vm_name": vm_name,
                "remote_path": remote_path,
                "files": files_data,
                "count": len(files),
            },
        )

    async def _download_file(
        self, vm_name: str, remote_path: str, local_path: str
    ) -> PluginResult:
        """Download a file from a VM."""
        conn = self.connection_pool.get_connection(vm_name)
        success = conn.download_file(remote_path, local_path)

        if not success:
            return PluginResult.error_result(
                "Download failed",
                code="DOWNLOAD_ERROR",
            )

        return PluginResult.success_result(
            message=f"Downloaded {remote_path} from '{vm_name}' to {local_path}",
            data={
                "vm_name": vm_name,
                "remote_path": remote_path,
                "local_path": local_path,
            },
        )

    async def _upload_file(
        self, vm_name: str, local_path: str, remote_path: str
    ) -> PluginResult:
        """Upload a file to a VM."""
        conn = self.connection_pool.get_connection(vm_name)
        success = conn.upload_file(local_path, remote_path)

        if not success:
            return PluginResult.error_result(
                "Upload failed",
                code="UPLOAD_ERROR",
            )

        return PluginResult.success_result(
            message=f"Uploaded {local_path} to {remote_path} on '{vm_name}'",
            data={
                "vm_name": vm_name,
                "local_path": local_path,
                "remote_path": remote_path,
            },
        )

    async def _list_vms(self) -> PluginResult:
        """List all configured VMs."""
        vms_data = []

        for vm in self.vm_registry.get_all_vms():
            # Try to connect and get status
            try:
                conn = self.connection_pool.get_connection(vm.name)
                connected = True
                status = "connected"
            except Exception as e:
                connected = False
                status = f"error: {str(e)[:50]}"

            vms_data.append(
                {
                    "name": vm.name,
                    "host": vm.host,
                    "user": vm.user,
                    "port": vm.port,
                    "requires_passphrase": vm.requires_passphrase,
                    "project_count": len(vm.projects),
                    "connected": connected,
                    "status": status,
                }
            )

        return PluginResult.success_result(
            message=f"Found {len(vms_data)} configured VMs",
            data={
                "vms": vms_data,
                "count": len(vms_data),
            },
        )

    async def _list_projects(self, vm_name: str) -> PluginResult:
        """List projects on a VM."""
        vm_config = self.vm_registry.get_vm(vm_name)
        projects_data = [p.to_dict() for p in vm_config.projects]

        return PluginResult.success_result(
            message=f"Found {len(projects_data)} projects on '{vm_name}'",
            data={
                "vm_name": vm_name,
                "host": vm_config.host,
                "projects": projects_data,
                "count": len(projects_data),
            },
        )

    def __del__(self):
        """Cleanup connections on plugin destruction."""
        if hasattr(self, "connection_pool") and self.connection_pool:
            try:
                self.connection_pool.close_all()
            except Exception:
                pass
