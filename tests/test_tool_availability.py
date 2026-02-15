"""Comprehensive tool availability test suite for Mother AI OS.

Verifies that all 16 builtin plugins (144 capabilities) and 8 external
tool repos are available end-to-end. Catches:
- Missing plugins or capabilities after code changes
- External CLIs that become unavailable
- Broken Anthropic tool schema generation
- Plugin registry gaps
- Catalog-vs-reality drift
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from mother.plugins.base import PluginBase, PluginResult, ResultStatus
from mother.plugins.builtin import (
    BUILTIN_PLUGINS,
    get_builtin_plugin,
    get_builtin_plugin_classes,
)

# ---------------------------------------------------------------------------
# Expected plugin capabilities — single source of truth for the test suite
# ---------------------------------------------------------------------------

EXPECTED_PLUGINS: dict[str, list[str]] = {
    "filesystem": [
        "read_file", "write_file", "append_file", "list_directory",
        "file_info", "delete_file", "copy_file", "move_file",
        "create_directory", "exists",
    ],
    "shell": [
        "run_command", "run_script", "get_env", "list_env", "which",
        "get_cwd", "hostname", "whoami", "command_exists", "system_info",
    ],
    "web": [
        "fetch", "get", "post", "head", "download", "check_url",
        "get_json", "extract_links", "parse_url", "encode_url",
    ],
    "email": [
        "list_accounts", "list_folders", "list_messages", "search_messages",
        "read_message", "send_message", "unread_count", "mark_message",
        "delete_message", "move_message",
    ],
    "pdf": [
        "merge", "split", "extract_pages", "info", "rotate",
        "delete_pages", "count_pages",
    ],
    "datacraft": [
        "process", "search", "tables", "get", "list", "stats",
        "graph", "delete",
    ],
    "tasks": [
        "focus", "top", "add", "list", "complete", "update",
        "delete", "get", "search", "stats", "areas",
    ],
    "transmit": [
        "email", "fax", "post", "bea", "channels", "history",
        "get", "stats",
    ],
    "taxlord": [
        "ingest", "search", "ask", "balance", "report", "documents",
        "ledgers", "elster_status", "vat", "sync",
    ],
    "leads": ["fetch", "list", "show", "analyze", "status"],
    "mailcraft": [
        "fetch", "list", "search", "read", "send", "categorize",
        "cleanup", "clean_spam", "batch_delete", "learn_from_trash",
        "semantic_search", "stats",
    ],
    "mattercraft": [
        "create", "list", "show", "search", "edit", "archive",
        "delete", "ingest", "query", "entities", "timeline",
        "tenders_list", "tenders_import",
    ],
    "google-docs": ["list", "get", "send", "status"],
    "tor": [
        "tor_check_status", "tor_fetch", "tor_browse", "tor_start",
        "tor_stop", "tor_new_identity", "tor_verified_sites",
        "darknet_bbc", "darknet_cia", "darknet_ddg",
    ],
    "tor-shell": [
        "darknet_dw", "darknet_voa", "darknet_rferl", "darknet_bellingcat",
        "darknet_propublica", "darknet_nyt", "darknet_bookmarks",
        "darknet_news",
    ],
    "ssh": [
        "connect", "run_command", "read_file", "list_directory",
        "download_file", "upload_file", "list_vms", "list_projects",
    ],
}

EXPECTED_TOTAL_CAPABILITIES = 144

# Capabilities that MUST require confirmation (destructive / side-effect ops)
DESTRUCTIVE_CAPABILITIES: list[tuple[str, str]] = [
    # filesystem
    ("filesystem", "write_file"),
    ("filesystem", "delete_file"),
    ("filesystem", "move_file"),
    # shell
    ("shell", "run_command"),
    ("shell", "run_script"),
    # web
    ("web", "post"),
    # email
    ("email", "send_message"),
    ("email", "delete_message"),
    # pdf
    ("pdf", "delete_pages"),
    # datacraft
    ("datacraft", "delete"),
    # tasks
    ("tasks", "delete"),
    # transmit (all sending channels)
    ("transmit", "email"),
    ("transmit", "fax"),
    ("transmit", "post"),
    ("transmit", "bea"),
    # mailcraft
    ("mailcraft", "send"),
    ("mailcraft", "cleanup"),
    ("mailcraft", "clean_spam"),
    ("mailcraft", "batch_delete"),
    # mattercraft
    ("mattercraft", "archive"),
    ("mattercraft", "delete"),
    ("mattercraft", "tenders_import"),
    # google-docs
    ("google-docs", "send"),
    # tor
    ("tor", "tor_start"),
    ("tor", "tor_stop"),
    # ssh
    ("ssh", "run_command"),
    ("ssh", "download_file"),
    ("ssh", "upload_file"),
]

# Capabilities that MUST NOT require confirmation (read-only / safe)
READ_ONLY_CAPABILITIES: list[tuple[str, str]] = [
    ("filesystem", "read_file"),
    ("filesystem", "exists"),
    ("filesystem", "file_info"),
    ("filesystem", "list_directory"),
    ("shell", "get_cwd"),
    ("shell", "whoami"),
    ("shell", "hostname"),
    ("shell", "which"),
    ("shell", "command_exists"),
    ("shell", "get_env"),
    ("shell", "list_env"),
    ("shell", "system_info"),
    ("web", "fetch"),
    ("web", "get"),
    ("web", "head"),
    ("web", "check_url"),
    ("web", "get_json"),
    ("web", "extract_links"),
    ("web", "parse_url"),
    ("web", "encode_url"),
    ("email", "list_accounts"),
    ("email", "list_folders"),
    ("email", "list_messages"),
    ("email", "read_message"),
    ("email", "unread_count"),
    ("pdf", "info"),
    ("pdf", "count_pages"),
    ("tasks", "list"),
    ("tasks", "stats"),
    ("tasks", "get"),
    ("tasks", "search"),
    ("tasks", "areas"),
    ("datacraft", "list"),
    ("datacraft", "stats"),
    ("datacraft", "search"),
    ("datacraft", "get"),
    ("transmit", "channels"),
    ("transmit", "history"),
    ("transmit", "get"),
    ("transmit", "stats"),
    ("leads", "list"),
    ("leads", "show"),
    ("leads", "status"),
    ("leads", "analyze"),
    ("mailcraft", "fetch"),
    ("mailcraft", "list"),
    ("mailcraft", "search"),
    ("mailcraft", "read"),
    ("mailcraft", "categorize"),
    ("mailcraft", "learn_from_trash"),
    ("mailcraft", "semantic_search"),
    ("mailcraft", "stats"),
    ("mattercraft", "create"),
    ("mattercraft", "list"),
    ("mattercraft", "show"),
    ("mattercraft", "search"),
    ("mattercraft", "edit"),
    ("mattercraft", "ingest"),
    ("mattercraft", "query"),
    ("mattercraft", "entities"),
    ("mattercraft", "timeline"),
    ("mattercraft", "tenders_list"),
    ("google-docs", "list"),
    ("google-docs", "get"),
    ("google-docs", "status"),
    ("tor", "tor_check_status"),
    ("tor", "tor_verified_sites"),
    ("tor-shell", "darknet_bookmarks"),
    ("tor-shell", "darknet_news"),
    ("ssh", "connect"),
    ("ssh", "list_vms"),
    ("ssh", "list_projects"),
    ("ssh", "read_file"),
    ("ssh", "list_directory"),
]

# External CLI tool binaries
EXTERNAL_CLI_TOOLS: dict[str, str] = {
    "leads": "leads",
    "taxlord": "taxlord",
    "mattercraft": "mattercraft",
    "mailcraft": "mailcraft",
    "gcp-draft": "gcp-draft",
    "datacraft": "datacraft",
    "contentcraft": "contentcraft",
}

# Tools catalog path
TOOLS_CATALOG_PATH = Path(__file__).parent.parent / "docs" / "ecosystem" / "tools-catalog.yaml"

CATALOG_TOOL_NAMES = [
    "contentcraft",
    "mailcraft",
    "datacraft",
    "leadengine",
    "lawkraft-transmit",
    "taxlord",
    "acnjxn",
    "helpers",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _instantiate_plugin(name: str) -> PluginBase:
    """Instantiate a builtin plugin by name with empty config."""
    cls = BUILTIN_PLUGINS[name]
    return cls(config={})


# =========================================================================
# 1. TestBuiltinPluginRegistry
# =========================================================================


class TestBuiltinPluginRegistry:
    """Verify all 16 plugins exist in BUILTIN_PLUGINS and can be instantiated."""

    def test_all_plugins_registered(self) -> None:
        """Assert exactly 16 plugins with expected names."""
        expected_names = set(EXPECTED_PLUGINS.keys())
        actual_names = set(BUILTIN_PLUGINS.keys())
        assert actual_names == expected_names, (
            f"Plugin registry mismatch.\n"
            f"  Missing: {expected_names - actual_names}\n"
            f"  Extra:   {actual_names - expected_names}"
        )
        assert len(BUILTIN_PLUGINS) == 16

    @pytest.mark.parametrize("plugin_name", sorted(EXPECTED_PLUGINS.keys()))
    def test_all_plugins_instantiate(self, plugin_name: str) -> None:
        """Each plugin can be instantiated with empty config."""
        plugin = _instantiate_plugin(plugin_name)
        assert isinstance(plugin, PluginBase)
        assert plugin.name == plugin_name

    @pytest.mark.parametrize("plugin_name", sorted(EXPECTED_PLUGINS.keys()))
    def test_get_builtin_plugin_lookup(self, plugin_name: str) -> None:
        """get_builtin_plugin(name) returns the correct class."""
        cls = get_builtin_plugin(plugin_name)
        assert cls is not None, f"get_builtin_plugin('{plugin_name}') returned None"
        assert cls is BUILTIN_PLUGINS[plugin_name]

    def test_get_builtin_plugin_unknown_returns_none(self) -> None:
        """Unknown plugin name returns None."""
        assert get_builtin_plugin("nonexistent-plugin") is None

    def test_get_builtin_plugin_classes_returns_copy(self) -> None:
        """get_builtin_plugin_classes returns a copy, not the original dict."""
        classes = get_builtin_plugin_classes()
        assert classes == BUILTIN_PLUGINS
        assert classes is not BUILTIN_PLUGINS


# =========================================================================
# 2. TestPluginCapabilities
# =========================================================================


class TestPluginCapabilities:
    """Verify each plugin exposes its expected capabilities."""

    @pytest.mark.parametrize(
        "plugin_name,expected_caps",
        sorted(EXPECTED_PLUGINS.items()),
        ids=sorted(EXPECTED_PLUGINS.keys()),
    )
    def test_plugin_capabilities(
        self, plugin_name: str, expected_caps: list[str]
    ) -> None:
        """Each plugin has the exact expected capabilities (name and count)."""
        plugin = _instantiate_plugin(plugin_name)
        actual_caps = [c.name for c in plugin.get_capabilities()]

        assert set(actual_caps) == set(expected_caps), (
            f"Plugin '{plugin_name}' capability mismatch.\n"
            f"  Missing: {set(expected_caps) - set(actual_caps)}\n"
            f"  Extra:   {set(actual_caps) - set(expected_caps)}"
        )
        assert len(actual_caps) == len(expected_caps), (
            f"Plugin '{plugin_name}' expected {len(expected_caps)} "
            f"capabilities, got {len(actual_caps)}"
        )

    def test_total_capability_count(self) -> None:
        """Sum of all capabilities should be exactly 144."""
        total = 0
        for plugin_name in EXPECTED_PLUGINS:
            plugin = _instantiate_plugin(plugin_name)
            total += len(plugin.get_capabilities())
        assert total == EXPECTED_TOTAL_CAPABILITIES, (
            f"Expected {EXPECTED_TOTAL_CAPABILITIES} total capabilities, got {total}"
        )

    @pytest.mark.parametrize("plugin_name", sorted(EXPECTED_PLUGINS.keys()))
    def test_no_duplicate_capability_names_within_plugin(
        self, plugin_name: str
    ) -> None:
        """Each plugin's capabilities have unique names."""
        plugin = _instantiate_plugin(plugin_name)
        names = [c.name for c in plugin.get_capabilities()]
        assert len(names) == len(set(names)), (
            f"Plugin '{plugin_name}' has duplicate capability names: "
            f"{[n for n in names if names.count(n) > 1]}"
        )


# =========================================================================
# 3. TestAnthropicSchemaGeneration
# =========================================================================


class TestAnthropicSchemaGeneration:
    """Verify every plugin generates valid Anthropic tool_use schemas."""

    @pytest.mark.parametrize("plugin_name", sorted(EXPECTED_PLUGINS.keys()))
    def test_all_plugins_generate_schemas(self, plugin_name: str) -> None:
        """get_anthropic_schemas() returns a non-empty list of dicts."""
        plugin = _instantiate_plugin(plugin_name)
        schemas = plugin.get_anthropic_schemas()
        assert isinstance(schemas, list)
        assert len(schemas) > 0
        for schema in schemas:
            assert isinstance(schema, dict)

    @pytest.mark.parametrize("plugin_name", sorted(EXPECTED_PLUGINS.keys()))
    def test_schema_structure(self, plugin_name: str) -> None:
        """Each schema has name, description, input_schema with type+properties."""
        plugin = _instantiate_plugin(plugin_name)
        for schema in plugin.get_anthropic_schemas():
            assert "name" in schema, f"Missing 'name' in schema: {schema}"
            assert "description" in schema, f"Missing 'description' in schema: {schema}"
            assert "input_schema" in schema, f"Missing 'input_schema' in schema: {schema}"

            input_schema = schema["input_schema"]
            assert input_schema.get("type") == "object", (
                f"input_schema.type should be 'object' for {schema['name']}"
            )
            assert "properties" in input_schema, (
                f"Missing 'properties' in input_schema for {schema['name']}"
            )

    @pytest.mark.parametrize("plugin_name", sorted(EXPECTED_PLUGINS.keys()))
    def test_schema_naming_convention(self, plugin_name: str) -> None:
        """Tool name matches {plugin_name}_{capability_name} pattern."""
        plugin = _instantiate_plugin(plugin_name)
        cap_names = [c.name for c in plugin.get_capabilities()]

        for schema in plugin.get_anthropic_schemas():
            tool_name: str = schema["name"]
            assert tool_name.startswith(f"{plugin_name}_"), (
                f"Schema name '{tool_name}' doesn't start with '{plugin_name}_'"
            )
            # Extract capability part after the plugin prefix
            cap_part = tool_name[len(plugin_name) + 1 :]
            assert cap_part in cap_names, (
                f"Schema name '{tool_name}' has capability '{cap_part}' "
                f"not found in plugin capabilities: {cap_names}"
            )

    def test_all_schemas_combined_no_name_collisions(self) -> None:
        """Collect all 144 schemas and verify no name collisions."""
        all_names: list[str] = []
        for plugin_name in EXPECTED_PLUGINS:
            plugin = _instantiate_plugin(plugin_name)
            for schema in plugin.get_anthropic_schemas():
                all_names.append(schema["name"])

        assert len(all_names) == EXPECTED_TOTAL_CAPABILITIES
        assert len(all_names) == len(set(all_names)), (
            f"Schema name collisions: "
            f"{[n for n in all_names if all_names.count(n) > 1]}"
        )

    @pytest.mark.parametrize("plugin_name", sorted(EXPECTED_PLUGINS.keys()))
    def test_required_params_present_in_schema(self, plugin_name: str) -> None:
        """Required params from CapabilitySpec appear in schema's required list."""
        plugin = _instantiate_plugin(plugin_name)
        for cap in plugin.get_capabilities():
            required_param_names = [p.name for p in cap.parameters if p.required]
            if not required_param_names:
                continue

            schema = cap.to_anthropic_schema(plugin_name)
            schema_required = schema.get("input_schema", {}).get("required", [])
            for param_name in required_param_names:
                assert param_name in schema_required, (
                    f"Required param '{param_name}' missing from schema "
                    f"'required' list for {plugin_name}.{cap.name}"
                )


# =========================================================================
# 4. TestConfirmationFlags
# =========================================================================


class TestConfirmationFlags:
    """Verify destructive capabilities require confirmation."""

    @pytest.mark.parametrize(
        "plugin_name,cap_name",
        DESTRUCTIVE_CAPABILITIES,
        ids=[f"{p}.{c}" for p, c in DESTRUCTIVE_CAPABILITIES],
    )
    def test_destructive_capabilities_require_confirmation(
        self, plugin_name: str, cap_name: str
    ) -> None:
        """Destructive capabilities MUST require confirmation."""
        plugin = _instantiate_plugin(plugin_name)
        cap = plugin.get_capability(cap_name)
        assert cap is not None, (
            f"Capability '{cap_name}' not found in plugin '{plugin_name}'"
        )
        assert cap.confirmation_required is True, (
            f"{plugin_name}.{cap_name} should require confirmation "
            f"(destructive operation)"
        )

    @pytest.mark.parametrize(
        "plugin_name,cap_name",
        READ_ONLY_CAPABILITIES,
        ids=[f"{p}.{c}" for p, c in READ_ONLY_CAPABILITIES],
    )
    def test_read_only_capabilities_no_confirmation(
        self, plugin_name: str, cap_name: str
    ) -> None:
        """Read-only capabilities MUST NOT require confirmation."""
        plugin = _instantiate_plugin(plugin_name)
        cap = plugin.get_capability(cap_name)
        assert cap is not None, (
            f"Capability '{cap_name}' not found in plugin '{plugin_name}'"
        )
        assert cap.confirmation_required is False, (
            f"{plugin_name}.{cap_name} should NOT require confirmation "
            f"(read-only operation)"
        )


# =========================================================================
# 5. TestExternalToolCLIs
# =========================================================================


class TestExternalToolCLIs:
    """Verify all external CLI tools that plugins depend on are installed."""

    @pytest.mark.parametrize(
        "tool_name,binary",
        sorted(EXTERNAL_CLI_TOOLS.items()),
        ids=sorted(EXTERNAL_CLI_TOOLS.keys()),
    )
    def test_cli_tool_available(self, tool_name: str, binary: str) -> None:
        """External CLI binary exists in PATH."""
        path = shutil.which(binary)
        assert path is not None, (
            f"CLI tool '{binary}' (for {tool_name}) not found in PATH. "
            f"Is it installed?"
        )

    # CLIs that don't support --help (e.g. interactive scripts)
    _NO_HELP_FLAG = {"gcp-draft"}

    @pytest.mark.parametrize(
        "tool_name,binary",
        sorted(EXTERNAL_CLI_TOOLS.items()),
        ids=sorted(EXTERNAL_CLI_TOOLS.keys()),
    )
    def test_cli_tools_respond_to_help(self, tool_name: str, binary: str) -> None:
        """Each CLI responds to --help without error."""
        import subprocess

        path = shutil.which(binary)
        if path is None:
            pytest.skip(f"CLI tool '{binary}' not available")
        if binary in self._NO_HELP_FLAG:
            pytest.skip(f"'{binary}' is interactive and doesn't support --help")

        result = subprocess.run(
            [binary, "--help"],
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"'{binary} --help' exited with code {result.returncode}.\n"
            f"stderr: {result.stderr.decode(errors='replace')[:500]}"
        )


# =========================================================================
# 6. TestToolsCatalog
# =========================================================================


class TestToolsCatalog:
    """Verify tools-catalog.yaml is complete and matches reality."""

    @pytest.fixture()
    def catalog(self) -> dict[str, Any]:
        """Load the tools catalog."""
        assert TOOLS_CATALOG_PATH.exists(), (
            f"Tools catalog not found at {TOOLS_CATALOG_PATH}"
        )
        with open(TOOLS_CATALOG_PATH) as f:
            return yaml.safe_load(f)

    def test_catalog_loads(self, catalog: dict[str, Any]) -> None:
        """YAML parses without error and has expected top-level keys."""
        assert "version" in catalog
        assert "tools" in catalog
        assert isinstance(catalog["tools"], list)

    def test_catalog_contains_all_known_tools(self, catalog: dict[str, Any]) -> None:
        """All 8 tool names are present."""
        tool_names = {t["name"] for t in catalog["tools"]}
        expected = set(CATALOG_TOOL_NAMES)
        assert expected == tool_names, (
            f"Catalog tool mismatch.\n"
            f"  Missing: {expected - tool_names}\n"
            f"  Extra:   {tool_names - expected}"
        )

    def test_catalog_entries_have_required_fields(
        self, catalog: dict[str, Any]
    ) -> None:
        """Each entry has name, description, repository, version, risk_level,
        integration_types."""
        required_fields = {
            "name", "description", "repository", "version",
            "risk_level", "integration_types",
        }
        for tool in catalog["tools"]:
            missing = required_fields - set(tool.keys())
            assert not missing, (
                f"Tool '{tool.get('name', '?')}' missing fields: {missing}"
            )

    def test_catalog_risk_levels_valid(self, catalog: dict[str, Any]) -> None:
        """Each risk_level is low/medium/high/critical."""
        valid_levels = {"low", "medium", "high", "critical"}
        for tool in catalog["tools"]:
            assert tool["risk_level"] in valid_levels, (
                f"Tool '{tool['name']}' has invalid risk_level: "
                f"'{tool['risk_level']}' (expected one of {valid_levels})"
            )

    def test_catalog_integration_types_valid(
        self, catalog: dict[str, Any]
    ) -> None:
        """Each integration type is cli/python/http/docker."""
        valid_types = {"cli", "python", "http", "docker"}
        for tool in catalog["tools"]:
            for itype in tool["integration_types"]:
                assert itype in valid_types, (
                    f"Tool '{tool['name']}' has invalid integration_type: "
                    f"'{itype}' (expected one of {valid_types})"
                )


# =========================================================================
# 7. TestPluginExecution
# =========================================================================


class TestPluginExecution:
    """Smoke tests for read-only capabilities (safe to run, no side effects)."""

    # -- filesystem --

    async def test_filesystem_exists(self, tmp_path: Path) -> None:
        """filesystem.exists works with a temp file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        plugin = _instantiate_plugin("filesystem")
        result = await plugin.execute("exists", {"path": str(test_file)})
        assert result.success is True
        assert result.data["exists"] is True
        assert result.data["is_file"] is True

    async def test_filesystem_read_file(self, tmp_path: Path) -> None:
        """filesystem.read_file reads a temp file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        plugin = _instantiate_plugin("filesystem")
        result = await plugin.execute("read_file", {"path": str(test_file)})
        assert result.success is True
        assert result.data["content"] == "hello world"

    # -- shell --

    async def test_shell_get_cwd(self) -> None:
        """shell.get_cwd returns a path."""
        plugin = _instantiate_plugin("shell")
        result = await plugin.execute("get_cwd", {})
        assert result.success is True
        assert "cwd" in result.data

    async def test_shell_which(self) -> None:
        """shell.which finds python3."""
        plugin = _instantiate_plugin("shell")
        result = await plugin.execute("which", {"command": "python3"})
        assert result.success is True
        assert result.data["found"] is True

    async def test_shell_hostname(self) -> None:
        """shell.hostname returns hostname."""
        plugin = _instantiate_plugin("shell")
        result = await plugin.execute("hostname", {})
        assert result.success is True
        assert "hostname" in result.data

    async def test_shell_whoami(self) -> None:
        """shell.whoami returns username."""
        plugin = _instantiate_plugin("shell")
        result = await plugin.execute("whoami", {})
        assert result.success is True
        assert "username" in result.data

    async def test_shell_system_info(self) -> None:
        """shell.system_info returns OS details."""
        plugin = _instantiate_plugin("shell")
        result = await plugin.execute("system_info", {})
        assert result.success is True
        assert "os" in result.data
        assert "architecture" in result.data

    # -- web --

    async def test_web_parse_url(self) -> None:
        """web.parse_url decomposes a URL."""
        plugin = _instantiate_plugin("web")
        result = await plugin.execute(
            "parse_url", {"url": "https://example.com/path?q=1"}
        )
        assert result.success is True
        assert result.data["scheme"] == "https"
        assert result.data["hostname"] == "example.com"
        assert result.data["path"] == "/path"

    async def test_web_encode_url(self) -> None:
        """web.encode_url builds encoded URL."""
        plugin = _instantiate_plugin("web")
        result = await plugin.execute(
            "encode_url",
            {"base_url": "https://example.com/search", "params": {"q": "hello world"}},
        )
        assert result.success is True
        assert "url" in result.data

    # -- tasks --

    async def test_tasks_list(self) -> None:
        """tasks.list executes without error."""
        plugin = _instantiate_plugin("tasks")
        result = await plugin.execute("list", {})
        # May succeed or fail depending on backend, but should not raise
        assert isinstance(result, PluginResult)

    async def test_tasks_stats(self) -> None:
        """tasks.stats executes without error."""
        plugin = _instantiate_plugin("tasks")
        result = await plugin.execute("stats", {})
        assert isinstance(result, PluginResult)

    # -- datacraft --

    async def test_datacraft_list(self) -> None:
        """datacraft.list executes without error."""
        plugin = _instantiate_plugin("datacraft")
        result = await plugin.execute("list", {})
        assert isinstance(result, PluginResult)

    async def test_datacraft_stats(self) -> None:
        """datacraft.stats executes without error."""
        plugin = _instantiate_plugin("datacraft")
        result = await plugin.execute("stats", {})
        assert isinstance(result, PluginResult)

    # -- transmit --

    async def test_transmit_channels(self) -> None:
        """transmit.channels executes without error."""
        plugin = _instantiate_plugin("transmit")
        result = await plugin.execute("channels", {})
        assert isinstance(result, PluginResult)

    async def test_transmit_stats(self) -> None:
        """transmit.stats executes without error."""
        plugin = _instantiate_plugin("transmit")
        result = await plugin.execute("stats", {})
        assert isinstance(result, PluginResult)

    # -- unknown capability --

    @pytest.mark.parametrize("plugin_name", sorted(EXPECTED_PLUGINS.keys()))
    async def test_unknown_capability_returns_error(
        self, plugin_name: str
    ) -> None:
        """All plugins return UNKNOWN_CAPABILITY for bogus capability names."""
        plugin = _instantiate_plugin(plugin_name)
        result = await plugin.execute("__nonexistent_capability__", {})
        assert result.success is False
        assert result.error_code == "UNKNOWN_CAPABILITY"

    # -- leads / taxlord (skipif not available) --

    async def test_leads_status(self) -> None:
        """leads.status executes (skipped if CLI unavailable)."""
        if shutil.which("leads") is None:
            pytest.skip("leads CLI not available")
        plugin = _instantiate_plugin("leads")
        result = await plugin.execute("status", {})
        assert isinstance(result, PluginResult)

    async def test_taxlord_elster_status(self) -> None:
        """taxlord.elster_status executes (skipped if CLI unavailable)."""
        if shutil.which("taxlord") is None:
            pytest.skip("taxlord CLI not available")
        plugin = _instantiate_plugin("taxlord")
        result = await plugin.execute("elster_status", {})
        assert isinstance(result, PluginResult)
