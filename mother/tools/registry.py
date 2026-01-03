"""Tool registry for discovering and managing CLI wrappers.

This module bridges legacy ToolWrapper-based tools with the new plugin system.
Both systems work together, with plugins taking precedence for overlapping names.
"""

from typing import Any, Optional
from pathlib import Path
import logging

from .base import ToolWrapper
from .mailcraft import MailcraftTool
from .leads import LeadsTool
from .taxlord import TaxlordTool
from .gcp_draft import GCPDraftTool
from .acnjxn import AcnjxnWrapper
from .datacraft import DatacraftTool
from .pdf_merge import PDFMergeTool
from .transmit import TransmitTool
from ..config.settings import Settings

# Import plugin system (optional, for graceful degradation)
try:
    from ..plugins import PluginManager, PluginConfig, PluginResult
    PLUGINS_AVAILABLE = True
except ImportError:
    PLUGINS_AVAILABLE = False
    PluginManager = None
    PluginConfig = None

logger = logging.getLogger("mother.tools.registry")


class ToolRegistry:
    """Registry for managing CLI tool wrappers and plugins.

    This registry bridges legacy ToolWrapper-based tools with the new
    plugin system. Both systems work together:
    - Legacy tools: Hardcoded ToolWrapper classes
    - Plugins: Dynamically discovered via PluginManager

    For tool name resolution, plugins take precedence over legacy wrappers.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        plugin_config: Optional["PluginConfig"] = None,
        enable_plugins: bool = True,
    ):
        self.wrappers: dict[str, ToolWrapper] = {}
        self._settings = settings
        self._plugin_manager: Optional["PluginManager"] = None
        self._plugins_enabled = enable_plugins and PLUGINS_AVAILABLE

        # Load legacy tools
        self._load_tools()

        # Initialize plugin system
        if self._plugins_enabled:
            self._init_plugins(plugin_config)

    def _init_plugins(self, plugin_config: Optional["PluginConfig"] = None) -> None:
        """Initialize the plugin system.

        Args:
            plugin_config: Optional plugin configuration
        """
        if not PLUGINS_AVAILABLE:
            logger.warning("Plugin system not available (import failed)")
            return

        try:
            config = plugin_config or PluginConfig()
            self._plugin_manager = PluginManager(config)
            # Note: Full initialization (discover + load) happens in async initialize()
            logger.info("Plugin manager created (async initialization pending)")
        except Exception as e:
            logger.error(f"Failed to initialize plugin system: {e}")
            self._plugin_manager = None

    async def initialize_plugins(self) -> None:
        """Async initialization of the plugin system.

        Call this after creating the registry to discover and load plugins.
        """
        if self._plugin_manager is not None:
            try:
                await self._plugin_manager.initialize()
                logger.info(
                    f"Plugin system initialized: {len(self._plugin_manager)} capabilities"
                )
            except Exception as e:
                logger.error(f"Failed to initialize plugins: {e}")

    @property
    def plugin_manager(self) -> Optional["PluginManager"]:
        """Get the plugin manager instance."""
        return self._plugin_manager

    def _load_tools(self) -> None:
        """Load all configured tool wrappers."""
        if self._settings:
            self._load_from_settings()
        else:
            self._load_defaults()

    def _load_defaults(self) -> None:
        """Load tools with default paths."""
        home = Path.home()

        # Mailcraft
        mailcraft_bin = home / ".local" / "bin" / "mailcraft"
        if mailcraft_bin.exists():
            self.wrappers["mailcraft"] = MailcraftTool(binary=str(mailcraft_bin))

        # Leads
        leads_bin = home / ".local" / "bin" / "leads"
        if leads_bin.exists():
            self.wrappers["leads"] = LeadsTool(binary=str(leads_bin))

        # Taxlord
        taxlord_dir = home / "projects" / "taxlord"
        if taxlord_dir.exists():
            self.wrappers["taxlord"] = TaxlordTool(taxlord_dir=str(taxlord_dir))

        # GCP Draft
        gcp_draft_bin = home / ".local" / "bin" / "gcp-draft"
        if gcp_draft_bin.exists():
            self.wrappers["gcp_draft"] = GCPDraftTool(binary=str(gcp_draft_bin))

        # Acnjxn (Action Jackson)
        acnjxn_bin = home / ".local" / "bin" / "acnjxn"
        acnjxn_venv = home / "projects" / "acnjxn" / ".venv" / "bin" / "acnjxn"
        if acnjxn_bin.exists():
            self.wrappers["acnjxn"] = AcnjxnWrapper(acnjxn_bin=acnjxn_bin)
        elif acnjxn_venv.exists():
            self.wrappers["acnjxn"] = AcnjxnWrapper(acnjxn_bin=acnjxn_venv)

        # Datacraft (Document Processing)
        datacraft_bin = home / ".local" / "bin" / "datacraft"
        datacraft_dir = home / "projects" / "datacraft"
        if datacraft_bin.exists():
            self.wrappers["datacraft"] = DatacraftTool()
        elif datacraft_dir.exists():
            self.wrappers["datacraft"] = DatacraftTool(datacraft_path=str(datacraft_dir))

        # PDF Merge
        pdf_merge_bin = home / ".local" / "bin" / "pdf-merge"
        if pdf_merge_bin.exists():
            self.wrappers["pdf_merge"] = PDFMergeTool(binary=str(pdf_merge_bin))

        # Transmit (universal document transmission)
        transmit_bin = home / ".local" / "bin" / "transmit"
        if transmit_bin.exists():
            self.wrappers["transmit"] = TransmitTool(binary=str(transmit_bin))

    def _load_from_settings(self) -> None:
        """Load tools using settings configuration."""
        s = self._settings

        # Mailcraft
        if s.mailcraft_bin.exists():
            self.wrappers["mailcraft"] = MailcraftTool(
                binary=str(s.mailcraft_bin),
                password=s.mailcraft_password,
                timeout=s.tool_timeout,
            )

        # Leads
        if s.leads_bin.exists():
            self.wrappers["leads"] = LeadsTool(
                binary=str(s.leads_bin),
                timeout=s.tool_timeout,
            )

        # Taxlord
        if s.taxlord_dir.exists():
            self.wrappers["taxlord"] = TaxlordTool(
                taxlord_dir=str(s.taxlord_dir),
                timeout=s.tool_timeout,
            )

        # GCP Draft
        if s.gcp_draft_bin.exists():
            self.wrappers["gcp_draft"] = GCPDraftTool(
                binary=str(s.gcp_draft_bin),
                timeout=60,  # Shorter timeout for this simple tool
            )

        # Acnjxn (Action Jackson)
        acnjxn_bin = s.acnjxn_bin if hasattr(s, 'acnjxn_bin') else Path.home() / ".local" / "bin" / "acnjxn"
        acnjxn_venv = Path.home() / "projects" / "acnjxn" / ".venv" / "bin" / "acnjxn"
        if acnjxn_bin.exists():
            self.wrappers["acnjxn"] = AcnjxnWrapper(acnjxn_bin=acnjxn_bin)
        elif acnjxn_venv.exists():
            self.wrappers["acnjxn"] = AcnjxnWrapper(acnjxn_bin=acnjxn_venv)

        # Datacraft (Document Processing)
        datacraft_bin = Path.home() / ".local" / "bin" / "datacraft"
        datacraft_dir = Path.home() / "projects" / "datacraft"
        if datacraft_bin.exists():
            self.wrappers["datacraft"] = DatacraftTool(timeout=s.tool_timeout)
        elif datacraft_dir.exists():
            self.wrappers["datacraft"] = DatacraftTool(
                datacraft_path=str(datacraft_dir),
                timeout=s.tool_timeout,
            )

        # PDF Merge
        pdf_merge_bin = Path.home() / ".local" / "bin" / "pdf-merge"
        if pdf_merge_bin.exists():
            self.wrappers["pdf_merge"] = PDFMergeTool(
                binary=str(pdf_merge_bin),
                timeout=60,
            )

        # Transmit (universal document transmission)
        transmit_bin = Path.home() / ".local" / "bin" / "transmit"
        if transmit_bin.exists():
            self.wrappers["transmit"] = TransmitTool(
                binary=str(transmit_bin),
                timeout=120,
            )

    def get_wrapper(self, name: str) -> Optional[ToolWrapper]:
        """Get a tool wrapper by name."""
        return self.wrappers.get(name)

    def get_all_anthropic_schemas(self) -> list[dict]:
        """Get all tool schemas in Anthropic format.

        Combines schemas from both legacy tools and plugins.
        Plugin schemas take precedence (appear first).
        """
        schemas = []
        seen_names = set()

        # Plugin schemas first (higher priority)
        if self._plugin_manager is not None:
            for schema in self._plugin_manager.get_all_schemas():
                schemas.append(schema)
                seen_names.add(schema.get("name", ""))

        # Legacy tool schemas
        for wrapper in self.wrappers.values():
            for command in wrapper.get_commands():
                try:
                    schema = wrapper.get_anthropic_tool_schema(command)
                    # Skip if plugin already provides this capability
                    if schema.get("name", "") not in seen_names:
                        schemas.append(schema)
                except Exception:
                    # Skip commands that fail to generate schema
                    pass

        return schemas

    def list_tools(self) -> dict[str, dict]:
        """List all available tools with their info.

        Combines legacy tools and plugins.
        """
        result = {}

        # Legacy tools
        for name, wrapper in self.wrappers.items():
            result[name] = {
                "description": wrapper.description,
                "commands": list(wrapper.get_commands().keys()),
                "source": "legacy",
            }

        # Plugin tools
        if self._plugin_manager is not None:
            for name, info in self._plugin_manager.list_plugins().items():
                result[name] = {
                    "description": info.description,
                    "commands": info.capabilities,
                    "source": "plugin",
                    "version": info.version,
                    "author": info.author,
                }

        return result

    def get_tool_details(self, name: str) -> Optional[dict]:
        """Get detailed information about a tool."""
        wrapper = self.wrappers.get(name)
        if not wrapper:
            return None

        commands = {}
        for cmd_name, cmd_def in wrapper.get_commands().items():
            commands[cmd_name] = {
                "description": cmd_def.get("description", ""),
                "parameters": cmd_def.get("parameters", []),
                "confirmation_required": cmd_def.get("confirmation_required", False),
            }

        return {
            "name": name,
            "description": wrapper.description,
            "commands": commands,
        }

    def parse_tool_name(self, full_name: str) -> tuple[Optional[str], Optional[str]]:
        """Parse a full tool name into wrapper/plugin name and command/capability.

        Example: "mailcraft_list" -> ("mailcraft", "list")
        Example: "taxlord_elster_vat" -> ("taxlord", "elster.vat")

        Checks plugins first, then legacy wrappers.
        """
        # Check plugins first
        if self._plugin_manager is not None and full_name in self._plugin_manager:
            try:
                plugin_name, capability = self._plugin_manager.parse_capability_name(full_name)
                return plugin_name, capability
            except Exception:
                pass

        # Check legacy wrappers
        for wrapper_name in self.wrappers:
            if full_name.startswith(f"{wrapper_name}_"):
                command_part = full_name[len(wrapper_name) + 1:]
                # Handle nested commands (elster_vat -> elster.vat)
                wrapper = self.wrappers[wrapper_name]
                commands = wrapper.get_commands()

                # Try direct match first
                if command_part in commands:
                    return wrapper_name, command_part

                # Try converting underscores to dots
                dotted = command_part.replace("_", ".")
                if dotted in commands:
                    return wrapper_name, dotted

                # Try just the first part
                if command_part in commands:
                    return wrapper_name, command_part

        return None, None

    def is_plugin_capability(self, full_name: str) -> bool:
        """Check if a tool name refers to a plugin capability.

        Args:
            full_name: Full tool name (e.g., "mailcraft_send_email")

        Returns:
            True if this is a plugin capability
        """
        if self._plugin_manager is None:
            return False
        return full_name in self._plugin_manager

    async def execute_plugin(
        self,
        full_name: str,
        params: dict[str, Any],
    ) -> "PluginResult":
        """Execute a plugin capability.

        Args:
            full_name: Full capability name (e.g., "mailcraft_send_email")
            params: Parameters for the capability

        Returns:
            PluginResult with execution outcome

        Raises:
            ValueError: If plugins not available or capability not found
        """
        if self._plugin_manager is None:
            raise ValueError("Plugin system not available")

        return await self._plugin_manager.execute(full_name, params)

    def requires_confirmation(self, full_name: str) -> bool:
        """Check if a tool/capability requires user confirmation.

        Args:
            full_name: Full tool name

        Returns:
            True if confirmation is required
        """
        # Check plugins first
        if self._plugin_manager is not None and full_name in self._plugin_manager:
            return self._plugin_manager.requires_confirmation(full_name)

        # Check legacy wrappers
        wrapper_name, command = self.parse_tool_name(full_name)
        if wrapper_name and command:
            wrapper = self.wrappers.get(wrapper_name)
            if wrapper:
                commands = wrapper.get_commands()
                cmd_def = commands.get(command, {})
                return cmd_def.get("confirmation_required", False)

        return False
