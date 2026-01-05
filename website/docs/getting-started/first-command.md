---
sidebar_position: 3
---

# Your First Command

Let's send your first natural language command to Mother AI OS.

## Start the Server

First, make sure the server is running:

```bash
mother serve
```

## Send a Command

In another terminal, send a command using curl:

```bash
curl -X POST http://localhost:8080/command \
  -H "X-API-Key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"command": "List files in the current directory"}'
```

You'll receive a response like:

```json
{
  "success": true,
  "response": "Here are the files in the current directory:\n- README.md\n- setup.py\n- src/\n- tests/",
  "tool_calls": [
    {
      "tool": "filesystem",
      "args": {"path": "."},
      "success": true,
      "execution_time": 0.02
    }
  ]
}
```

## Try More Commands

Here are some example commands to try:

### File Operations

```bash
# Read a file
curl -X POST localhost:8080/command \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"command": "Show me the contents of README.md"}'

# Create a file
curl -X POST localhost:8080/command \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"command": "Create a file called notes.txt with the text Hello World"}'
```

### System Information

```bash
# Get system info
curl -X POST localhost:8080/command \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"command": "What is my current working directory?"}'

# Check disk usage
curl -X POST localhost:8080/command \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"command": "How much disk space is available?"}'
```

### Web Requests

```bash
# Fetch a webpage
curl -X POST localhost:8080/command \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"command": "Get the title of https://example.com"}'
```

## Using Python

You can also use Python to interact with Mother AI OS:

```python
import httpx

client = httpx.Client(
    base_url="http://localhost:8080",
    headers={"X-API-Key": "your-secret-key"}
)

response = client.post("/command", json={
    "command": "List Python files in the src directory"
})

result = response.json()
print(result["response"])
```

## Confirmation for Destructive Actions

Some actions (like deleting files or running shell commands) require confirmation:

```bash
curl -X POST localhost:8080/command \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"command": "Delete the file temp.txt"}'
```

Response:

```json
{
  "success": true,
  "response": "This action requires confirmation.",
  "pending_confirmation": {
    "id": "confirm-abc123",
    "tool_name": "filesystem",
    "command": "delete_file",
    "description": "Delete file: temp.txt"
  }
}
```

To confirm, send a confirmation request:

```bash
curl -X POST localhost:8080/command/{session_id}/confirm \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"confirmation_id": "confirm-abc123"}'
```

## Next Steps

Now that you've sent your first command, learn about:

- [How Mother AI OS Works](/docs/concepts/how-it-works)
- [The Plugin System](/docs/concepts/plugin-system)
- [Creating Your Own Plugins](/docs/plugins/creating-plugins)
