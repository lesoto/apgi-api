# APGI System API — Production Readiness Audit Report

**Report Version:** 1.0
**Audit Date:** 2026-03-12
**Codebase Commit:** `c1f2105`
**Branch Audited:** `claude/audit-production-readiness-Ps6zp`
**Auditor:** Claude (automated end-to-end audit)

---

## Executive Summary

The APGI System API is a FastAPI application implementing a consciousness modeling REST service backed by PostgreSQL, Redis, and Celery. The architecture is well-structured, middleware coverage is comprehensive, and test scaffolding is in place. However, **the application is NOT production-ready** in its current state due to several verified security vulnerabilities, one credential-leaking critical bug, and a set of high-severity implementation gaps.

The most urgent issue is that **password reset tokens are logged in plaintext** to the application log on every SMTP failure — a single misconfigured SMTP server in production would expose every password reset token requested. This defect alone constitutes a critical data-exposure vulnerability.

Additional high-severity issues include plaintext storage of password reset tokens and MFA backup codes in the database, low-entropy MFA backup codes, missing input validation on export variable names, and Stripe API keys that fall back to hardcoded test placeholders with no production-environment enforcement.

Once the critical and high-severity items below are resolved, the application should reach an acceptable production baseline.

---

## KPI Scores

| Dimension | Score | Status |
|---|---|---|
| Functional Completeness | 74 / 100 | 🟡 Needs Work |
| Security & Auth | 58 / 100 | 🔴 Poor |
| Error Handling & Resilience | 72 / 100 | 🟡 Needs Work |
| Code Quality & Maintainability | 70 / 100 | 🟡 Needs Work |
| Observability & Ops Readiness | 76 / 100 | 🟡 Needs Work |
| **Overall Production Readiness** | **62 / 100** | **🔴 Not Ready** |

Score thresholds: 🟢 ≥ 85 · 🟡 65–84 · 🔴 < 65

---

## Bug Inventory

### CRITICAL

---

#### BUG-001 — Password Reset Token Logged in Plaintext on SMTP Failure

**Severity:** CRITICAL
**File:** `app/services/user_management.py:288, 332`
**Reproduction:**
1. Configure an invalid SMTP server (`SMTP_SERVER=badhost`).
2. Call `POST /v1/users/reset-password` with a valid email.
3. The token is committed to the DB at line 227, then `_send_password_reset_email` is called.
4. SMTP fails → the `except` block at line 329 emits two log lines:
   - Line 288 (no-SMTP path): `logger.info(f"Password reset for {email}: token is {reset_token}")`
   - Line 332 (failed SMTP path): `logger.warning(f"Password reset failed to send email, token for {email}: {reset_token}")`
5. Token is visible in structured logs, log aggregators, or any syslog forwarder.

**Impact:** An attacker with read access to logs can use the token to reset any user's password within the 1-hour window.
**Expected:** Token must never appear in log output. Log only `"Password reset email failed"` without the token value.
**Fix:** Remove the token from both log statements. Pass only `email` and `user_id` for correlation.

---

#### BUG-002 — Password Reset Token Stored in Database as Plaintext

**Severity:** CRITICAL
**File:** `app/services/user_management.py:222`, `app/database/models.py:98`
**Reproduction:**
1. Call `POST /v1/users/reset-password` for any valid email.
2. Query the `users` table: `SELECT password_reset_token FROM users WHERE email = '...'`.
3. The raw `secrets.token_urlsafe(32)` value is visible.

**Impact:** A database read (via SQL injection, compromised replica, backup leak, or insider threat) exposes every pending reset token. An attacker can immediately take over any account with a pending reset.
**Expected:** Token should be stored as a SHA-256 or bcrypt hash. Only the hash is stored; the raw token is sent via email and never persisted.
**Fix:** Hash the token before persisting (e.g., `hashlib.sha256(token.encode()).hexdigest()`). During confirmation, hash the submitted token and compare with the stored hash.

---

### HIGH

---

#### BUG-003 — MFA Backup Codes Stored as Plaintext JSON in Database

**Severity:** HIGH
**File:** `app/routes/users.py:652, 905`, `app/database/models.py:91`
**Reproduction:**
1. Enroll MFA for a user (`POST /v1/users/mfa/enroll`).
2. Inspect the `mfa_backup_codes` JSON column in the `users` table.
3. All 10 codes are stored verbatim as a JSON array.

**Impact:** A database read exposes all backup codes. Since backup codes bypass TOTP, an attacker can immediately authenticate as any user with MFA enabled.
**Expected:** Backup codes should be hashed before storage (bcrypt or SHA-256 with HMAC). Verification should hash the submitted code and compare against stored hashes.
**Fix:** Apply `hashlib.sha256(code.encode()).hexdigest()` to each code before storing. In `verify_mfa_backup_code`, hash the request code before comparing.

---

#### BUG-004 — MFA Backup Codes Have Insufficient Entropy

**Severity:** HIGH
**File:** `app/routes/users.py:647, 902`

```python
backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]
```

**Reproduction:** `secrets.token_hex(4)` produces 4 random bytes = 32 bits of entropy = 8 hex characters (e.g., `A3F2B10C`). With 10 codes and a database leak, an offline brute-force attack has a search space of 2^32 ≈ 4 billion per code. Modern GPUs can exhaust this in seconds.
**Expected:** NIST SP 800-63B recommends ≥ 112 bits of entropy for recovery codes. `secrets.token_hex(16)` (128-bit, 32 hex chars) is the minimum acceptable size.
**Fix:** Change to `secrets.token_hex(16).upper()` or `secrets.token_urlsafe(20)` (≥ 128 bits).

---

#### BUG-005 — Export Endpoint Does Not Validate Variable Names

**Severity:** HIGH
**File:** `app/routes/export.py:120–122`

```python
var_list = None
if variables:
    var_list = [v.strip() for v in variables.split(",")]
```

**Contrast with `get_time_series_data` at line 289–299 which correctly applies:**
```python
if not var or not re.match(r"^[a-zA-Z0-9_-]+$", var):
    raise HTTPException(...)
```

**Reproduction:** Call `GET /v1/sessions/{id}/export?format=json&variables=../../etc/passwd` or any injection payload. The unvalidated `var_list` is passed directly to `DataExportService.export_session_data`.
**Impact:** Depends on how `DataExportService` consumes variable names. If it uses them in Redis key construction or dynamic queries, injection or path traversal may be possible. Guaranteed inconsistency with the validated `timeseries` endpoint.
**Expected:** Apply the same regex validation used in `get_time_series_data` before passing `var_list` to the service layer.

---

#### BUG-006 — Stripe API Keys Default to Hardcoded Test Placeholders; No Production Enforcement

**Severity:** HIGH
**File:** `app/config.py:216–219`, `app/routes/payments.py:18`

```python
self.stripe_secret_key: str = os.getenv("STRIPE_SECRET_KEY", "sk_test_placeholder")
self.stripe_publishable_key: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "pk_test_placeholder")
```

The `__post_init__` method validates JWT, cursor, and webhook keys but **does not validate Stripe keys**. The payments router executes `stripe.api_key = settings.stripe_secret_key` at import time, meaning a deployment without `STRIPE_SECRET_KEY` silently initialises Stripe with a non-functional placeholder.
**Impact:** Payment processing fails silently in production if keys are not explicitly set. No guard prevents a staging key from being used in production.
**Fix:** Add production-environment validation for `STRIPE_SECRET_KEY` in `__post_init__`. Raise `ValueError` if the key is the default placeholder value in production.

---

#### BUG-007 — Password Reset Route Ordering Creates Routing Ambiguity

**Severity:** HIGH
**File:** `app/routes/users.py:468, 524`

Two routes coexist:
- `POST /v1/users/{user_id}/reset-password` (line 468) — authenticated, requires `user_id` path param
- `POST /v1/users/reset-password` (line 524) — unauthenticated, email-based flow

FastAPI/Starlette matches routes in registration order. If any router ordering places `/{user_id}/reset-password` before the literal `/reset-password`, a request to `/v1/users/reset-password` is caught by the path-parameter route with `user_id = "reset-password"`, producing a `UserNotFoundError` or `404` instead of the intended password-reset flow.

**Reproduction:** Verify registration order; call `POST /v1/users/reset-password` with `Content-Type: application/json` and `{"email": "user@example.com"}`. If the wrong handler fires, `{"detail": "User not found"}` is returned instead of the email-sent response.
**Fix:** Ensure the literal `/reset-password` route is registered before `/{user_id}/reset-password`. Use explicit ordering or rename the parameterized route to reduce ambiguity.

---

### MEDIUM

---

#### BUG-008 — Session Tasks Endpoint Lacks Admin Override for Ownership Check

**Severity:** MEDIUM
**File:** `app/routes/sessions.py:501–514`

All other session endpoints pass `is_admin=has_any_role(current_user.roles, [Role.ADMIN])` to `validate_session_ownership`. The `get_session_tasks` endpoint implements ownership inline without an admin bypass:

```python
if session.user_id != current_user.user_id:
    return "forbidden"
```

**Impact:** Admins cannot list tasks for sessions owned by other users, breaking administrative oversight.
**Expected:** Consistent admin override as applied in all other session-scoped endpoints.
**Fix:** Apply the same `validate_session_ownership` helper with the admin flag, or add an admin check inline.

---

#### BUG-009 — `asyncio.get_event_loop()` Deprecated; Will Raise RuntimeError in Python 3.12+

**Severity:** MEDIUM
**Files:** `app/routes/sessions.py:87, 517`, `app/middleware/authentication.py:239, 310`

```python
loop = asyncio.get_event_loop()
session = cast(SessionModel, await loop.run_in_executor(None, _blocking_validate))
```

`asyncio.get_event_loop()` emits a `DeprecationWarning` in Python 3.10+ and **raises a `RuntimeError`** in Python 3.12+ when called from a coroutine that did not create a new event loop. The correct API is `asyncio.get_running_loop()`.
**Fix:** Replace all four occurrences with `asyncio.get_running_loop()`.

---

#### BUG-010 — CSRF `_should_protect` Has Unreachable Dead Code (DELETE Not Protected for Bearer Auth)

**Severity:** MEDIUM
**File:** `app/middleware/csrf.py:99–103`

```python
if request.headers.get("authorization", "").startswith("Bearer "):
    return False          # ← returns here for ALL JWT-authenticated requests
if request.method == "DELETE":
    return True           # ← this branch is NEVER reached for Bearer clients
```

The code comment states "DELETE requests should always be protected due to their destructive nature" but the logic means JWT-authenticated DELETE requests (all authenticated deletes) bypass CSRF entirely. The condition at line 102 is dead code.
**Impact:** While pure-API JWT flows don't need classical CSRF tokens, the code intent is contradicted by the implementation, creating an audit discrepancy.
**Fix:** Move the DELETE check above the Bearer check, or remove the dead branch and update the comment to reflect the deliberate API-first design decision.

---

#### BUG-011 — Registration Endpoint Not Subject to Stricter Auth Rate Limit

**Severity:** MEDIUM
**File:** `app/middleware/rate_limiting.py:145–160`

The rate limiter categorises `/v1/auth` paths as `"auth:attempt"` (10 req/min). However, `POST /v1/users/register` is under `/v1/users` and falls to the `"global"` bucket (60 req/min). An attacker can create 60 accounts per minute per IP, enabling account enumeration, resource exhaustion, or spam.
**Fix:** Add `/v1/users/register` to the `"auth:attempt"` bucket, or add a dedicated `"user:register"` bucket with a conservative limit (e.g., 5 req/min per IP).

---

#### BUG-012 — API Key Authentication Assigns Empty Roles, Breaking Admin Ownership Bypasses

**Severity:** MEDIUM
**File:** `app/middleware/authentication.py:185–194`

```python
user_payload = TokenPayload(
    user_id=api_key_info.user_id,
    username="",          # ← no username
    roles=[],             # ← no roles
    ...
    permissions=api_key_info.permissions,
)
```

`has_any_role(current_user.roles, [Role.ADMIN])` always returns `False` for API key clients regardless of their permissions. Admin-level API keys cannot access other users' sessions or invoke admin-scoped operations via `validate_session_ownership`.
**Expected:** API key permissions should be mapped to equivalent roles, or the ownership-check helper should honour the `permissions` list in addition to `roles`.

---

#### BUG-013 — `list_users` Response Does Not Include Total Count for Pagination

**Severity:** MEDIUM
**File:** `app/routes/users.py:265–277`

`GET /v1/users` returns `List[UserResponse]` with page/per_page parameters but omits the total record count. Clients cannot compute the number of pages or detect when all records have been fetched.
**Expected:** Wrap the response in a paginated envelope similar to `SessionListResponse` which includes `pagination.total`.
**Fix:** Return a `UsersListResponse` with `users: List[UserResponse]` and `pagination: PaginationInfo`.

---

#### BUG-014 — Unused `python-jose` Library Alongside `pyjwt`

**Severity:** MEDIUM
**File:** `requirements.txt:16`, `requirements-prod.txt:16`

Both `pyjwt` and `python-jose[cryptography]` are declared as dependencies. The codebase only imports and uses `pyjwt`. `python-jose` introduces `cryptography` as a transitive dependency (large C-extension library) and historically has had CVEs. Having two JWT libraries with overlapping functionality increases the attack surface and dependency footprint unnecessarily.
**Fix:** Remove `python-jose[cryptography]` from all requirements files.

---

#### BUG-015 — CORS Default Allows All HTTP Methods

**Severity:** MEDIUM
**File:** `app/config.py:120`

```python
self.cors_allow_methods = ["*"]
```

When `CORS_ALLOW_METHODS` is not explicitly set, all HTTP methods are allowed. This includes `CONNECT`, `TRACE`, and `PATCH` which may not be expected by the API surface.
**Fix:** Change the default to `["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"]` to explicitly enumerate intended methods.

---

### LOW

---

#### BUG-016 — `GET /health` Is Listed in `PUBLIC_PATHS` But Also Has a Router Dependency

**Severity:** LOW
**File:** `app/middleware/authentication.py:58`, `app/routes/health.py:59`

`/health` is in `PUBLIC_PATHS` (no auth required), consistent with its intent as a public liveness probe. However, `root_health_check` depends on `get_health_service()` which calls Redis checks that may expose internal system state (component names, latency). Consider whether full health detail should require authentication in production.

---

#### BUG-017 — Missing `updated_at` Auto-Update on Soft Delete

**Severity:** LOW
**File:** `app/database/models.py:113`

The `User.updated_at` column uses `onupdate=func.now()` which applies to SQLAlchemy ORM updates. However, soft deletes that set `is_deleted=True` directly may not trigger this if the ORM session isn't properly flushed. Verify `updated_at` reflects the deletion timestamp.

---

#### BUG-018 — `datetime.now()` Without Timezone in Export Filename

**Severity:** LOW
**File:** `app/routes/export.py:160`

```python
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
```

Uses naive local time. Should use `datetime.now(timezone.utc)` for consistent, timezone-safe filenames across deployments.

---

#### BUG-019 — Celery Tasks Return Arbitrary `Any` Result Without Schema Validation

**Severity:** LOW
**File:** `app/tasks/task_registry.py`

Task results stored in `Task.result_data` (JSON column) have no enforced schema. When returned via `GET /v1/sessions/{id}/tasks`, the `TaskStatusResponse.result` field is typed as `Optional[Any]`, bypassing any validation. Downstream consumers may receive malformed data.

---

#### BUG-020 — No Request ID Propagated to All Log Statements

**Severity:** LOW
**File:** Multiple route files

Request logging middleware assigns a `request_id` to `request.state`, but individual route handlers log with plain `f"Session {session_id} created"` without including the request ID. This makes tracing a single request across log lines difficult in production.

---

## Missing Features / Incomplete Implementations

| # | Feature | Location | Impact | Notes |
|---|---|---|---|---|
| MF-001 | Email verification not enforced at login | `app/services/auth_manager.py:385-386` | HIGH | `is_active` check present, but users created via admin path (`create_default_user`) skip verification entirely |
| MF-002 | No rate limiting on MFA backup code verification | `app/routes/users.py:802-852` | HIGH | Brute-force against 32-bit codes possible |
| MF-003 | No account lockout for MFA failures | `app/services/auth_manager.py:406-410` | HIGH | Failed TOTP attempts don't increment `failed_login_attempts` |
| MF-004 | Webhook secret key optional in non-production | `app/config.py:321-322` | MEDIUM | No default validation means webhooks can run without signature verification in dev/staging |
| MF-005 | Refresh token rotation does not invalidate old sessions across devices | `app/services/auth_manager.py:546-565` | MEDIUM | Only one token is revoked per rotation; multiple active refresh tokens are supported but there's no "logout everywhere" UI |
| MF-006 | `GET /v1/users` missing total count in response | `app/routes/users.py:265-277` | MEDIUM | See BUG-013 |
| MF-007 | `POST /v1/users/reset-password/confirm` does not revoke existing sessions | `app/services/user_management.py:237-271` | MEDIUM | After password reset, all existing access and refresh tokens remain valid |
| MF-008 | Export endpoint `event_type` parameter not validated | `app/routes/export.py:337` | LOW | Unsupported event types silently return empty results instead of `400 Bad Request` |
| MF-009 | No dedicated security test suite | `tests/` | HIGH | No tests for SQL injection payloads, XSS, CSRF bypass, or JWT manipulation |
| MF-010 | OpenAPI docs expose detailed schema validation errors | `app/main.py:229-232` | LOW | `/docs` and `/openapi.json` publicly accessible; consider restricting in production |

---

## Dimension Scores — Detailed Breakdown

### 1. Functional Completeness — 74/100

**Strengths:**
- Full CRUD on sessions, tasks, templates, users, and API keys.
- Idempotency key support on session creation.
- Paginated list endpoints with cursor signing.
- Celery-backed async task execution.
- MFA enrolment, enable, disable, and backup code flows implemented.
- Stripe payment routes present.

**Gaps:**
- Export variable validation inconsistency (BUG-005).
- `list_users` pagination incomplete (BUG-013).
- No "logout all devices" operation.
- Password reset does not revoke existing sessions (MF-007).
- Event type validation missing in event analysis endpoint (MF-008).

---

### 2. Security & Auth — 58/100

**Strengths:**
- JWT with JTI-based revocation via Redis blocklist.
- Refresh token rotation with DB-backed invalidation.
- bcrypt + SHA-256 pre-hash for passwords (handles > 72 byte passwords).
- HMAC-based CSRF token with `secrets.compare_digest`.
- Deny-by-default authentication middleware (BUG-005 fix comment in code).
- RBAC with permission enum and role-to-permission mapping.
- Rate limiting per user (authenticated) or IP (unauthenticated).
- Account lockout after 5 failed login attempts.
- Comprehensive security headers (HSTS, CSP, COEP, COOP, X-Frame-Options).
- API key verification uses HMAC prefix for fast lookup + bcrypt full comparison.

**Weaknesses:**
- Critical: Token logged in plaintext on SMTP failure (BUG-001).
- Critical: Reset token stored as plaintext (BUG-002).
- High: MFA backup codes plaintext + low entropy (BUG-003, BUG-004).
- High: No production enforcement on Stripe keys (BUG-006).
- Medium: CSRF dead code for DELETE (BUG-010).
- Medium: No rate limit on registration (BUG-011).
- Medium: MFA failures don't trigger lockout (MF-003).
- Medium: Password reset doesn't revoke sessions (MF-007).

---

### 3. Error Handling & Resilience — 72/100

**Strengths:**
- Custom exception classes (`AuthenticationError`, `SessionNotFoundError`, `AuthorizationError`, etc.) mapped to appropriate HTTP status codes.
- Graceful Redis unavailability handling in rate limiter and token revocation.
- DB rollback on all exception paths.
- Schema validation middleware with configurable fail-on-error.
- Request size limiting middleware.
- Circuit-breaker-style `ServiceUnavailableError` for uninitialized services.

**Weaknesses:**
- Generic `except Exception` blocks in route handlers swallow unexpected errors without distinguishing error categories.
- `asyncio.get_event_loop()` will raise uncaught `RuntimeError` in Python 3.12+ (BUG-009).
- Health check returns `503` for uninitialized health service, but also fires a background alert task without a try/except wrapper.
- `_send_password_reset_email` failure is silently swallowed at line 330-331 (no re-raise), which means callers don't know the email didn't send.

---

### 4. Code Quality & Maintainability — 70/100

**Strengths:**
- Consistent router prefix and tag conventions.
- Dependency injection via `Depends()` throughout.
- Services encapsulated in separate modules.
- `SessionRoutesState` dataclass avoids bare global mutable state.
- Comprehensive Alembic migration setup.
- Hypothesis property-based tests alongside standard unit tests.
- Structured logging with `StructuredLogger`.

**Weaknesses:**
- Widespread `# type: ignore` suppression comments (> 60 occurrences).
- `asyncio.get_event_loop()` deprecated pattern in 4 locations.
- Dual JWT library dependency (`pyjwt` + `python-jose`) — unused dependency.
- Route conflict risk between `/reset-password` and `/{user_id}/reset-password` (BUG-007).
- `import` statements inside function bodies (e.g., `from app.database.models import AuditLog` inside `login`, `import re` inside handlers) — should be at module level.
- No `__all__` exports or interface contracts on service modules.

---

### 5. Observability & Ops Readiness — 76/100

**Strengths:**
- Prometheus metrics middleware.
- OpenTelemetry distributed tracing (conditional import).
- Structured JSON logging via `StructuredLogger`.
- Alert manager with webhook channels and error-rate thresholds.
- Health, readiness, and liveness endpoints.
- DB connection pool status logging.
- Kubernetes-compatible probes (`/health/ready`, `/health/live`).

**Weaknesses:**
- Request IDs not propagated into individual log statements (BUG-020).
- No correlation ID header (`X-Request-ID` or `X-Correlation-ID`) returned to clients.
- Alert manager fires and forgets background tasks without error handling in health route.
- No structured audit log for export operations, only for login events.

---

## Actionable Remediation Plan

| Priority | Bug / Feature | Affected File(s) | Effort | Owner |
|---|---|---|---|---|
| 🔴 P0 | BUG-001: Remove token from log statements | `app/services/user_management.py:288,332` | 30 min | Backend |
| 🔴 P0 | BUG-002: Hash password reset token before DB storage | `app/services/user_management.py:218-227,237-271` | 2 hrs | Backend |
| 🔴 P1 | BUG-003: Hash MFA backup codes before DB storage | `app/routes/users.py:647-652,899-905` | 2 hrs | Backend |
| 🔴 P1 | BUG-004: Increase backup code entropy | `app/routes/users.py:647,902` | 15 min | Backend |
| 🔴 P1 | BUG-005: Validate variable names in export endpoint | `app/routes/export.py:120-122` | 30 min | Backend |
| 🔴 P1 | BUG-006: Add Stripe key validation in production | `app/config.py:__post_init__` | 30 min | Backend |
| 🟡 P2 | BUG-007: Fix password reset route ordering | `app/routes/users.py` | 1 hr | Backend |
| 🟡 P2 | BUG-008: Add admin override to session tasks endpoint | `app/routes/sessions.py:501-514` | 30 min | Backend |
| 🟡 P2 | BUG-009: Replace `get_event_loop()` with `get_running_loop()` | `sessions.py`, `authentication.py` | 30 min | Backend |
| 🟡 P2 | BUG-010: Fix dead CSRF code for DELETE requests | `app/middleware/csrf.py:99-103` | 1 hr | Backend |
| 🟡 P2 | BUG-011: Apply stricter rate limit to registration | `app/middleware/rate_limiting.py` | 30 min | Backend |
| 🟡 P2 | BUG-012: Map API key permissions to roles | `app/middleware/authentication.py` | 2 hrs | Backend |
| 🟡 P2 | MF-003: Add lockout for MFA failures | `app/services/auth_manager.py:406-410` | 1 hr | Backend |
| 🟡 P2 | MF-007: Revoke sessions after password reset | `app/services/user_management.py` | 1 hr | Backend |
| 🟡 P3 | BUG-013: Add total count to user list response | `app/routes/users.py` | 1 hr | Backend |
| 🟡 P3 | BUG-014: Remove `python-jose` from dependencies | `requirements*.txt` | 15 min | Backend/DevOps |
| 🟡 P3 | BUG-015: Restrict default CORS methods | `app/config.py:120` | 15 min | Backend |
| 🟢 P4 | BUG-018: Use UTC in export filename | `app/routes/export.py:160` | 5 min | Backend |
| 🟢 P4 | BUG-020: Propagate request ID in route logs | All route files | 2 hrs | Backend |
| 🟢 P4 | MF-009: Add security test suite | `tests/security/` | 8 hrs | QA/Backend |

---

## Reproduction Environment

```bash
# Local setup (from CLAUDE.md)
ENVIRONMENT=development
DATABASE_URL=postgresql://apgi_dev:dev_password@localhost:5432/apgi_api_dev
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=<random, ≥32 chars>
CURSOR_SIGNING_KEY=<random, ≥32 chars>

./scripts/start.sh        # Starts all services via Docker Compose
pytest tests/unit/        # Run unit tests
```

---

## Appendix — File Inventory Audited

| File | Lines | Notes |
|---|---|---|
| `app/main.py` | 360 | Application factory, lifespan, middleware stack |
| `app/config.py` | 426 | Settings class with production validation |
| `app/database/models.py` | ~320 | ORM models: User, Session, Task, AuditLog, APIKey, RefreshToken |
| `app/routes/auth.py` | 269 | Login, refresh, logout, logout-access |
| `app/routes/sessions.py` | 877 | Session CRUD + lifecycle control |
| `app/routes/users.py` | 961 | User CRUD, MFA, password reset |
| `app/routes/export.py` | 378 | Export, summary, timeseries, events |
| `app/routes/tasks.py` | ~550 | Task execution and dependency management |
| `app/routes/health.py` | 126 | Health, readiness, liveness probes |
| `app/routes/admin.py` | ~150 | Audit log query |
| `app/services/auth_manager.py` | 662 | JWT, bcrypt, TOTP |
| `app/services/authorization.py` | 611 | RBAC, permissions, audit log helper |
| `app/services/user_management.py` | ~380 | User CRUD, password reset, verification |
| `app/middleware/authentication.py` | 444 | JWT + API key verification |
| `app/middleware/csrf.py` | 220 | CSRF token generation and validation |
| `app/middleware/rate_limiting.py` | 298 | Per-user/IP sliding window rate limits |
| `app/middleware/security_headers.py` | 120 | HSTS, CSP, X-Frame-Options, etc. |
| `requirements.txt` | 31 | Core dependencies |
| `tests/` | ~50 files | Unit, integration, property, load, e2e |

---

*Report generated by automated end-to-end audit — 2026-03-12*
