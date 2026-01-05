---
sidebar_position: 2
---

# Python SDK

Use Mother AI OS programmatically in your Python applications.

## Installation

```bash
pip install mother-ai-os
```

## Quick Start

```python
from mother import MotherClient

# Initialize client
client = MotherClient(
    base_url="http://localhost:8080",
    api_key="your-api-key"
)

# Execute a command
result = client.command("List all Python files")
print(result.response)
```

## Async Support

```python
import asyncio
from mother import AsyncMotherClient

async def main():
    client = AsyncMotherClient(
        base_url="http://localhost:8080",
        api_key="your-api-key"
    )

    result = await client.command("Show disk usage")
    print(result.response)

asyncio.run(main())
```

## Streaming Responses

```python
async for event in client.command_stream("Analyze this directory"):
    if event.type == "thinking":
        print(f"Thinking: {event.content}")
    elif event.type == "tool_call":
        print(f"Executing: {event.plugin}.{event.capability}")
    elif event.type == "response":
        print(f"Result: {event.content}")
```

## Session Management

```python
# Create a session for multi-turn conversations
session = client.create_session()

# Commands share context within a session
session.command("Read config.yaml")
session.command("What does the database section say?")

# Clean up
session.close()
```

## Handling Confirmations

```python
result = client.command("Delete temp files")

if result.requires_confirmation:
    print(f"Action requires confirmation: {result.pending_action}")

    # Approve the action
    if input("Proceed? (y/n): ").lower() == "y":
        final_result = client.confirm(result.confirmation_id, approved=True)
```

## Error Handling

```python
from mother.exceptions import (
    MotherAPIError,
    AuthenticationError,
    PluginError
)

try:
    result = client.command("Do something")
except AuthenticationError:
    print("Invalid API key")
except PluginError as e:
    print(f"Plugin failed: {e.plugin_name} - {e.message}")
except MotherAPIError as e:
    print(f"API error: {e}")
```

## Direct Plugin Execution

```python
# Execute a specific plugin capability directly
result = client.execute_plugin(
    plugin="filesystem",
    capability="read_file",
    parameters={"path": "/path/to/file.txt"}
)

print(result.data["content"])
```
