# Mother AI OS - Launch Readiness Checklist

This checklist provides verified commands and expected outputs for deploying Mother AI OS.

## Pre-Flight Checks

### 1. System Requirements

| Requirement | Command | Expected |
|-------------|---------|----------|
| Python 3.11+ | `python3 --version` | `Python 3.11.x` or higher |
| pip | `pip --version` | Any recent version |
| Docker (optional) | `docker --version` | `Docker version 20.x+` |

### 2. Verify Package Name

The correct PyPI package name is `mother-ai-os` (not `mother-ai`).

```bash
pip install mother-ai-os
```

---

## Installation Methods

### Method A: pip (Development)

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install from PyPI
pip install mother-ai-os

# Verify installation
mother --version
# Expected: mother 0.3.0
```

### Method B: pip (From Source)

```bash
# Clone repository
git clone https://github.com/Mother-AI-OS/mother.git
cd mother

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install from source
pip install .

# Verify
mother --version
# Expected: mother 0.3.0
```

### Method C: pipx (Isolated)

```bash
# Install with pipx
pipx install mother-ai-os

# Verify
mother --version
# Expected: mother 0.3.0
```

### Method D: Docker

```bash
# Build image
docker build -t mother-ai-os:latest .

# Run container
docker run -d \
  --name mother \
  -p 8080:8080 \
  -e MOTHER_REQUIRE_AUTH=true \
  -e MOTHER_API_KEY=your-secret-key \
  -e ANTHROPIC_API_KEY=your-anthropic-key \
  mother-ai-os:latest

# Verify health
curl http://localhost:8080/health
# Expected: {"status":"healthy",...}
```

### Method E: Docker Compose

```bash
# Use existing docker-compose.yml in repo
cp .env.example .env
# Edit .env with your API keys

docker compose up -d

# Verify
curl http://localhost:8080/health
```

---

## Post-Installation Setup

### 1. Initialize Multi-Key Authentication

```bash
# Initialize key store
mother keys init
# Expected: Key store initialized at ~/.config/mother/keys.db

# Create admin key
mother keys add my-admin --role admin
# Expected:
# Created API key: my-admin
# Key: mk_xxxxxxxxxxxxxxxx  <-- SAVE THIS!
# Role: admin
```

### 2. Run Production Readiness Check

```bash
mother doctor
# Expected output:
# [PASS] Authentication: ...
# [PASS] LLM Provider: ...
# [PASS] Safe Mode: ...
# ...
# Summary: X passed, Y warnings, 0 failures
```

### 3. Verify All Checks Pass

```bash
mother doctor --json | jq '.summary'
# Expected:
# {
#   "passed": 10+,
#   "warnings": 0-3,
#   "failures": 0,
#   "production_ready": true
# }
```

---

## Instance Bundle Deployment

### Generate Deployment Bundle

```bash
# Create bundle in new directory
mother init ./my-deployment

# Expected files:
# ./my-deployment/
# ├── docker-compose.yml
# ├── Dockerfile
# ├── .env.example
# └── config/
#     └── policy.yaml
```

### Deploy the Bundle

```bash
cd my-deployment

# Configure
cp .env.example .env
nano .env  # Add API keys

# Start
docker compose up -d

# Verify
curl http://localhost:8080/health
```

---

## CLI Command Reference

### Verified Commands

| Command | Purpose | Verified |
|---------|---------|----------|
| `mother --version` | Show version | ✅ |
| `mother serve` | Start API server | ✅ |
| `mother setup` | Interactive setup wizard | ✅ |
| `mother status` | Show system status | ✅ |
| `mother doctor` | Production readiness checks | ✅ |
| `mother doctor -v` | Verbose doctor output | ✅ |
| `mother doctor --json` | JSON doctor output | ✅ |
| `mother init` | Generate deployment bundle | ✅ |
| `mother init -o <dir>` | Specify output directory | ✅ |
| `mother init --no-docker` | Skip Docker files | ✅ |
| `mother init --no-policy` | Skip policy template | ✅ |
| `mother keys init` | Initialize key store | ✅ |
| `mother keys add <name>` | Create new API key | ✅ |
| `mother keys add <name> --role admin` | Create admin key | ✅ |
| `mother keys list` | List all keys | ✅ |
| `mother keys list --all` | Include revoked keys | ✅ |
| `mother keys info <id>` | Show key details | ✅ |
| `mother keys revoke <id>` | Revoke a key | ✅ |
| `mother keys rotate <id>` | Rotate a key | ✅ |
| `mother keys delete <id>` | Delete key permanently | ✅ |
| `mother export` | Export configuration | ✅ |
| `mother export -o <file>` | Export to specific file | ✅ |
| `mother import <file>` | Import configuration | ✅ |
| `mother import <file> --force` | Force overwrite | ✅ |

---

## Health Check Endpoints

### /health

```bash
curl http://localhost:8080/health
# Expected response:
# {
#   "status": "healthy",
#   "version": "0.3.0",
#   "safe_mode": true,
#   "sandbox_mode": true
# }
```

### /tools

```bash
curl -H "X-API-Key: your-key" http://localhost:8080/tools
# Expected: List of available capabilities
```

---

## Troubleshooting

### Package Not Found

```bash
# Wrong package name
pip install mother-ai  # WRONG

# Correct package name
pip install mother-ai-os  # CORRECT
```

### Docker Image Name

```bash
# Wrong image name
docker pull mother-ai:latest  # WRONG

# Correct image name
docker pull mother-ai-os:latest  # CORRECT (if published)
# Or build locally:
docker build -t mother-ai-os:latest .
```

### Key Store Issues

```bash
# Check key store location
ls -la ~/.config/mother/keys.db

# Reset key store (WARNING: deletes all keys)
rm ~/.config/mother/keys.db
mother keys init
```

### Rate Limiting

```bash
# Check rate limit headers
curl -v -H "X-API-Key: your-key" http://localhost:8080/health 2>&1 | grep -i ratelimit
# Expected:
# X-RateLimit-Limit: 60
# X-RateLimit-Remaining: 59
# X-RateLimit-Reset: ...
```

---

## Security Checklist

Before production deployment:

- [ ] `mother doctor` shows 0 failures
- [ ] `MOTHER_REQUIRE_AUTH=true` is set
- [ ] `MOTHER_SAFE_MODE=true` is set
- [ ] `MOTHER_SANDBOX_MODE=true` is set
- [ ] `MOTHER_AUDIT_ENABLED=true` is set
- [ ] Multi-key auth initialized with `mother keys init`
- [ ] At least one admin key created
- [ ] API bound to localhost (or behind reverse proxy)
- [ ] Sensitive files have 0600 permissions
- [ ] LLM provider API key is configured

---

## Version Information

- Package: `mother-ai-os`
- Version: `0.3.0`
- CLI: `mother`
- Docker Image: `mother-ai-os:latest`

*Last verified: 2026-01-13*
