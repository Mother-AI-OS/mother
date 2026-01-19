# Implementation Plan: Tool Registry + Install Command

**Branch:** `feature/tools-registry`
**Date:** 2026-01-19

---

## Overview

This document describes the implementation plan for the Mother Tools Registry system, which enables users to discover, install, enable/disable, and uninstall external tool repos that integrate with Mother.

**Key distinction:**
- **Plugins** = capabilities loaded into Mother's runtime (existing system)
- **Tools** = external tool repos that can be installed/managed separately

A Tool *may* provide a Plugin, but tools are managed independently.

---

## Inspection Summary

### Existing Patterns to Follow

| Component | Location | Pattern |
|-----------|----------|---------|
| CLI | `mother/cli/__init__.py` | argparse with `subparsers.add_parser()` |
| Config | `mother/config/settings.py` | Pydantic `BaseSettings` with `~/.config/mother` |
| Data | `settings.log_dir` | `~/.local/share/mother/logs` |
| Audit | `mother/audit/logger.py` | `AuditEventType` enum, `AuditLogger.log()` |
| Policy | `mother/policy/engine.py` | `PolicyEngine.evaluate(capability, params, context)` |
| Plugin | `mother/plugins/__init__.py` | `PluginManager`, `PluginLoader`, `PluginRegistry` |

### Key Decisions

1. **Tool data location:** `~/.local/share/mother/tools/`
   - `tools.json` - installed tools registry
   - `catalog.yaml` - known tools catalog (also in repo at `docs/ecosystem/tools-catalog.yaml`)

2. **Tool manifest:** `mother-tool.yaml` in tool repo root
   - Different from `mother-plugin.yaml` (which is for plugin capabilities)
   - A tool can have both files

3. **Integration modes:** python, cli, http, docker (same as plugins)

4. **Tools disabled by default** - user must `mother tools enable <name>`

---

## File-by-File Plan

### New Modules

| File | Purpose |
|------|---------|
| `mother/tools/__init__.py` | Public exports for tools system |
| `mother/tools/manifest.py` | `ToolManifest` schema and validation |
| `mother/tools/store.py` | `ToolStore` for persistence (JSON) |
| `mother/tools/registry.py` | `ToolRegistry` core logic |
| `mother/tools/installer.py` | Install logic (local path, git, catalog) |
| `mother/tools/catalog.py` | Known tools catalog loader |
| `mother/tools/exceptions.py` | Tool-specific exceptions |
| `mother/cli/tools.py` | `mother tools` CLI commands |
| `docs/ecosystem/tools-catalog.yaml` | Known tools catalog |

### Modified Modules

| File | Change |
|------|--------|
| `mother/cli/__init__.py` | Add `tools` subparser |
| `mother/audit/logger.py` | Add `TOOL_*` event types |
| `mother/config/settings.py` | Add `tools_dir` path |

### Test Additions

| File | Purpose |
|------|---------|
| `tests/test_tools_manifest.py` | Manifest validation tests |
| `tests/test_tools_store.py` | Store persistence tests |
| `tests/test_tools_registry.py` | Registry logic tests |
| `tests/test_tools_installer.py` | Installer tests |
| `tests/test_cli_tools.py` | CLI command tests |
| `tests/fixtures/mother-tool.yaml` | Sample tool manifest |

---

## Module Interfaces

### 1. ToolManifest (`mother/tools/manifest.py`)

```python
@dataclass
class ToolManifest:
    schema_version: str  # "1.0"
    tool: ToolMetadata
    integration: IntegrationSpec
    permissions: list[str]
    config: list[ConfigField]

@dataclass
class ToolMetadata:
    name: str           # lowercase, alphanumeric, hyphens
    version: str        # semver
    description: str
    author: str
    homepage: str | None
    license: str | None
    risk_level: RiskLevel  # LOW, MEDIUM, HIGH, CRITICAL

@dataclass
class IntegrationSpec:
    type: IntegrationType  # python, cli, http, docker
    python: PythonIntegrationSpec | None
    cli: CLIIntegrationSpec | None
    http: HTTPIntegrationSpec | None
    docker: DockerIntegrationSpec | None

def load_tool_manifest(path: Path) -> ToolManifest: ...
def validate_tool_manifest(data: dict) -> ToolManifest: ...
```

### 2. ToolStore (`mother/tools/store.py`)

```python
@dataclass
class InstalledTool:
    name: str
    version: str
    source: str          # "local:/path", "git:url", "catalog:name"
    installed_at: datetime
    enabled: bool
    manifest_path: Path
    integration_type: str

class ToolStore:
    def __init__(self, store_path: Path): ...
    def list_tools(self) -> list[InstalledTool]: ...
    def get_tool(self, name: str) -> InstalledTool | None: ...
    def add_tool(self, tool: InstalledTool) -> None: ...
    def remove_tool(self, name: str) -> None: ...
    def enable_tool(self, name: str) -> None: ...
    def disable_tool(self, name: str) -> None: ...
    def save(self) -> None: ...
    def load(self) -> None: ...
```

### 3. ToolRegistry (`mother/tools/registry.py`)

```python
class ToolRegistry:
    def __init__(
        self,
        store: ToolStore,
        catalog: ToolCatalog,
        policy_engine: PolicyEngine | None = None,
        audit_logger: AuditLogger | None = None,
    ): ...

    async def install(
        self,
        source: str,
        confirm_high_risk: bool = False,
    ) -> InstalledTool: ...

    async def uninstall(self, name: str) -> None: ...

    def enable(self, name: str) -> None: ...
    def disable(self, name: str) -> None: ...

    def list_installed(self) -> list[InstalledTool]: ...
    def list_available(self) -> list[CatalogEntry]: ...

    def get_status(self, name: str) -> ToolStatus: ...
```

### 4. ToolCatalog (`mother/tools/catalog.py`)

```python
@dataclass
class CatalogEntry:
    name: str
    description: str
    repository: str      # git URL
    version: str         # latest known version
    risk_level: RiskLevel
    integration_types: list[str]
    homepage: str | None

class ToolCatalog:
    def __init__(self, catalog_path: Path | None = None): ...
    def load(self) -> None: ...
    def get_entry(self, name: str) -> CatalogEntry | None: ...
    def list_entries(self) -> list[CatalogEntry]: ...
    def search(self, query: str) -> list[CatalogEntry]: ...
```

### 5. CLI Commands (`mother/cli/tools.py`)

```
mother tools list                    # List installed + catalog
mother tools install <source>        # Install from local/git/catalog
mother tools uninstall <name>        # Remove tool
mother tools enable <name>           # Enable disabled tool
mother tools disable <name>          # Disable without uninstall
mother tools status <name>           # Show tool details
mother tools doctor                  # Check all tools health
```

---

## Commit Plan

### Commit 1: Manifest Schema + Validator + Fixtures

**Files:**
- `mother/tools/__init__.py` (minimal exports)
- `mother/tools/manifest.py`
- `mother/tools/exceptions.py`
- `tests/test_tools_manifest.py`
- `tests/fixtures/mother-tool.yaml`

**Scope:** Define `ToolManifest`, `ToolMetadata`, `IntegrationSpec` dataclasses. Implement `load_tool_manifest()` and `validate_tool_manifest()`. Add comprehensive tests.

### Commit 2: ToolStore + ToolRegistry Core

**Files:**
- `mother/tools/store.py`
- `mother/tools/registry.py`
- `mother/tools/catalog.py`
- `mother/config/settings.py` (add tools_dir)
- `docs/ecosystem/tools-catalog.yaml`
- `tests/test_tools_store.py`
- `tests/test_tools_registry.py`

**Scope:** Implement persistence layer and core registry operations. Create initial catalog with known tools from `ecosystem_scan.py`.

### Commit 3: CLI Commands

**Files:**
- `mother/cli/tools.py`
- `mother/cli/__init__.py` (add tools subparser)
- `tests/test_cli_tools.py`

**Scope:** Implement all `mother tools` commands with proper argument parsing, output formatting, and error handling.

### Commit 4: Policy + Audit Integration

**Files:**
- `mother/audit/logger.py` (add TOOL_* events)
- `mother/tools/registry.py` (wire policy/audit)
- `mother/tools/installer.py` (extract install logic)
- `tests/test_tools_installer.py`

**Scope:** Add audit events for tool operations. Wire policy checks for high-risk tool installs. Implement installer with local/git/catalog support.

### Commit 5: Docs + Examples + Polish

**Files:**
- `docs/ecosystem/TOOLS_REGISTRY.md`
- `docs/dev/PR_SUMMARY_TOOLS_REGISTRY.md`
- Update `README.md` with tools section
- Any final fixes from testing

**Scope:** Documentation, examples, final integration testing.

---

## Risk Analysis

| Risk | Mitigation |
|------|------------|
| Git clone security | Only clone from trusted sources, validate manifest before loading |
| Path traversal | Validate all paths, use `Path.resolve()`, reject `..` |
| Arbitrary code execution | Tools disabled by default, policy gate for high-risk |
| Breaking existing plugins | Tools system is parallel, doesn't modify plugin system |

---

## Testing Strategy

1. **Unit tests:** Each module has dedicated test file
2. **Integration tests:** CLI commands tested with temp directories
3. **Fixtures:** Sample manifests in `tests/fixtures/`
4. **Mocking:** Mock git operations, policy engine where needed

---

## Success Criteria

- [ ] `mother tools list` shows catalog + installed
- [ ] `mother tools install /path/to/tool` works for local
- [ ] `mother tools install contentcraft` works for catalog
- [ ] `mother tools enable/disable` toggles tool state
- [ ] `mother tools uninstall` removes tool
- [ ] `mother tools status` shows detailed info
- [ ] High-risk tools require confirmation
- [ ] All operations are audited
- [ ] Tests pass with >80% coverage for new code

---

*Plan created by Claude Opus 4.5 during tools registry implementation session.*
