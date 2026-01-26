"""Shared SSH client library for Mother AI OS and ContentCraft.

This module provides reusable SSH connection management, file operations,
and VM configuration loading for accessing remote virtual machines.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import paramiko
import yaml
from scp import SCPClient

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Result of a remote command execution."""

    stdout: str
    stderr: str
    exit_code: int
    success: bool

    @property
    def output(self) -> str:
        """Combined stdout and stderr."""
        if self.stderr:
            return f"{self.stdout}\n{self.stderr}".strip()
        return self.stdout


@dataclass
class FileInfo:
    """Information about a remote file."""

    name: str
    path: str
    size: int
    mtime: datetime
    is_dir: bool


@dataclass
class ProjectInfo:
    """Information about a project on a VM."""

    name: str
    path: str
    type: str  # web_app, python_package, nextjs_app, etc.
    description: str
    readme_path: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "path": self.path,
            "type": self.type,
            "description": self.description,
            "readme_path": self.readme_path,
        }


@dataclass
class VMConfig:
    """Configuration for a virtual machine."""

    name: str
    host: str
    user: str
    ssh_key_path: Path
    requires_passphrase: bool
    projects: list[ProjectInfo]
    port: int = 22

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "host": self.host,
            "user": self.user,
            "ssh_key_path": str(self.ssh_key_path),
            "requires_passphrase": self.requires_passphrase,
            "port": self.port,
            "projects": [p.to_dict() for p in self.projects],
        }


class SSHConnection:
    """Manages SSH connection to a virtual machine.

    Provides high-level operations for command execution and file operations.
    Handles connection pooling and automatic reconnection.
    """

    def __init__(self, config: VMConfig):
        """Initialize SSH connection.

        Args:
            config: VM configuration
        """
        self.config = config
        self._client: paramiko.SSHClient | None = None
        self._connected = False

    def connect(self) -> None:
        """Establish SSH connection to the VM.

        Raises:
            paramiko.SSHException: If connection fails
            FileNotFoundError: If SSH key file not found
        """
        if self._connected and self._client:
            # Test if connection is still alive
            try:
                self._client.exec_command("echo test", timeout=5)
                return  # Connection still alive
            except Exception:
                # Connection dead, reconnect
                self._connected = False
                self._client = None

        # Create new connection
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Resolve SSH key path
        ssh_key_path = self.config.ssh_key_path.expanduser()

        if not ssh_key_path.exists():
            raise FileNotFoundError(f"SSH key not found: {ssh_key_path}")

        try:
            # Try connecting using ssh-agent first (for passphrase-protected keys)
            client.connect(
                hostname=self.config.host,
                port=self.config.port,
                username=self.config.user,
                key_filename=str(ssh_key_path),
                timeout=10,
                look_for_keys=True,  # Use ssh-agent if available
                allow_agent=True,
            )
            self._client = client
            self._connected = True
            logger.info(f"Connected to VM '{self.config.name}' at {self.config.host}")

        except Exception as e:
            logger.error(f"Failed to connect to {self.config.name}: {e}")
            raise

    def disconnect(self) -> None:
        """Close SSH connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._connected = False
            logger.info(f"Disconnected from VM '{self.config.name}'")

    def run_command(self, command: str, timeout: int = 30) -> CommandResult:
        """Execute a command on the remote VM.

        Args:
            command: Command to execute
            timeout: Command timeout in seconds

        Returns:
            CommandResult with stdout, stderr, and exit code

        Raises:
            RuntimeError: If not connected
            paramiko.SSHException: If command execution fails
        """
        if not self._connected or not self._client:
            raise RuntimeError(f"Not connected to VM '{self.config.name}'")

        try:
            stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()

            result = CommandResult(
                stdout=stdout.read().decode("utf-8", errors="replace"),
                stderr=stderr.read().decode("utf-8", errors="replace"),
                exit_code=exit_code,
                success=exit_code == 0,
            )

            logger.debug(
                f"Command on {self.config.name}: {command[:50]}... -> exit_code={exit_code}"
            )
            return result

        except Exception as e:
            logger.error(f"Command execution failed on {self.config.name}: {e}")
            raise

    def read_file(self, remote_path: str, max_size: int = 1024 * 1024) -> str:
        """Read a file from the remote VM.

        Args:
            remote_path: Path to file on remote VM
            max_size: Maximum file size in bytes (default: 1MB)

        Returns:
            File contents as string

        Raises:
            RuntimeError: If not connected or file too large
            FileNotFoundError: If file doesn't exist
        """
        if not self._connected or not self._client:
            raise RuntimeError(f"Not connected to VM '{self.config.name}'")

        # Check file size first
        size_cmd = f"stat -c %s '{remote_path}' 2>/dev/null || echo -1"
        result = self.run_command(size_cmd, timeout=5)

        try:
            file_size = int(result.stdout.strip())
        except ValueError:
            raise FileNotFoundError(f"File not found: {remote_path}")

        if file_size < 0:
            raise FileNotFoundError(f"File not found: {remote_path}")

        if file_size > max_size:
            raise RuntimeError(
                f"File too large: {file_size} bytes (max: {max_size} bytes)"
            )

        # Read file content
        cat_cmd = f"cat '{remote_path}'"
        result = self.run_command(cat_cmd, timeout=30)

        if not result.success:
            raise RuntimeError(f"Failed to read file: {result.stderr}")

        logger.debug(f"Read {len(result.stdout)} bytes from {remote_path}")
        return result.stdout

    def list_directory(self, remote_path: str) -> list[FileInfo]:
        """List contents of a directory on the remote VM.

        Args:
            remote_path: Path to directory on remote VM

        Returns:
            List of FileInfo objects

        Raises:
            RuntimeError: If not connected or directory doesn't exist
        """
        if not self._connected or not self._client:
            raise RuntimeError(f"Not connected to VM '{self.config.name}'")

        # Use ls with detailed format
        # Format: permissions links owner group size month day time/year name
        ls_cmd = f"ls -la --time-style=+%s '{remote_path}' 2>/dev/null"
        result = self.run_command(ls_cmd, timeout=10)

        if not result.success:
            raise RuntimeError(f"Failed to list directory: {result.stderr}")

        files = []
        for line in result.stdout.strip().split("\n"):
            if not line or line.startswith("total"):
                continue

            parts = line.split()
            if len(parts) < 7:
                continue

            # Skip . and ..
            name = " ".join(parts[6:])
            if name in (".", ".."):
                continue

            permissions = parts[0]
            size = int(parts[4])
            mtime_timestamp = int(parts[5])
            is_dir = permissions.startswith("d")

            files.append(
                FileInfo(
                    name=name,
                    path=f"{remote_path.rstrip('/')}/{name}",
                    size=size,
                    mtime=datetime.fromtimestamp(mtime_timestamp),
                    is_dir=is_dir,
                )
            )

        logger.debug(f"Listed {len(files)} items in {remote_path}")
        return files

    def file_exists(self, remote_path: str) -> bool:
        """Check if a file exists on the remote VM.

        Args:
            remote_path: Path to check

        Returns:
            True if file exists, False otherwise
        """
        if not self._connected or not self._client:
            raise RuntimeError(f"Not connected to VM '{self.config.name}'")

        test_cmd = f"test -e '{remote_path}' && echo 1 || echo 0"
        result = self.run_command(test_cmd, timeout=5)
        return result.stdout.strip() == "1"

    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Download a file from the remote VM.

        Args:
            remote_path: Path on remote VM
            local_path: Local destination path

        Returns:
            True if successful

        Raises:
            RuntimeError: If not connected or download fails
        """
        if not self._connected or not self._client:
            raise RuntimeError(f"Not connected to VM '{self.config.name}'")

        try:
            with SCPClient(self._client.get_transport()) as scp:
                scp.get(remote_path, local_path)
            logger.info(f"Downloaded {remote_path} to {local_path}")
            return True

        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise RuntimeError(f"Failed to download file: {e}")

    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Upload a file to the remote VM.

        Args:
            local_path: Local file path
            remote_path: Destination path on remote VM

        Returns:
            True if successful

        Raises:
            RuntimeError: If not connected or upload fails
            FileNotFoundError: If local file doesn't exist
        """
        if not self._connected or not self._client:
            raise RuntimeError(f"Not connected to VM '{self.config.name}'")

        local_file = Path(local_path)
        if not local_file.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        try:
            with SCPClient(self._client.get_transport()) as scp:
                scp.put(local_path, remote_path)
            logger.info(f"Uploaded {local_path} to {remote_path}")
            return True

        except Exception as e:
            logger.error(f"Upload failed: {e}")
            raise RuntimeError(f"Failed to upload file: {e}")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


class VMRegistry:
    """Registry for managing VM configurations.

    Loads VM configurations from YAML file and provides lookup methods.
    """

    def __init__(self, vms: dict[str, VMConfig]):
        """Initialize registry.

        Args:
            vms: Dictionary mapping VM names to VMConfig objects
        """
        self._vms = vms

    @classmethod
    def load_from_yaml(cls, config_path: Path) -> "VMRegistry":
        """Load VM configurations from YAML file.

        Args:
            config_path: Path to vms.yaml configuration file

        Returns:
            VMRegistry instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        config_path = config_path.expanduser()

        if not config_path.exists():
            raise FileNotFoundError(f"VM configuration not found: {config_path}")

        try:
            with open(config_path) as f:
                data = yaml.safe_load(f)

            if not data or "vms" not in data:
                raise ValueError("Invalid configuration: missing 'vms' section")

            vms = {}
            for vm_name, vm_data in data["vms"].items():
                # Parse projects
                projects = []
                for proj_data in vm_data.get("projects", []):
                    projects.append(
                        ProjectInfo(
                            name=proj_data["name"],
                            path=proj_data["path"],
                            type=proj_data["type"],
                            description=proj_data["description"],
                            readme_path=proj_data["readme_path"],
                        )
                    )

                # Create VMConfig
                ssh_key_str = vm_data["ssh_key"]
                ssh_key_path = Path(ssh_key_str).expanduser()

                vms[vm_name] = VMConfig(
                    name=vm_name,
                    host=vm_data["host"],
                    user=vm_data["user"],
                    ssh_key_path=ssh_key_path,
                    requires_passphrase=vm_data.get("requires_passphrase", False),
                    projects=projects,
                    port=vm_data.get("port", 22),
                )

            logger.info(f"Loaded {len(vms)} VM configurations from {config_path}")
            return cls(vms)

        except Exception as e:
            logger.error(f"Failed to load VM configuration: {e}")
            raise ValueError(f"Failed to load VM configuration: {e}")

    def get_vm(self, name: str) -> VMConfig:
        """Get VM configuration by name.

        Args:
            name: VM name (e.g., 'projects', 'trading', 'uapk')

        Returns:
            VMConfig object

        Raises:
            KeyError: If VM not found
        """
        if name not in self._vms:
            available = ", ".join(self._vms.keys())
            raise KeyError(f"VM '{name}' not found. Available VMs: {available}")

        return self._vms[name]

    def get_all_vms(self) -> list[VMConfig]:
        """Get all VM configurations.

        Returns:
            List of VMConfig objects
        """
        return list(self._vms.values())

    def list_vm_names(self) -> list[str]:
        """Get list of VM names.

        Returns:
            List of VM names
        """
        return list(self._vms.keys())


class SSHConnectionPool:
    """Connection pool for managing SSH connections to multiple VMs.

    Maintains persistent connections and handles automatic reconnection.
    Thread-safe for concurrent access.
    """

    def __init__(self, registry: VMRegistry):
        """Initialize connection pool.

        Args:
            registry: VM registry with configurations
        """
        self.registry = registry
        self._connections: dict[str, SSHConnection] = {}
        self._lock = __import__("threading").Lock()

    def get_connection(self, vm_name: str) -> SSHConnection:
        """Get or create SSH connection to a VM.

        Args:
            vm_name: Name of the VM

        Returns:
            SSHConnection instance (connected)

        Raises:
            KeyError: If VM not found
            paramiko.SSHException: If connection fails
        """
        with self._lock:
            if vm_name not in self._connections:
                config = self.registry.get_vm(vm_name)
                conn = SSHConnection(config)
                self._connections[vm_name] = conn

            conn = self._connections[vm_name]

            # Ensure connection is active
            try:
                conn.connect()
            except Exception as e:
                # Remove dead connection from pool
                del self._connections[vm_name]
                raise

            return conn

    def close_all(self) -> None:
        """Close all connections in the pool."""
        with self._lock:
            for conn in self._connections.values():
                try:
                    conn.disconnect()
                except Exception as e:
                    logger.warning(f"Error closing connection: {e}")

            self._connections.clear()
            logger.info("All SSH connections closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close_all()
