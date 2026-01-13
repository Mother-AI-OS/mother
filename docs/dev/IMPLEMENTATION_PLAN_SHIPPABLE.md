# Implementation Plan: Shippable/Portable Upgrades

## Overview

This document outlines the implementation plan for the shippable/portable upgrades:
1. Multi-key auth + roles/scopes
2. Rate limiting + quotas
3. `mother doctor` command
4. `mother init` + export/import config

## File Structure

### New Files

```
mother/
├── auth/
│   ├── __init__.py          # Module exports
│   ├── keys.py               # API key store (SQLite-backed)
│   ├── models.py             # Key, Role, Scope models
│   └── scopes.py             # Scope enforcement logic
├── api/
│   └── middleware/
│       ├── __init__.py       # Middleware exports
│       └── ratelimit.py      # Rate limiting middleware
├── cli/
│   └── commands/
│       ├── doctor.py         # Production readiness checks
│       ├── init.py           # Instance bundle generator
│       └── keys.py           # API key management CLI
tests/
├── test_auth_keys.py         # Key store tests
├── test_auth_scopes.py       # Scope enforcement tests
├── test_ratelimit.py         # Rate limiting tests
├── test_cli_doctor.py        # Doctor command tests
├── test_cli_init.py          # Init command tests
docs/
└── dev/
    └── SHIP_ABILITY.md       # Documentation
```

### Modified Files

```
mother/
├── api/
│   ├── auth.py               # Add multi-key validation
│   └── routes.py             # Add rate limit middleware
├── audit/
│   └── logger.py             # Add actor_* fields
├── config/
│   └── settings.py           # Add rate limit settings
├── cli/
│   └── __init__.py           # Register new commands
└── policy/
    └── engine.py             # Accept identity context
```

---

## A. Multi-key Auth + Roles/Scopes

### A1. Key Store (`mother/auth/keys.py`)

```python
class APIKeyStore:
    """SQLite-backed API key management."""

    DB_PATH = ~/.config/mother/keys.db

    def __init__(self, db_path: Path | None = None)
    def initialize(self) -> None  # Create tables
    def add_key(name: str, role: Role, scopes: list[str]) -> APIKey
    def get_key(key_id: str) -> APIKey | None
    def validate_key(api_key: str) -> APIKey | None
    def list_keys() -> list[APIKey]
    def revoke_key(key_id: str) -> bool
    def rotate_key(key_id: str) -> APIKey  # New key, old revoked

class APIKey:
    """API key data model."""
    id: str           # UUID
    name: str         # Human-readable name
    key_hash: str     # bcrypt hash of actual key
    role: Role        # admin/operator/readonly
    scopes: list[str] # Capability prefixes
    created_at: datetime
    expires_at: datetime | None
    revoked: bool
    last_used_at: datetime | None
```

### A2. Models (`mother/auth/models.py`)

```python
class Role(str, Enum):
    ADMIN = "admin"        # Full access
    OPERATOR = "operator"  # Execute capabilities, no key management
    READONLY = "readonly"  # Read-only operations

class IdentityContext:
    """Identity context passed through request lifecycle."""
    key_id: str
    name: str
    role: Role
    scopes: list[str]

    def has_scope(self, required: str) -> bool
    def is_admin(self) -> bool
```

### A3. Scope Enforcement (`mother/auth/scopes.py`)

```python
# Scope format: "prefix:action" or "prefix:*"
# Examples: "filesystem:read", "tasks:*", "policy:read"

ROLE_DEFAULT_SCOPES = {
    Role.ADMIN: ["*"],  # All scopes
    Role.OPERATOR: ["filesystem:*", "tasks:*", "shell:*", "email:*"],
    Role.READONLY: ["filesystem:read", "filesystem:list", "tasks:read"],
}

def check_scope(identity: IdentityContext, capability: str) -> bool:
    """Check if identity has required scope for capability."""

def capability_to_scope(capability_name: str) -> str:
    """Convert capability name to required scope."""
    # "filesystem_read_file" -> "filesystem:read"
```

### A4. Auth Updates (`mother/api/auth.py`)

```python
# Add new functions
async def get_identity_context(
    api_key: str = Security(api_key_header)
) -> IdentityContext | None:
    """Get identity context from API key."""

async def require_scope(scope: str):
    """Dependency that requires specific scope."""

# Keep backward compatibility
async def verify_api_key(...) -> str | None:
    # If MOTHER_API_KEY set (legacy mode): validate against it
    # Else: validate against key store
```

---

## B. Rate Limiting + Quotas

### B1. Middleware (`mother/api/middleware/ratelimit.py`)

```python
class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 20,
    )

    def check(self, key: str) -> tuple[bool, dict]:
        """Check if request allowed. Returns (allowed, headers)."""

    def get_retry_after(self, key: str) -> int:
        """Seconds until next request allowed."""

class RateLimitMiddleware:
    """FastAPI middleware for rate limiting."""

    def __init__(
        self,
        app: ASGIApp,
        command_rpm: int = 60,
        stream_rpm: int = 30,
        burst: int = 20,
        enabled: bool = True,
    )

    async def __call__(self, scope, receive, send):
        # Extract API key from headers
        # Check appropriate limiter based on path
        # Return 429 if exceeded
```

### B2. Settings (`mother/config/settings.py`)

```python
# Add to Settings class
rate_limit_enabled: bool = True  # MOTHER_RATE_LIMIT_ENABLED
rate_limit_command_rpm: int = 60  # MOTHER_RATE_LIMIT_COMMAND_RPM
rate_limit_stream_rpm: int = 30   # MOTHER_RATE_LIMIT_STREAM_RPM
rate_limit_burst: int = 20        # MOTHER_RATE_LIMIT_BURST
```

### B3. Error Response

```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests",
  "retry_after": 5,
  "limit": 60,
  "remaining": 0,
  "reset_at": "2024-01-15T10:30:00Z"
}
```

---

## C. `mother doctor` Command

### C1. Implementation (`mother/cli/commands/doctor.py`)

```python
class DoctorCheck:
    """Single diagnostic check."""
    name: str
    status: Literal["PASS", "WARN", "FAIL"]
    message: str
    remediation: str | None

class Doctor:
    """Production readiness checker."""

    def run_all_checks(self) -> list[DoctorCheck]

    # Individual checks
    def check_python_version(self) -> DoctorCheck
    def check_config_paths(self) -> DoctorCheck
    def check_policy_file(self) -> DoctorCheck
    def check_safe_mode(self) -> DoctorCheck
    def check_sandbox_enabled(self) -> DoctorCheck
    def check_auth_configured(self) -> DoctorCheck
    def check_audit_logging(self) -> DoctorCheck
    def check_port_available(self) -> DoctorCheck
    def check_high_risk_plugins(self) -> DoctorCheck
    def check_docker_runtime(self) -> DoctorCheck

def run_doctor(args) -> int:
    """CLI entry point."""
```

### C2. Output Format

```
Mother Doctor - Production Readiness Check
==========================================

[PASS] Python version: 3.12.3 (>= 3.10 required)
[PASS] Config directory: ~/.config/mother (writable)
[PASS] Workspace directory: ./workspace (writable)
[PASS] Policy file: ./mother_policy.yaml (valid)
[WARN] Safe mode: DISABLED
       → Enable with MOTHER_SAFE_MODE=true for production
[PASS] Sandbox mode: enabled
[PASS] Authentication: 2 API keys configured
[PASS] Audit logging: enabled (./logs/audit.jsonl)
[PASS] Port 8080: available
[PASS] High-risk plugins: all disabled
[WARN] Docker runtime: not detected
       → Install Docker for enhanced sandboxing

Summary: 9 passed, 2 warnings, 0 failures
```

---

## D. `mother init` + Export/Import

### D1. Init Command (`mother/cli/commands/init.py`)

```python
class InstanceBundleGenerator:
    """Generate portable instance bundle."""

    def generate(self, path: Path) -> None:
        # Create directory structure
        # Generate docker-compose.yml
        # Generate .env.example
        # Generate policy.yaml template
        # Generate README.md
        # Create empty workspace/ and logs/

def run_init(args) -> int:
    """CLI entry point for 'mother init'."""

def run_export_config(args) -> int:
    """CLI entry point for 'mother export-config'."""

def run_import_config(args) -> int:
    """CLI entry point for 'mother import-config'."""
```

### D2. Bundle Structure

```
<bundle_path>/
├── docker-compose.yml
├── .env.example
├── mother_policy.yaml
├── workspace/
│   └── .gitkeep
├── logs/
│   └── .gitkeep
├── plugins/
│   └── .gitkeep
└── README.md
```

### D3. Export Format

```yaml
# mother_config_export.yaml
version: "1.0"
exported_at: "2024-01-15T10:00:00Z"
policy:
  content: |
    version: "1.0"
    name: "default-safe"
    ...
plugins:
  enabled:
    - email
    - pdf
    - datacraft
settings:
  safe_mode: true
  sandbox_mode: true
  audit_enabled: true
  # NOTE: Secrets are NOT exported
```

---

## E. Audit Attribution Updates

### E1. AuditEntry Updates (`mother/audit/logger.py`)

```python
@dataclass
class AuditEntry:
    # ... existing fields ...

    # New actor fields
    actor_key_id: str | None = None
    actor_name: str | None = None
    actor_role: str | None = None
```

### E2. Logging Methods Updates

```python
def log_capability_request(
    self,
    capability: str,
    params: dict,
    identity: IdentityContext | None = None,  # New parameter
    ...
):
    entry = AuditEntry(
        ...
        actor_key_id=identity.key_id if identity else None,
        actor_name=identity.name if identity else None,
        actor_role=identity.role.value if identity else None,
    )
```

---

## Implementation Order

### Commit 1: Multi-key Store + Auth Identity Context
- Create `mother/auth/` module
- Implement `APIKeyStore` with SQLite
- Implement `APIKey` and `IdentityContext` models
- Update `mother/api/auth.py` for dual-mode auth
- Add `mother keys` CLI commands
- Tests: `test_auth_keys.py`

### Commit 2: Scopes/Roles Enforcement + Audit Attribution
- Implement scope checking in `mother/auth/scopes.py`
- Update `PolicyEngine` to accept identity context
- Update `AuditLogger` with actor fields
- Add scope validation to API routes
- Tests: `test_auth_scopes.py`

### Commit 3: Rate Limiting Middleware + Tests
- Create `mother/api/middleware/ratelimit.py`
- Add rate limit settings to `Settings`
- Integrate middleware in `main.py`
- Tests: `test_ratelimit.py`

### Commit 4: Doctor + Init/Export/Import + Docs
- Create `mother/cli/commands/doctor.py`
- Create `mother/cli/commands/init.py`
- Register CLI commands
- Write `docs/dev/SHIP_ABILITY.md`
- Update README quickstart
- Tests: `test_cli_doctor.py`, `test_cli_init.py`

---

## Testing Strategy

### Unit Tests
- Key store CRUD operations
- Scope matching logic
- Rate limiter token bucket
- Doctor check functions
- Bundle generation

### Integration Tests
- Auth flow with multi-key
- Scope enforcement on routes
- Rate limiting behavior
- Export/import roundtrip

### CI Requirements
- All tests pass offline
- No external dependencies
- Coverage maintained
