---
sidebar_position: 1
---

# How Mother AI OS Works

Understanding the architecture and flow of Mother AI OS.

## Overview

Mother AI OS acts as an intelligent middleware between you and your system tools. When you send a natural language command, here's what happens:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   You       │ ──► │   Mother    │ ──► │   Claude    │ ──► │   Plugins   │
│ "List files"│     │   API       │     │   AI        │     │   Execute   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                    │                   │
                           └────────────────────┴───────────────────┘
                                         Response
```

## Request Flow

### 1. Command Reception

Your natural language command arrives at the Mother AI OS API:

```json
{
  "command": "Show me Python files larger than 100 lines"
}
```

### 2. AI Interpretation

Claude AI analyzes your request and determines:
- Which plugin(s) to use
- What parameters to pass
- The order of operations (for multi-step tasks)

### 3. Plugin Execution

Mother AI OS executes the selected plugin capabilities:

```python
# Claude decides to use filesystem plugin
await plugins.execute("filesystem_list_directory", {"path": "."})
# Then filters for Python files over 100 lines
```

### 4. Response Generation

Results are processed and returned in natural language:

```json
{
  "success": true,
  "response": "Found 3 Python files over 100 lines:\n- main.py (245 lines)\n- agent.py (189 lines)\n- plugins.py (312 lines)",
  "tool_calls": [...]
}
```

## Key Components

### Agent Core

The central orchestrator that:
- Manages conversation state
- Coordinates with Claude AI
- Dispatches to plugins
- Handles confirmations

### Plugin Manager

Discovers, loads, and manages plugins:
- Built-in plugins (filesystem, shell, web)
- User-installed plugins from PyPI
- Custom local plugins

### Security Layer

Validates all operations:
- Permission checking
- Path validation
- Confirmation requirements
- Rate limiting

## Multi-Step Operations

For complex tasks, Mother AI OS can chain multiple operations:

```
Command: "Find all TODO comments in Python files and save to report.txt"

Step 1: filesystem_list_directory(path=".", recursive=true)
Step 2: filesystem_read_file(path="file1.py")
Step 3: filesystem_read_file(path="file2.py")
...
Step N: filesystem_write_file(path="report.txt", content=todos)
```

## Session Management

Mother AI OS maintains session state:
- Conversation history
- Pending confirmations
- Execution context

Sessions can be:
- Ephemeral (default)
- Persistent (with memory enabled)

## Next Steps

- Learn about the [Plugin System](/docs/concepts/plugin-system)
- Understand the [Security Model](/docs/concepts/security)
