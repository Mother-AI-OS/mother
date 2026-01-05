---
sidebar_position: 1
---

# REST API Endpoints

Mother AI OS provides a RESTful API for all operations.

## Base URL

```
http://localhost:8080
```

## Authentication

All requests require an API key:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8080/...
```

## Endpoints

### Health Check

```http
GET /health
```

Returns server status.

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

---

### Execute Command

```http
POST /command
```

Execute a natural language command.

**Request:**
```json
{
  "command": "List all Python files",
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "success": true,
  "response": "Found 5 Python files:\n- main.py\n- agent.py\n...",
  "session_id": "abc123",
  "tool_calls": [
    {
      "plugin": "filesystem",
      "capability": "list_directory",
      "parameters": {"path": "."}
    }
  ]
}
```

---

### Execute Command (Streaming)

```http
POST /command/stream
```

Stream the response as Server-Sent Events.

**Request:** Same as `/command`

**Response:** SSE stream with events:
- `thinking` - AI reasoning
- `tool_call` - Plugin execution
- `response` - Final response

---

### Confirm Action

```http
POST /confirm
```

Confirm a pending action (e.g., file deletion).

**Request:**
```json
{
  "confirmation_id": "conf-123",
  "approved": true
}
```

---

### List Plugins

```http
GET /plugins
```

Get all available plugins and their capabilities.

**Response:**
```json
{
  "plugins": [
    {
      "name": "filesystem",
      "description": "File and directory operations",
      "capabilities": ["read_file", "write_file", ...]
    }
  ]
}
```

---

### Session Management

```http
GET /sessions/{session_id}
DELETE /sessions/{session_id}
```

Retrieve or delete session state.

## Error Responses

All errors return:

```json
{
  "success": false,
  "error": "Error message",
  "error_code": "ERROR_CODE"
}
```

Common error codes:
- `UNAUTHORIZED` - Invalid API key
- `VALIDATION_ERROR` - Invalid request
- `PLUGIN_ERROR` - Plugin execution failed
- `CONFIRMATION_REQUIRED` - Action needs confirmation
