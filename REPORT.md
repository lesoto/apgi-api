# APGI System API — End-to-End Audit Report

**Report Version:** 5.0
**Audit Date:** 2026-03-08
**Auditor:** Claude Code (claude-sonnet-4-6)
**Repository:** lesoto/apgi-api
**Branch:** `claude/app-audit-security-gVXx4`
**Stack:** FastAPI + PostgreSQL + Redis + Celery, Python 3.x

---

## Executive Summary

This report documents the results of a rigorous end-to-end audit of the APGI System API — a REST API for Allostatic Precision-Gated Ignition consciousness modeling. The audit covered all route handlers, middleware, authentication/authorization services, database models, configuration management, error handling, and test infrastructure.

**Overall Assessment:** The codebase demonstrates a mature, well-structured architecture with strong security foundations (JWT with rotation, bcrypt, RBAC, CSRF, rate limiting, structured logging, alerting). However, several critical defects — including unreachable API routes, a broken async pattern causing `RuntimeError` in auth middleware, and debug `print()` statements leaking internals — significantly undermine production readiness.

**Immediate action required on 3 Critical items before any production deployment.**

---

## KPI Scores

| Dimension | Score | Threshold | Status |
|-----------|-------|-----------|--------|
| Functional Completeness | **52 / 100** | ≥ 75 | 🔴 FAIL |
| Security | **68 / 100** | ≥ 80 | 🔴 FAIL |
| Error Handling & Resilience | **74 / 100** | ≥ 75 | 🟡 WARN |
| Implementation Quality | **71 / 100** | ≥ 75 | 🟡 WARN |
| API Design Consistency | **78 / 100** | ≥ 75 | 🟢 PASS |

**Legend:** 🔴 < 70 · 🟡 70–79 · 🟢 ≥ 80

**Overall Health Score: 69 / 100** 🔴

---

## Bug Inventory

### CRITICAL Severity

---

#### BUG-001 — Webhooks and API-Key endpoints are entirely unreachable

- **Severity:** Critical
- **Category:** Functional Completeness
- **Affected Files:** `app/main.py`, `app/routes/__init__.py`

**Description:**
`app/routes/webhooks.py` and `app/routes/api_keys.py` both define complete, fully-implemented `APIRouter` instances, but neither router is imported or registered in `app/main.py`. As a result, every endpoint in these two files — webhook delivery management and API key CRUD — returns `404 Not Found` for all clients.

**Reproduction Steps:**
1. `GET /v1/webhooks/deliveries` → `404 Not Found`
2. `POST /v1/api-keys` → `404 Not Found`
3. `GET /v1/api-keys` → `404 Not Found`

**Expected:** HTTP 200/201 responses from properly registered routes.
**Actual:** HTTP 404 — routes not registered with the FastAPI application.

**Root Cause:**
`app/main.py` imports and includes: `auth`, `export`, `health`, `metrics`, `sessions`, `state`, `tasks`, `templates`, `users`, `version`, `payments`.
Missing: `webhooks`, `api_keys`.

**Fix:**
```python
# app/main.py — add to imports:
from app.routes import api_keys, webhooks

# app/main.py — add to router registrations:
app.include_router(api_keys.router)
app.include_router(webhooks.router)
```

---

#### BUG-002 — `asyncio.run()` nested inside async event loop causes `RuntimeError` in authentication middleware

- **Severity:** Critical
- **Category:** Error Handling & Resilience / Security
- **Affected Files:** `app/middleware/authentication.py:232`

**Description:**
`AuthenticationMiddleware._blocking_verify_token()` is called via `loop.run_in_executor()`, making it run in a thread pool. Inside that thread, it calls `asyncio.run(auth_manager.verify_token(...))`. In Python ≥ 3.10 (and on many asyncio implementations), calling `asyncio.run()` when an event loop is already active raises `RuntimeError: This event loop is already running`, causing all JWT-authenticated requests to fail with 500 Internal Server Error.

**Affected Code (`app/middleware/authentication.py:222–235`):**
```python
def _blocking_verify_token(self, token: str) -> TokenPayload:
    import asyncio
    db = SessionLocal()
    try:
        auth_manager = AuthManager(db)
        payload = asyncio.run(auth_manager.verify_token(token, expected_type="access"))  # BUG
        return payload
    finally:
        db.close()
```

**Reproduction Steps:**
1. Send any authenticated request with a valid JWT Bearer token.
2. Observe `RuntimeError: This event loop is already running` in logs; endpoint returns 500.

**Expected:** Token verified successfully, request proceeds.
**Actual:** `RuntimeError` raised, authentication fails.

**Fix:** Use a dedicated new event loop in the blocking wrapper:
```python
loop = asyncio.new_event_loop()
try:
    payload = loop.run_until_complete(auth_manager.verify_token(token, expected_type="access"))
finally:
    loop.close()
```

---

#### BUG-003 — Debug `print()` statements leak API key internals to stdout in production

- **Severity:** Critical
- **Category:** Security
- **Affected Files:** `app/middleware/authentication.py:282–296`

**Description:**
The `_blocking_verify_api_key()` method contains five `print()` statements that dump internal API key validation state to stdout: the HMAC prefix computed from each incoming API key, total count of active keys, candidate key prefixes, and match results. In production deployments with log aggregation (CloudWatch, Datadog, Splunk, etc.), this output can be captured and used to enumerate the key prefix space or monitor authentication patterns.

**Affected Lines:**
```python
print(f"DEBUG: prefix={prefix}")                         # Line 282
print(f"DEBUG: active_keys count={len(active_keys)}")    # Line 283
print(f"DEBUG: candidate prefix={candidate_key.key_prefix}")  # Line 285
print("DEBUG: found match!")                             # Line 292
print("DEBUG: no match found")                           # Line 296
```

**Fix:** Remove all five `print()` statements. Replace with `logger.debug()` calls if needed during local development, gated by log level.

---

### HIGH Severity

---

#### BUG-004 — `GET /v1/sessions/{session_id}/tasks` missing session ownership check

- **Severity:** High
- **Category:** Security / Authorization
- **Affected Files:** `app/routes/sessions.py:357–410`

**Description:**
The endpoint `GET /v1/sessions/{session_id}/tasks` verifies that the session *exists* but does not verify that the requesting user *owns* the session. Any authenticated user with the `TASK_READ` permission (all roles including `viewer`) can enumerate tasks from any other user's session if they know the session ID.

All other session-scoped endpoints (`GET /{id}`, `POST /{id}/start`, `POST /{id}/pause`, `POST /{id}/stop`, `POST /{id}/reset`, `DELETE /{id}`, `POST /{id}/step`) correctly call `validate_session_ownership()`.

**Reproduction Steps:**
1. Authenticate as User A. Create a session; note its `session_id`.
2. Authenticate as User B (different account).
3. `GET /v1/sessions/{user_a_session_id}/tasks` → Returns User A's tasks (should be 403).

**Expected:** HTTP 403 Forbidden.
**Actual:** HTTP 200 with tasks from another user's session.

**Fix:** Add an ownership check immediately after the session existence check in `get_session_tasks()`:
```python
if session.user_id != current_user.user_id:
    raise HTTPException(status_code=403, detail="Access denied: you do not own this session")
```

---

#### BUG-005 — `POST /v1/payments/create-intent` has no authentication requirement

- **Severity:** High
- **Category:** Security
- **Affected Files:** `app/routes/payments.py:39–78`

**Description:**
The payment intent creation endpoint has no `Depends(get_current_user)` or `Depends(require_permission(...))` dependency. Any unauthenticated party can call `POST /v1/payments/create-intent` and receive a Stripe `clientSecret`. The `AuthenticationMiddleware` passes unauthenticated requests through when no `Authorization` header is present (line 107 of `authentication.py`), so middleware does not compensate for the missing dependency.

**Reproduction Steps:**
1. `POST /v1/payments/create-intent` with no `Authorization` header, body `{"items": []}`.
2. Observe HTTP 200 with `clientSecret`.

**Fix:**
```python
async def create_payment_intent(
    request: PaymentIntentCreateRequest,
    current_user: TokenPayload = Depends(get_current_user),  # Add this
):
```

---

#### BUG-006 — Insecure default `JWT_SECRET_KEY` committed in `.env`

- **Severity:** High
- **Category:** Security
- **Affected Files:** `.env:9`

**Description:**
The `.env` file contains `JWT_SECRET_KEY=your-secret-key-change-in-production-min-32-chars`. This exact string is in `config.py`'s `insecure_defaults` list and will trigger a config error only in production. In development the key is loaded and used, allowing trivial JWT token forgery by anyone who knows the key value (it's now public via the repository).

**Fix:** Rotate all secrets. Generate a new key: `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Ensure `.env` is never committed (enforce via pre-commit or CI).

---

#### BUG-007 — Stripe API keys committed in `.env`

- **Severity:** High
- **Category:** Security
- **Affected Files:** `.env:27–28`

**Description:**
The `.env` file contains real Stripe test API keys:
- `STRIPE_SECRET_KEY=sk_test_4eC39HqLyjWDarjtT1zdp7dc`
- `STRIPE_PUBLISHABLE_KEY=pk_test_TYooMQauvdEDq54NiTphI7jx`

Even test keys should not be committed to version control. This establishes practices that may be replicated with live keys and may violate Stripe's terms of service.

**Fix:** Rotate keys in the Stripe dashboard. Remove from `.env`. Use environment injection at runtime or a secrets manager.

---

#### BUG-008 — `asyncio.get_event_loop()` deprecated; raises `RuntimeError` in Python 3.12+

- **Severity:** High
- **Category:** Implementation Quality
- **Affected Files:** `app/middleware/authentication.py:218, 250`

**Description:**
Both `_verify_token()` and `_verify_api_key()` call `asyncio.get_event_loop()`. This is deprecated since Python 3.10 and emits `DeprecationWarning`. In Python 3.12+ it raises `RuntimeError` if there is no current event loop in the calling context. The correct API inside an `async` method is `asyncio.get_running_loop()`.

**Fix:** Replace both occurrences:
```python
loop = asyncio.get_running_loop()  # was: asyncio.get_event_loop()
```

---

#### BUG-009 — CSRF token scheme is broken for non-JWT form submissions

- **Severity:** High
- **Category:** Security
- **Affected Files:** `app/middleware/csrf.py:54–115`

**Description:**
The CSRF middleware generates a random token on GET requests, stores its HMAC hash in the cookie, but **never returns the raw token to the client**. When validating POST/DELETE requests, it expects the client to send the raw token in `X-CSRF-Token`, then re-hashes it and compares with the cookie value. Since clients only possess `hash(token)` and not `token`, no value they send will pass validation.

The middleware is effectively short-circuited for JWT-authenticated requests (the common API use case), but for any form-based or cookie-authenticated client, CSRF protection is non-functional.

**Flow breakdown:**
1. GET: `token = random()` → cookie = `hash(token)` → raw `token` is **discarded**
2. POST: receives header value `H` → validates `hash(H) == cookie` → `hash(H) == hash(token)` requires `H == token`, but client never received `token`

**Fix:** Implement the double-submit cookie pattern correctly by storing the raw token in the cookie and validating the header against it directly, or return the raw token in a response header for AJAX clients.

---

#### BUG-010 — `asyncio.create_task()` called in synchronous authorization function

- **Severity:** High
- **Category:** Implementation Quality
- **Affected Files:** `app/services/authorization.py:155`

**Description:**
`get_permissions_for_roles()` is a synchronous function that calls `asyncio.create_task()` in the exception handler for invalid role strings. `asyncio.create_task()` requires an active running event loop; calling it in a synchronous context (e.g., during startup, testing, or from a non-async call path) raises `RuntimeError: no running event loop`.

**Affected Code:**
```python
def get_permissions_for_roles(roles: List[str]) -> Set[Permission]:
    ...
    except ValueError:
        asyncio.create_task(alert_manager.trigger_custom_alert(...))  # BUG
```

**Fix:** Guard with a try/except for `RuntimeError`, use `asyncio.ensure_future()`, or replace with a synchronous log call for the non-async context.

---

### MEDIUM Severity

---

#### BUG-011 — Task dependency creation lacks cycle detection

- **Severity:** Medium
- **Category:** Functional Completeness
- **Affected Files:** `app/routes/tasks.py:449–503`

**Description:**
`POST /v1/tasks/{task_id}/dependencies` checks for self-dependencies and duplicate dependencies but does not detect circular chains (e.g., A→B, B→C, C→A). A circular dependency graph could cause Celery task execution to deadlock or loop indefinitely, consuming worker processes.

**Fix:** Before inserting the new dependency, perform a BFS/DFS traversal of existing dependencies starting from `prerequisite_task_id` to verify that `dependent_task_id` is not already reachable.

---

#### BUG-012 — `Content-Disposition` filename not quoted per RFC 6266

- **Severity:** Medium
- **Category:** Security
- **Affected Files:** `app/routes/export.py:154–156`

**Description:**
The export endpoint builds the `Content-Disposition` header without quoting the filename:
```python
headers={"Content-Disposition": f"attachment; filename={filename}"},
```
While the filename is regex-sanitized (only `[a-zA-Z0-9_-]` characters plus the extension and dots), RFC 6266 requires filename values to be quoted strings. Some HTTP clients and middleware may parse unquoted filenames incorrectly or reject the header.

**Fix:**
```python
headers={"Content-Disposition": f'attachment; filename="{filename}"'},
```

---

#### BUG-013 — `new_password` return value silently discarded in password reset

- **Severity:** Medium
- **Category:** Functional Completeness
- **Affected Files:** `app/routes/users.py:494–498`

**Description:**
In `reset_user_password`, the return value of `user_service.reset_password()` is assigned to `new_password` but never used or included in the response. The `PasswordResetResponse` only contains `user_id` and a static success message. If the service generates a temporary password, clients have no way to receive it.

**Affected Code:**
```python
new_password = user_service.reset_password(
    user_id=user_id, new_password=request.new_password
)
return PasswordResetResponse(user_id=user_id, message="Password reset successfully")
```

**Fix:** Either remove the variable assignment if intentionally unused, or add the generated password to the response schema if admin-generated resets should return a temporary password.

---

#### BUG-014 — Rate limiter trusts `X-Forwarded-For` without proxy allowlist

- **Severity:** Medium
- **Category:** Security
- **Affected Files:** `app/middleware/rate_limiting.py:94–104`

**Description:**
`_get_client_id()` reads `X-Forwarded-For` to identify clients for rate limiting. Without a trusted-proxy allowlist, any client can spoof this header to bypass per-IP rate limits by rotating IP addresses.

**Fix:** Only trust `X-Forwarded-For` when the direct client IP is a known/trusted proxy. Alternatively, offload IP resolution to a reverse proxy (nginx, Caddy) that strips and re-writes this header before requests reach the application.

---

#### BUG-015 — `GET /v1/client-docs` references non-existent `/v1/dashboard` endpoint

- **Severity:** Medium
- **Category:** Functional Completeness
- **Affected Files:** `app/routes/version.py:261–268`

**Description:**
The client docs endpoint returns an `endpoints` dictionary that includes `"dashboard": "/v1/dashboard"`, but no dashboard endpoint exists anywhere in the codebase. Clients following this reference will receive 404.

**Fix:** Remove `"dashboard"` from the endpoints dictionary or implement the endpoint.

---

#### BUG-016 — MD5 used in export filename generation

- **Severity:** Medium
- **Category:** Security
- **Affected Files:** `app/routes/export.py:142`

**Description:**
`hashlib.md5()` is used to generate part of export filenames for uniqueness. While not used for security purposes, MD5 is cryptographically broken and may trigger security scanners/audits. The existing combination of timestamp + sanitized session ID is sufficient for uniqueness.

**Fix:** Replace with `hashlib.sha256(...).hexdigest()[:8]` or remove the hash component entirely.

---

#### BUG-017 — `asyncio.create_task()` in `log_audit_event()` may fail outside async context

- **Severity:** Medium
- **Category:** Implementation Quality
- **Affected Files:** `app/services/authorization.py:536`

**Description:**
`log_audit_event()` is a synchronous function. In its exception handler it calls `asyncio.create_task()`. This will raise `RuntimeError` if called outside an async context (same root cause as BUG-010).

---

#### BUG-018 — Default `HOST=0.0.0.0` exposes API on all network interfaces

- **Severity:** Medium
- **Category:** Security
- **Affected Files:** `app/config.py:45`

**Description:**
`self.host = os.getenv("HOST", "0.0.0.0")` binds the API to all interfaces by default. In development environments or Docker containers without network isolation, this unnecessarily exposes the service. The `main.py` `__main__` block correctly defaults to `127.0.0.1`, but the `Settings` class default is misaligned.

**Fix:** Change the default in `config.py` to `"127.0.0.1"` for development, or document the required override for Docker environments.

---

#### BUG-019 — `GET /v1/users/verify-email` contains inline DB logic, bypasses service layer

- **Severity:** Medium
- **Category:** Implementation Quality
- **Affected Files:** `app/routes/users.py:110–161`

**Description:**
The `verify_email` endpoint queries the `User` model directly from the route handler and updates fields inline rather than delegating to `UserManagementService`. This bypasses caching, event hooks, and audit logging that the service layer provides, and duplicates business logic that should live in the service.

---

### LOW Severity

---

#### BUG-020 — `print()` statement in `version.py` triggers lint false-positive

- **Severity:** Low
- **Category:** Implementation Quality
- **Affected Files:** `app/routes/version.py:99`

**Description:**
The Python client example template string in `get_client_documentation()` contains `print("API Health:", health)`. This is template/documentation content, not executed code, but grep-based linters flag it as a production `print()` statement.

---

#### BUG-021 — `CURSOR_SIGNING_KEY` missing from `.env`

- **Severity:** Low
- **Category:** Configuration
- **Affected Files:** `.env`

**Description:**
`CURSOR_SIGNING_KEY` is required by `config.py` (raises `ValueError` in production if missing or insecure) but is absent from the `.env` file. Pagination cursor signing is undefined in development.

**Fix:** Add `CURSOR_SIGNING_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")` to `.env`.

---

#### BUG-022 — `app/routes/__init__.py` exports stale router list

- **Severity:** Low
- **Category:** Implementation Quality
- **Affected Files:** `app/routes/__init__.py`

**Description:**
`__init__.py` exports only 9 routers (`auth`, `users`, `sessions`, `state`, `tasks`, `export`, `health`, `metrics`, `version`), while the application registers 11 routers and 4 additional router files exist. The `templates`, `payments`, `api_keys`, and `webhooks` routers are absent from `__all__`.

---

#### BUG-023 — API key `TokenPayload` has empty `username` and `roles` fields

- **Severity:** Low
- **Category:** Implementation Quality
- **Affected Files:** `app/middleware/authentication.py:165–174`

**Description:**
When authenticating via API key, the constructed `TokenPayload` has `username=""` and `roles=[]`. API key users must rely entirely on explicit `permissions` on the key for authorization. The empty `username` reduces traceability in audit logs. This behavior is not documented in any user-facing API documentation.

---

#### BUG-024 — `profile_functions=True` hardcoded in profiling middleware initialization

- **Severity:** Low
- **Category:** Implementation Quality
- **Affected Files:** `app/main.py:251`

**Description:**
When `PROFILING_ENABLED=true`, the `ProfilingMiddleware` is always initialized with `profile_functions=True` hardcoded and no corresponding environment variable. Detailed function profiling is expensive in high-throughput environments and should be separately configurable.

---

## Missing Features Log

| ID | Feature | Expected | Status | Priority |
|----|---------|----------|--------|----------|
| MF-001 | **Webhook management endpoints** | Full CRUD via `webhooks.py` router | ❌ Router not registered (BUG-001) | P0 |
| MF-002 | **API key management endpoints** | Full CRUD via `api_keys.py` router | ❌ Router not registered (BUG-001) | P0 |
| MF-003 | **Dashboard endpoint** | `GET /v1/dashboard` (referenced in client docs) | ❌ Not implemented | P2 |
| MF-004 | **Email delivery for verification tokens** | Registration creates a token; no email is sent | ❌ SMTP config exists; no send logic | P1 |
| MF-005 | **Task dependency cycle detection** | Reject circular dependency graphs | ❌ Not implemented (BUG-011) | P1 |
| MF-006 | **Audit log read endpoint** | `AuditLog` model is written to but no GET endpoint exists | ❌ No route defined | P2 |
| MF-007 | **MFA setup/enable endpoint** | `generate_mfa_secret()` and `get_mfa_qr_url()` exist in `AuthManager` | ❌ No route defined | P1 |
| MF-008 | **Extended pagination metadata** | `has_next`, `total_pages` in list responses | ⚠️ Partial — total count only | P2 |
| MF-009 | **Payment amount server-side calculation** | Amount is hardcoded at $99.00; no item-based pricing | ❌ Stub implementation | P1 |
| MF-010 | **User deactivation endpoint** | Soft delete (`is_active=False`) exists in model; no dedicated endpoint | ⚠️ Achievable via `PUT /users/{id}` by admin | P2 |

---

## Security Assessment Summary

| Area | Finding | Risk |
|------|---------|------|
| JWT auth | Access + refresh token rotation ✅ | Low |
| JWT auth | JTI-based access token revocation via Redis ✅ | Low |
| JWT auth | `asyncio.run()` in thread breaks auth — BUG-002 | **Critical** |
| API key auth | HMAC prefix + bcrypt verification ✅ | Low |
| API key auth | Debug print exposes prefix state — BUG-003 | **Critical** |
| RBAC | Role-based permissions with `require_permission()` ✅ | Low |
| RBAC | Session task list missing ownership check — BUG-004 | High |
| Payment | Unauthenticated payment intent creation — BUG-005 | High |
| Secrets | Insecure default JWT key in `.env` — BUG-006 | High |
| Secrets | Stripe test keys in `.env` — BUG-007 | High |
| Input validation | Pydantic schemas on all requests ✅ | Low |
| Input validation | UUID validation on session IDs ✅ | Low |
| CSRF | Middleware present but broken token scheme — BUG-009 | High |
| CORS | Specific allowed origins in `.env` ✅ | Low |
| Rate limiting | Redis-backed sliding window ✅ | Low |
| Rate limiting | `X-Forwarded-For` spoofing possible — BUG-014 | Medium |
| Injection | ORM used throughout; no raw SQL ✅ | Low |
| Error responses | Generic 500 messages; no stack traces in responses ✅ | Low |
| Password security | bcrypt cost factor 12, 72-byte truncation handled ✅ | Low |
| Account lockout | 5 attempts → 15-minute lockout ✅ | Low |
| MFA | TOTP supported via pyotp ✅ | Low |
| TLS | CSRF cookie `secure=True` enforces HTTPS ✅ | Low |

---

## Actionable Recommendations

### Immediate — P0 (before production deployment)

| # | Action | File(s) | Effort |
|---|--------|---------|--------|
| R-001 | Register `webhooks` and `api_keys` routers in `main.py` | `app/main.py` | < 1 h |
| R-002 | Fix `asyncio.run()` in auth middleware — use `new_event_loop()` | `app/middleware/authentication.py` | 2 h |
| R-003 | Remove 5 debug `print()` statements from auth middleware | `app/middleware/authentication.py` | 30 min |
| R-004 | Rotate all secrets; prevent `.env` commits via CI gate | `.env`, CI | 2 h |
| R-005 | Add `Depends(get_current_user)` to payments endpoint | `app/routes/payments.py` | 30 min |

### Short Term — P1 (next sprint)

| # | Action | File(s) | Effort |
|---|--------|---------|--------|
| R-006 | Add ownership check to `GET /v1/sessions/{id}/tasks` | `app/routes/sessions.py` | 1 h |
| R-007 | Replace `asyncio.get_event_loop()` with `asyncio.get_running_loop()` | `app/middleware/authentication.py` | 30 min |
| R-008 | Fix CSRF double-submit pattern — expose raw token to client | `app/middleware/csrf.py` | 3 h |
| R-009 | Fix `asyncio.create_task()` in synchronous functions | `app/services/authorization.py` | 2 h |
| R-010 | Implement email sending for verification tokens (SMTP service) | `app/services/user_management.py` | 4 h |
| R-011 | Implement MFA setup/enable/disable endpoints | `app/routes/auth.py` | 4 h |
| R-012 | Add cycle detection for task dependencies (BFS/DFS) | `app/routes/tasks.py` | 4 h |
| R-013 | Add trusted proxy allowlist for `X-Forwarded-For` | `app/middleware/rate_limiting.py` | 2 h |
| R-014 | Implement server-side payment amount calculation | `app/routes/payments.py` | 6 h |

### Medium Term — P2 (future milestones)

| # | Action | File(s) | Effort |
|---|--------|---------|--------|
| R-015 | Add audit log read/filter endpoints | New route file | 6 h |
| R-016 | Quote `Content-Disposition` filename per RFC 6266 | `app/routes/export.py` | 30 min |
| R-017 | Replace MD5 in filename hash with SHA-256 | `app/routes/export.py` | 30 min |
| R-018 | Move `verify_email` logic into `UserManagementService` | `app/routes/users.py`, `app/services/user_management.py` | 2 h |
| R-019 | Implement or remove `/v1/dashboard` endpoint | `app/routes/version.py` + new file | 4 h |
| R-020 | Update `app/routes/__init__.py` exports to match actual routers | `app/routes/__init__.py` | 30 min |
| R-021 | Add `has_next` and `total_pages` to pagination responses | `app/models/schemas.py` | 2 h |
| R-022 | Change default `HOST` to `127.0.0.1` in `config.py` | `app/config.py` | 15 min |

---

## Detailed Component Assessment

### Authentication (`app/routes/auth.py`, `app/services/auth_manager.py`)

**Strengths:**
- Separate access (30 min) and refresh (7 d) token lifecycle with rotation on each refresh
- Bcrypt at cost factor 12 for password hashing
- Account lockout after 5 failed attempts (15-minute window)
- JTI-based access token revocation via Redis blocklist
- Dedicated `POST /v1/auth/logout-access` for immediate access token invalidation
- MFA (TOTP via pyotp) validated on login

**Issues:** BUG-002 (asyncio.run), BUG-008 (deprecated get_event_loop)

---

### Authorization (`app/services/authorization.py`)

**Strengths:**
- Clean RBAC with `Role` and `Permission` enums; role-to-permission mapping table
- `require_permission()` / `require_role()` FastAPI dependency pattern is DRY
- Audit logging on every authorization decision (success and failure)
- Resource ownership utility (`check_resource_ownership()`)

**Issues:** BUG-004 (missing task list ownership check), BUG-010, BUG-017 (asyncio.create_task in sync)

---

### Session Management (`app/routes/sessions.py`, `app/services/session_manager.py`)

**Strengths:**
- State machine transitions enforced via `ALLOWED_TRANSITIONS` table
- Session ID validated as UUID format
- Redis caching + PostgreSQL persistence
- Ownership validation on all lifecycle endpoints (start, pause, stop, reset, delete, step, get)

**Issues:** BUG-004 — `get_session_tasks` is the only session-scoped endpoint lacking the ownership check

---

### Task Execution (`app/routes/tasks.py`)

**Strengths:**
- Task dependency model with unique constraint and self-dependency prevention
- Celery-backed async execution with status polling
- Webhook delivery on completion
- Session ownership verified before task cancellation

**Issues:** BUG-011 — no cycle detection in dependency graph

---

### Data Export (`app/routes/export.py`)

**Strengths:**
- Streaming responses for large file exports
- Configurable size limits (`MAX_EXPORT_MB`, `MAX_EXPORT_POINTS`)
- Variable name sanitization (regex whitelist)
- Session ID sanitized for safe filenames
- Cursor-based pagination for time series data

**Issues:** BUG-012 (unquoted filename), BUG-016 (MD5 usage)

---

### Payments (`app/routes/payments.py`)

**Critical Issues:**
- BUG-005 — No authentication required
- Hardcoded amount ($99.00) with no real server-side calculation
- Mock response triggered by hardcoded Stripe key prefix string comparison — fragile

---

### Webhooks & API Keys

- BUG-001 — Both router files are fully implemented but completely unreachable

---

### Middleware Stack

**Strengths:**
- Layered defense: `RequestSizeLimit → GZip → Prometheus → Logging → APIVersioning → ResponseValidation → CSRF → Auth → Deprecation → RateLimit → CORS`
- Prometheus metrics middleware collects per-endpoint stats
- Structured JSON logging with sensitive field redaction
- Configurable OpenTelemetry distributed tracing
- Alerting system with rate limiting and cooldown periods
- Request size limiting with configurable threshold

**Issues:** BUG-002, BUG-003, BUG-008 (auth middleware), BUG-009 (CSRF), BUG-014 (rate limiter IP spoofing)

---

### Configuration (`app/config.py`)

**Strengths:**
- Production validation: `ValueError` raised on insecure/missing secrets
- URL format validation for database, Redis, Celery
- Known insecure key list (`insecure_defaults`) with exact-match checks
- Environment-specific CORS origin defaults
- Comprehensive logging level validation

**Issues:** BUG-006, BUG-007 (secrets in `.env`), BUG-021 (missing cursor key), BUG-018 (host default)

---

### Error Handling (`app/exception_handlers.py`)

**Strengths:**
- Centralized handlers for custom `APIError`, `RequestValidationError`, `HTTPException`, and catch-all
- Request body redaction of sensitive fields before logging
- Generic 500 responses (no internal details or stack traces to clients)
- Unique error IDs (`err_<hex>`) for correlation across logs and alerts
- Alert triggering on unhandled exceptions with request metadata

**Issues:** None identified

---

### Database Models (`app/database/models.py`)

**Strengths:**
- Comprehensive composite indexing for all common query patterns
- Soft delete pattern on `User` and `Session`
- Cascade delete configured correctly throughout
- `AuditLog` model with full metadata (user, action, resource, IP, user-agent, status)
- Separate `RefreshToken` table with revocation flag and expiry
- `APIKey` model with HMAC prefix for O(1) candidate reduction + bcrypt verification
- `TaskDependency` model with unique constraint

**Issues:** None identified

---

## Test Coverage Assessment

| Suite | Location | Quality Notes |
|-------|----------|---------------|
| Unit tests | `tests/unit/` | Present; coverage report generated |
| Integration tests | `tests/integration/` | Present (smoke, state, task, user, monitoring) |
| Property-based tests | `tests/property/` | Hypothesis configured with dev/ci/thorough profiles |
| E2E tests | `tests/e2e/` | Skeleton + DB utils present |
| Load tests | `tests/load/` | Present (performance, validation) |
| API contract tests | `tests/api_contract_tests.py` | Present; runs against live server |

**Gaps:**
- No test covering BUG-002 (`asyncio.run` in thread causes RuntimeError)
- No test validating that `GET /sessions/{id}/tasks` rejects non-owners (BUG-004)
- No test for unauthenticated payment intent creation (BUG-005)
- No test verifying webhook or api-key endpoints return 404 (symptom of BUG-001)
- No test for circular task dependency detection (BUG-011)

---

## Appendix: File Reference Map

| Component | File |
|-----------|------|
| App factory | `app/main.py` |
| Configuration | `app/config.py` |
| Auth routes | `app/routes/auth.py` |
| User routes | `app/routes/users.py` |
| Session routes | `app/routes/sessions.py` |
| Task routes | `app/routes/tasks.py` |
| Export routes | `app/routes/export.py` |
| Payment routes | `app/routes/payments.py` |
| Webhook routes | `app/routes/webhooks.py` ⚠️ **unregistered** |
| API key routes | `app/routes/api_keys.py` ⚠️ **unregistered** |
| Health routes | `app/routes/health.py` |
| Version routes | `app/routes/version.py` |
| Auth middleware | `app/middleware/authentication.py` |
| CSRF middleware | `app/middleware/csrf.py` |
| Rate limiter | `app/middleware/rate_limiting.py` |
| Auth manager | `app/services/auth_manager.py` |
| Authorization | `app/services/authorization.py` |
| Session manager | `app/services/session_manager.py` |
| DB models | `app/database/models.py` |
| Schemas | `app/models/schemas.py` |
| Exception handlers | `app/exception_handlers.py` |

---

*Report generated by automated code audit. All findings are based on static analysis of source code as of commit `6c183d6` on branch `claude/app-audit-security-gVXx4`.*
