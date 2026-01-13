# Mother AI OS - Shippable & Portable Deployment Guide

This document covers installation, deployment, multi-key authentication, and rate limiting configuration for production environments.

## Table of Contents

1. [Installation Options](#installation-options)
2. [Instance Bundle Usage](#instance-bundle-usage)
3. [Authentication Modes](#authentication-modes)
4. [Multi-Key Setup & Rotation](#multi-key-setup--rotation)
5. [Rate Limiting Configuration](#rate-limiting-configuration)
6. [Production Readiness Checks](#production-readiness-checks)
7. [Configuration Export/Import](#configuration-exportimport)

---

## Installation Options

### Option 1: pipx (Recommended for CLI usage)

```bash
# Install with pipx for isolated environment
pipx install mother-ai

# Verify installation
mother --version

# Run setup wizard
mother setup
```

### Option 2: pip (For development or integration)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install from PyPI
pip install mother-ai

# Or install from source
git clone https://github.com/Mother-AI-OS/mother.git
cd mother
pip install -e .
```

### Option 3: Docker (Recommended for production)

```bash
# Pull the official image
docker pull mother-ai:latest

# Or build from source
docker build -t mother-ai:latest .

# Run with environment variables
docker run -d \
  --name mother \
  -p 8080:8080 \
  -e MOTHER_REQUIRE_AUTH=true \
  -e ANTHROPIC_API_KEY=your-key \
  -v mother_data:/app/data \
  mother-ai:latest
```

### Option 4: Docker Compose (Full stack)

```bash
# Generate deployment files
mother init ./my-instance

# Configure
cd my-instance
cp .env.example .env
# Edit .env with your settings

# Start
docker-compose up -d
```

---

## Instance Bundle Usage

The `mother init` command creates a portable deployment bundle with all necessary configuration files.

### Creating an Instance Bundle

```bash
# Create in current directory
mother init

# Create in specific directory
mother init ./my-mother-instance

# Create with specific options
mother init ./my-instance --no-docker  # Skip Docker files
mother init ./my-instance --no-policy  # Skip policy template
```

### Bundle Contents

```
my-mother-instance/
├── docker-compose.yml    # Docker Compose configuration
├── Dockerfile            # Container build instructions
├── .env.example          # Environment template (no secrets!)
├── config/
│   └── policy.yaml       # Security policy template
└── workspace/            # Sandboxed file operations directory
```

### Deploying the Bundle

```bash
cd my-mother-instance

# 1. Configure environment
cp .env.example .env
nano .env  # Add your API keys and settings

# 2. Initialize multi-key authentication
mother keys init
mother keys add admin-key --role admin
# Save the generated key securely!

# 3. Verify configuration
mother doctor

# 4. Start the server
docker-compose up -d
# Or without Docker:
mother serve
```

---

## Authentication Modes

Mother supports two authentication modes for backward compatibility.

### Legacy Single-Key Mode

The original authentication method using a single API key from environment variable.

```bash
# Set in environment
export MOTHER_API_KEY="your-secret-key"
export MOTHER_REQUIRE_AUTH=true

# Start server
mother serve
```

**Limitations:**
- No role-based access control
- No audit attribution
- Cannot revoke without restart
- All users share the same key

### Multi-Key Mode (Recommended)

SQLite-backed key management with roles, scopes, and audit attribution.

```bash
# Initialize key store
mother keys init

# Create keys with different roles
mother keys add admin-key --role admin
mother keys add operator-key --role operator
mother keys add readonly-key --role readonly

# Start server (automatically uses multi-key mode)
mother serve
```

**Features:**
- Role-based access control (admin/operator/readonly)
- Scope-based permissions
- Key rotation without downtime
- Full audit attribution
- Per-key rate limiting

### Mode Detection

Mother automatically detects which mode to use:

1. If `keys.db` exists and contains keys → Multi-key mode
2. If `MOTHER_API_KEY` is set → Legacy single-key mode
3. If `MOTHER_REQUIRE_AUTH=false` → No authentication (development only!)

---

## Multi-Key Setup & Rotation

### Initial Setup

```bash
# Initialize the key store (creates ~/.config/mother/keys.db)
mother keys init

# Create your first admin key
mother keys add my-admin --role admin
# Output:
# Created API key: my-admin
# Key: mk_a1b2c3d4e5f6...  <-- Save this securely!
# Role: admin
#
# IMPORTANT: Save this key now. It cannot be retrieved later.
```

### Role Definitions

| Role | Description | Default Scopes |
|------|-------------|----------------|
| `admin` | Full access to all capabilities | `*` (all) |
| `operator` | Can execute most operations | `filesystem:*`, `tasks:*`, `web:*`, `email:*` |
| `readonly` | Read-only access | `filesystem:read`, `tasks:read`, `web:read` |

### Creating Keys with Custom Scopes

```bash
# Create key with specific scopes
mother keys add file-reader \
  --role readonly \
  --scope filesystem:read \
  --scope tasks:read

# Create key with expiration
mother keys add temp-access \
  --role operator \
  --expires 30  # Expires in 30 days
```

### Managing Keys

```bash
# List all active keys
mother keys list

# List including revoked keys
mother keys list --all

# View key details
mother keys info my-admin

# Revoke a key (immediate, cannot be undone)
mother keys revoke compromised-key

# Rotate a key (revoke old, create new with same settings)
mother keys rotate my-admin
# New key is generated, old key is revoked

# Permanently delete a key record
mother keys delete old-key
```

### Key Rotation Best Practices

1. **Regular Rotation**: Rotate keys every 90 days
2. **Incident Response**: Immediately revoke compromised keys
3. **Zero-Downtime**: Use `rotate` command to create new key before revoking old
4. **Audit Trail**: All key operations are logged

```bash
# Rotation workflow
# 1. Rotate the key
mother keys rotate production-key
# Output: New key: mk_new123...

# 2. Update your application with new key

# 3. Verify new key works
curl -H "X-API-Key: mk_new123..." http://localhost:8080/health

# 4. Old key is already revoked
```

---

## Rate Limiting Configuration

Mother includes per-key rate limiting using a token bucket algorithm.

### Default Limits

| Role | Requests per Minute | Burst Multiplier |
|------|---------------------|------------------|
| `readonly` | 60 RPM | 1.5x (90 burst) |
| `operator` | 120 RPM | 1.5x (180 burst) |
| `admin` | 300 RPM | 1.5x (450 burst) |

### Configuration

Rate limiting is enabled by default. Configure via environment variables:

```bash
# Disable rate limiting (not recommended for production)
export MOTHER_RATE_LIMIT_ENABLED=false

# Custom limits (future enhancement)
# export MOTHER_RATE_LIMIT_DEFAULT_RPM=60
# export MOTHER_RATE_LIMIT_ADMIN_RPM=300
# export MOTHER_RATE_LIMIT_BURST_MULTIPLIER=1.5
```

### Exempt Paths

The following paths are exempt from rate limiting:
- `/health`
- `/status`
- `/docs`
- `/openapi.json`

### Rate Limit Headers

All responses include rate limit headers:

```
X-RateLimit-Limit: 60          # Requests allowed per minute
X-RateLimit-Remaining: 45      # Requests remaining
X-RateLimit-Reset: 1705152000  # Unix timestamp when limit resets
```

### 429 Response

When rate limited, the API returns:

```json
{
  "detail": "Rate limit exceeded. Please retry later.",
  "retry_after": "5"
}
```

Headers:
```
HTTP/1.1 429 Too Many Requests
Retry-After: 5
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
```

### Per-Key Isolation

Each API key has its own rate limit bucket. Key A being throttled does not affect Key B.

---

## Production Readiness Checks

The `mother doctor` command verifies your installation is production-ready.

### Running Doctor

```bash
# Basic check
mother doctor

# Verbose output with details
mother doctor -v

# JSON output for automation
mother doctor --json
```

### Check Categories

| Check | PASS | WARN | FAIL |
|-------|------|------|------|
| Authentication | Auth enabled + key configured | No legacy key | Auth disabled |
| Multi-Key Mode | Key store initialized with keys | Store empty | Store corrupted |
| LLM Provider | API key configured | Key seems short | No key |
| Safe Mode | Enabled | Disabled | - |
| Sandbox Mode | Enabled | Disabled | - |
| Audit Logging | Enabled + writable | Disabled | Not writable |
| Policy File | Valid YAML loaded | No custom policy | Invalid YAML |
| Workspace Dir | Exists + writable | - | Not writable |
| Config Dir | Exists + readable | - | Not accessible |
| Rate Limiting | Enabled | Disabled | - |
| Database Integrity | All DBs pass check | - | Corruption detected |
| File Permissions | Secure (0600) | Loose permissions | - |
| Network Binding | Localhost only | All interfaces | - |

### Example Output

```
Mother Doctor - Production Readiness Check
==================================================
[PASS] Authentication: Legacy API key configured
[PASS] Multi-Key Mode: Multi-key store initialized (3 keys)
[PASS] LLM Provider: Provider 'anthropic' configured
[PASS] Safe Mode: Safe mode enabled
[PASS] Sandbox Mode: Sandbox mode enabled
[PASS] Audit Logging: Audit logging enabled
[WARN] Policy File: No custom policy file
[PASS] Workspace Directory: Workspace directory accessible
[PASS] Config Directory: Config directory accessible
[PASS] Rate Limiting: Rate limiting enabled
[PASS] Database Integrity: All databases healthy
[PASS] File Permissions: File permissions appropriate
[PASS] Network Binding: API bound to localhost only
==================================================
Summary: 12 passed, 1 warnings, 0 failures

System is production ready!
```

### Automation

```bash
# Use in CI/CD
mother doctor --json | jq '.summary.production_ready'
# Returns: true or false

# Exit code
mother doctor
echo $?  # 0 = ready, 1 = has failures
```

---

## Configuration Export/Import

Transfer configuration between Mother instances without exposing secrets.

### Export Configuration

```bash
# Export to default file
mother export

# Export to specific path
mother export -o backup.tar.gz

# Include API keys database (use with caution!)
mother export --include-keys -o full-backup.tar.gz
```

**Exported items:**
- `email_accounts.json` - Email account configurations
- `plugins.json` - Plugin settings
- `policy.yaml` - Security policy (if custom)
- `manifest.json` - Export metadata

**Never exported:**
- API keys (secrets)
- LLM provider API keys
- Credentials file

### Import Configuration

```bash
# Import configuration
mother import backup.tar.gz

# Force overwrite existing files
mother import backup.tar.gz --force

# JSON output
mother import backup.tar.gz --json
```

### Migration Workflow

```bash
# On source machine
mother export -o mother-config.tar.gz

# Transfer file to destination
scp mother-config.tar.gz user@newserver:~/

# On destination machine
mother import mother-config.tar.gz

# Recreate API keys (they don't transfer)
mother keys init
mother keys add admin --role admin

# Verify
mother doctor
```

---

## Security Checklist

Before deploying to production:

- [ ] Run `mother doctor` with no failures
- [ ] Enable authentication (`MOTHER_REQUIRE_AUTH=true`)
- [ ] Use multi-key mode for audit attribution
- [ ] Enable safe mode (`MOTHER_SAFE_MODE=true`)
- [ ] Enable sandbox mode (`MOTHER_SANDBOX_MODE=true`)
- [ ] Enable audit logging (`MOTHER_AUDIT_ENABLED=true`)
- [ ] Configure rate limiting (enabled by default)
- [ ] Bind to localhost unless external access needed
- [ ] Set file permissions to 0600 on sensitive files
- [ ] Rotate API keys regularly (every 90 days)
- [ ] Review custom policy.yaml if used
- [ ] Test 429 rate limiting behavior

---

## Troubleshooting

### Key Store Issues

```bash
# Check key store location
ls -la ~/.config/mother/keys.db

# Verify integrity
sqlite3 ~/.config/mother/keys.db "PRAGMA integrity_check;"

# Reset key store (WARNING: deletes all keys)
rm ~/.config/mother/keys.db
mother keys init
```

### Rate Limiting Issues

```bash
# Check current limits
curl -v http://localhost:8080/health
# Look for X-RateLimit-* headers

# Reset rate limit for a key (restart server)
# Or wait for token bucket to refill
```

### Authentication Failures

```bash
# Test legacy mode
curl -H "X-API-Key: $MOTHER_API_KEY" http://localhost:8080/health

# Test multi-key mode
curl -H "X-API-Key: mk_yourkey..." http://localhost:8080/health

# Check which mode is active
mother doctor -v | grep -A2 "Authentication"
```

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `MOTHER_REQUIRE_AUTH` | `true` | Enable authentication |
| `MOTHER_API_KEY` | - | Legacy single API key |
| `MOTHER_SAFE_MODE` | `true` | Restrict high-risk capabilities |
| `MOTHER_SANDBOX_MODE` | `true` | Sandbox file operations |
| `MOTHER_AUDIT_ENABLED` | `true` | Enable audit logging |
| `MOTHER_HOST` | `127.0.0.1` | API bind address |
| `MOTHER_PORT` | `8080` | API port |
| `MOTHER_CONFIG_DIR` | `~/.config/mother` | Configuration directory |
| `MOTHER_WORKSPACE_DIR` | `./workspace` | Sandboxed workspace |
| `MOTHER_AUDIT_LOG_PATH` | `./logs/audit.jsonl` | Audit log file |
| `MOTHER_POLICY_PATH` | - | Custom policy file path |
| `AI_PROVIDER` | `anthropic` | LLM provider |
| `ANTHROPIC_API_KEY` | - | Anthropic API key |
| `OPENAI_API_KEY` | - | OpenAI API key |

---

## Version History

- **v1.0.0** - Initial multi-key auth, rate limiting, doctor, init commands
