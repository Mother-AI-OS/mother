---
sidebar_position: 3
---

# Security Model

Mother AI OS implements defense-in-depth security.

## Permission System

Every plugin capability declares required permissions:

```yaml
capabilities:
  - name: delete_file
    description: Delete a file
    confirmation_required: true  # Requires user confirmation
    permissions:
      - filesystem:write
```

## Confirmation Requirements

Destructive actions require explicit confirmation:

- File deletion
- Shell command execution
- Bulk modifications

The API returns a `pending_confirmation` that must be approved.

## Path Validation

All file paths are validated:
- No path traversal (`../`)
- Restricted to allowed directories
- Symlink resolution

## API Authentication

All requests require an API key:

```bash
curl -H "X-API-Key: your-secret-key" ...
```

## Best Practices

1. Use strong, unique API keys
2. Run behind a reverse proxy in production
3. Enable HTTPS
4. Limit network exposure
5. Review plugin permissions before installation
