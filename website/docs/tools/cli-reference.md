---
sidebar_position: 3
---

# CLI Reference

Complete reference for `mother tools` commands.

## Commands

### list

List tools.

```bash
mother tools list [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `--installed` | Show only installed tools |
| `--available` | Show available tools from catalog |
| `--enabled` | Show only enabled tools |
| `--disabled` | Show only disabled tools |
| `--json` | Output as JSON |

**Examples:**

```bash
# List all installed tools
mother tools list --installed

# List available tools in catalog
mother tools list --available

# JSON output for scripting
mother tools list --json
```

### status

Show detailed status of a tool.

```bash
mother tools status <name> [OPTIONS]
```

**Arguments:**
| Argument | Description |
|----------|-------------|
| `name` | Tool name |

**Options:**
| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |

**Example:**

```bash
mother tools status code-formatter
```

**Output:**

```
Tool: code-formatter
Version: 1.2.0
Status: installed, enabled
Risk Level: low
Integration: cli
Installed: 2024-01-15 10:30:00
Source: git:https://github.com/example/code-formatter
```

### install

Install a tool.

```bash
mother tools install <source> [OPTIONS]
```

**Arguments:**
| Argument | Description |
|----------|-------------|
| `source` | Installation source |

**Source Formats:**
- `local:/path/to/tool` - Local directory
- `git:https://github.com/user/repo` - Git repository
- `tool-name` - Catalog entry

**Options:**
| Option | Description |
|--------|-------------|
| `--enable` | Enable immediately after install |
| `--yes` | Skip confirmation prompts |
| `--json` | Output as JSON |

**Examples:**

```bash
# Install from catalog
mother tools install code-formatter

# Install from Git
mother tools install git:https://github.com/example/my-tool

# Install from local path
mother tools install local:./my-tool

# Install and enable immediately
mother tools install code-formatter --enable --yes
```

### uninstall

Uninstall a tool.

```bash
mother tools uninstall <name> [OPTIONS]
```

**Arguments:**
| Argument | Description |
|----------|-------------|
| `name` | Tool name |

**Options:**
| Option | Description |
|--------|-------------|
| `--yes` | Skip confirmation |
| `--json` | Output as JSON |

**Example:**

```bash
mother tools uninstall code-formatter --yes
```

### enable

Enable an installed tool.

```bash
mother tools enable <name>
```

**Arguments:**
| Argument | Description |
|----------|-------------|
| `name` | Tool name |

**Example:**

```bash
mother tools enable code-formatter
```

### disable

Disable an installed tool.

```bash
mother tools disable <name>
```

**Arguments:**
| Argument | Description |
|----------|-------------|
| `name` | Tool name |

**Example:**

```bash
mother tools disable code-formatter
```

### search

Search for tools in the catalog.

```bash
mother tools search <query> [OPTIONS]
```

**Arguments:**
| Argument | Description |
|----------|-------------|
| `query` | Search term |

**Options:**
| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |

**Example:**

```bash
mother tools search formatter
```

### health

Check tool health.

```bash
mother tools health <name> [OPTIONS]
```

**Arguments:**
| Argument | Description |
|----------|-------------|
| `name` | Tool name |

**Options:**
| Option | Description |
|--------|-------------|
| `--json` | Output as JSON |

**Example:**

```bash
mother tools health code-formatter
```

**Output:**

```
Tool: code-formatter
Binary: formatter
Status: healthy
Version: 1.2.0
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Tool not found |
| 3 | Tool not installed |
| 4 | Policy violation |
| 5 | Installation failed |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MOTHER_TOOLS_DIR` | Tool installation directory |
| `MOTHER_TOOL_POLICY` | Path to policy config |
| `MOTHER_NO_CONFIRM` | Skip confirmations (use with caution) |

## Configuration

### Tool Store Location

Tools are stored in `~/.local/share/mother/tools/`.

Structure:
```
~/.local/share/mother/tools/
  tools.json          # Installed tools database
  repos/              # Cloned repositories
    code-formatter/
    my-tool/
```

### Policy File

Create `mother_tool_policy.yaml` in project root or `~/.config/mother/`:

```yaml
enabled: true
default_action: confirm

risk_rules:
  low: allow
  medium: confirm
  high: confirm
  critical: deny

blocked_tools:
  - untrusted-tool

allowed_tools:
  - verified-tool
```
