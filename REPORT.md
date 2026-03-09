# APGI System API — End-to-End Audit Report

**Project:** APGI System API (Allostatic Precision-Gated Ignition)
**Branch:** `claude/app-audit-security-PtO9y`
**Audit Date:** 2026-03-09
**Auditor:** Claude Code (automated, full-codebase inspection)
**Report Version:** 6.0

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [KPI Scores](#2-kpi-scores)
3. [Bug Inventory](#3-bug-inventory)
4. [Missing Features Log](#4-missing-features-log)
5. [Recommendations](#5-recommendations)
6. [Appendix — Positive Findings](#6-appendix--positive-findings)

---

## 1. Executive Summary

The APGI System API is a FastAPI + PostgreSQL + Redis application that models consciousness systems via a REST interface. The stack is architecturally sound: proper middleware layering, structured logging, JWT with refresh-token rotation, account lockout, TOTP/MFA, Celery task queues, Prometheus metrics, and OpenTelemetry tracing stubs.

However, the audit uncovered **6 critical bugs** and **13 high-severity issues** that require remediation before this application can be considered production-ready. The most severe problems are:

- **The `.env` file is committed to version control** despite being listed in `.gitignore`, exposing placeholder secret keys and a real Stripe test API key.
- **A debug `print()` statement** is left in production authentication code (`_blocking_verify_api_key`), leaking information on every failed API key lookup.
- **Duplicate module imports** in `main.py` are a sign of an unreviewed merge artefact.
- **`/v1/users/create-default`** is simultaneously declared as a `PUBLIC_PATH` in the auth middleware and decorated with `require_permission(Permission.USER_CREATE)`, making it permanently unreachable (always returns 401/403).
- **CIDR notation in the trusted-proxy allowlist** uses a naïve string-prefix match that can be bypassed (e.g., `10.0.0.0/8` collapses to prefix `"10."`, matching `100.x.x.x`).
- **Payment amount is hardcoded** at $99.00 regardless of cart contents; the mock detection branch key-matches a specific Stripe test key prefix embedded in source code.

Overall application health is **67 / 100**. The codebase shows mature patterns in many areas, but the items above must be fixed before a production deployment.

---

## 2. KPI Scores

| Dimension | Score | Status | Notes |
|-----------|------:|--------|-------|
| **Functional Completeness** | 70 / 100 | 🟡 WARN | Core CRUD functional; create-default endpoint broken; password reset incomplete; payment amount hardcoded |
| **UI/UX Consistency** | 65 / 100 | 🟡 WARN | Error formats vary across routes; some responses lack standard envelope; docs partly inconsistent |
| **Responsiveness & Performance** | 74 / 100 | 🟡 WARN | Good pooling/caching; sync SQLAlchemy in async context; no N+1 guard on task dependencies |
| **Error Handling & Resilience** | 68 / 100 | 🟡 WARN | Logout hard-fails when Redis unavailable; no circuit breaker; webhook TOCTOU; missing jitter on retries |
| **Implementation Quality** | 58 / 100 | 🔴 FAIL | .env committed; debug print in prod auth; duplicate imports; CIDR bypass; broken endpoint; CSP weakened |
| | | | |
| **Overall** | **67 / 100** | 🟡 WARN | |

**Score Legend**

| Range | Status | Label |
|-------|--------|-------|
| 90–100 | 🟢 | PASS — production ready |
| 75–89 | 🟢 | PASS — minor fixes needed |
| 60–74 | 🟡 | WARN — release-blocking issues present |
| 0–59 | 🔴 | FAIL — significant remediation required |

---

## 3. Bug Inventory

Bugs are ordered by severity (Critical → High → Medium → Low) then by impact within each tier.

---

### 3.1 Critical Severity

---

#### BUG-C01 — `.env` committed to git with placeholder and real API keys

| Field | Detail |
|-------|--------|
| **Severity** | Critical |
| **File** | `.env` (repo root) |
| **Lines** | 9–11, 29–30 |
| **Status** | `.env` is listed in `.gitignore` but is tracked by git (`git ls-files .env` returns a match) |

**Expected:** `.env` should never appear in git history.

**Actual:** The file is tracked. It contains:
- `JWT_SECRET_KEY=your-secret-key-change-in-production-min-32-chars` — insecure placeholder, rejects in production but accepted in development
- `CURSOR_SIGNING_KEY=your-cursor-signing-key-change-in-production-min-32-chars` — same
- `WEBHOOK_SECRET_KEY=your-webhook-secret-key-change-in-production-min-32-chars` — same
- `STRIPE_SECRET_KEY=sk_test_4eC39HqLyjWDarjtT1zdp7dc` — **an actual Stripe test-mode secret key**
- `STRIPE_PUBLISHABLE_KEY=pk_test_TYooMQauvdEDq54NiTphI7jx` — Stripe publishable key

**Impact:** Any developer or CI runner with repo access has the Stripe test key. The key can be used to create test charges, list test customers, and enumerate test payment methods.

**Reproduction:**
```bash
git ls-files .env          # confirms it is tracked
git log --all -- .env      # shows full commit history
cat .env | grep STRIPE     # reveals key
```

**Fix:**
```bash
git rm --cached .env
git commit -m "chore: untrack .env — was erroneously committed"
# Rotate the Stripe test key immediately via dashboard.stripe.com
# Use a secrets manager (AWS Secrets Manager, HashiCorp Vault) for all keys going forward
```

---

#### BUG-C02 — Debug `print()` in production authentication code

| Field | Detail |
|-------|--------|
| **Severity** | Critical |
| **File** | `app/middleware/authentication.py` |
| **Line** | 339 |

**Expected:** No debug output in production code.

**Actual:**
```python
if not db_api_key:
    print("DEBUG: no match found")   # ← committed to production code path
    raise ValueError("Invalid API key")
```

**Impact:** Every failed API key lookup writes `"DEBUG: no match found"` to stdout. In containerised environments this floods logs. It can also be used for timing-based enumeration to confirm which API keys are near-matches versus completely unknown (information disclosure).

**Fix:** Remove the `print` statement entirely. The `raise ValueError` below it is sufficient; the caller already logs the failure at WARNING level.

---

#### BUG-C03 — `/v1/users/create-default` endpoint is permanently unreachable

| Field | Detail |
|-------|--------|
| **Severity** | Critical |
| **File** | `app/middleware/authentication.py:55–70`, `app/routes/users.py:171–214` |

**Expected:** `POST /v1/users/create-default` creates the initial admin user for bootstrapping a fresh deployment.

**Actual:** The path `/v1/users/create-default` appears in **both** `PUBLIC_PATHS` (authentication middleware skips auth for it) **and** the route is decorated with `dependencies=[Depends(require_permission(Permission.USER_CREATE))]`.

Flow for any request, authenticated or not:
1. Auth middleware sees the path in `PUBLIC_PATHS` → skips authentication → `request.state.user` is never set.
2. FastAPI resolves `require_permission(Permission.USER_CREATE)` → calls `get_current_user(request)`.
3. `get_current_user` finds no user in `request.state` → raises HTTP 401 or 403.

The endpoint is unreachable under every possible authentication state.

**Fix (preferred):** Remove `/v1/users/create-default` from `PUBLIC_PATHS`. Require a valid admin JWT to call it, or protect it with a first-run check (refuse if any admin user already exists in the DB).

---

#### BUG-C04 — Duplicate module imports in `main.py` (merge artefact)

| Field | Detail |
|-------|--------|
| **Severity** | Critical (code quality) |
| **File** | `app/main.py` |
| **Lines** | 48–63 and 72–86 |

**Expected:** Each module imported once.

**Actual:** All route modules are imported in two separate `from app.routes import (...)` blocks. The second block (lines 72–86) is a subset of the first (lines 48–63). Python silently deduplicates module references, so routes are not double-registered, but this:
- Is an unreviewed merge conflict artefact (`git log` confirms it appeared after a merge commit)
- Creates a maintenance hazard (changes made to one block may not be reflected in the other)
- Signals that the codebase contains at least one partially-resolved merge conflict

**Fix:** Delete lines 72–86 (the duplicate `from app.routes import (...)` block) and keep only the first block.

---

#### BUG-C05 — CIDR proxy allowlist check is bypassable via string-prefix match

| Field | Detail |
|-------|--------|
| **Severity** | Critical |
| **File** | `app/middleware/rate_limiting.py` |
| **Lines** | 107–115 |

**Expected:** Rate limiter identifies the real client IP by trusting `X-Forwarded-For` only from legitimate reverse proxies in configured private CIDR ranges.

**Actual:**
```python
def is_trusted_proxy(ip: str) -> bool:
    for trusted in trusted_proxies:
        if "/" in trusted:  # CIDR notation (simplified check)
            network, prefix = trusted.split("/")
            if ip.startswith(network.rstrip("0").rstrip(".")):  # ← broken logic
                return True
```

The `rstrip("0").rstrip(".")` transformation produces:
- `10.0.0.0/8` → `"10."` → correctly matches `10.x.x.x` but **also matches** `100.x.x.x`, `101.x.x.x` … `109.x.x.x`
- `172.16.0.0/12` → `"172.16."` → matches `172.16.x.x` but **misses** `172.17.x.x` through `172.31.x.x`

An attacker on `100.64.x.x` (CGNAT space, public internet) can spoof `X-Forwarded-For` to bypass per-IP rate limiting entirely.

**Fix:** Use the Python standard library:
```python
import ipaddress

TRUSTED_PROXY_NETS = [
    ipaddress.ip_network("127.0.0.1/32"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
]

def is_trusted_proxy(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in net for net in TRUSTED_PROXY_NETS)
    except ValueError:
        return False
```

---

#### BUG-C06 — Payment amount hardcoded; mock detection embeds a specific Stripe key prefix

| Field | Detail |
|-------|--------|
| **Severity** | Critical |
| **File** | `app/routes/payments.py` |
| **Lines** | 53–59 |

**Expected:** Payment amount calculated from the request `items`; mock vs. live mode determined by environment variable, not by source-code key matching.

**Actual:**
```python
amount = 9900  # $99.00 in cents — hardcoded regardless of items

if settings.stripe_secret_key.startswith("sk_test_4eC39H"):
    return PaymentIntentCreateResponse(
        clientSecret="pi_3MtwBwLkdIwHu7ix28a3tqPa_secret_a1b2c3d4e5f6g7h8i9j0"
    )
```

Problems:
1. The `items` parameter is accepted but **never used** to calculate the amount.
2. The mock detection string `"sk_test_4eC39H"` is the prefix of the **specific Stripe key committed to `.env`** — a coupling between source code and a credential.
3. The mock `clientSecret` is a hardcoded literal string. A frontend using this will attempt to confirm a non-existent PaymentIntent and fail silently or produce confusing Stripe errors.
4. Any future Stripe key rotation that keeps the same prefix silently activates mock mode in production.

**Fix:** Calculate amount server-side from a product catalogue. Use `ENVIRONMENT != "production"` (or a dedicated `STRIPE_MOCK_ENABLED` flag) for mock detection. Use Stripe's official test mode for integration testing.

---

### 3.2 High Severity

---

#### BUG-H01 — `logout-access` hard-fails when Redis is unavailable

| Field | Detail |
|-------|--------|
| **Severity** | High |
| **File** | `app/routes/auth.py:243–246`, `app/services/auth_manager.py:307–312` |

**Expected:** Logout always succeeds or degrades gracefully.

**Actual:**
```python
revoked = await auth_manager.revoke_access_token(access_token)
if not revoked:
    raise InvalidTokenError("Access token could not be revoked")
```

`revoke_access_token` returns `False` when `self.redis is None` (Redis unavailable). The route converts `False` into HTTP 400/401. Users cannot log out during a Redis outage.

**Fix:** Accept `False` from `revoke_access_token` when Redis is unavailable and return HTTP 204 with a logged warning. Short-lived access tokens (30 min) provide the fallback guarantee. Logout must never be harder than login.

---

#### BUG-H02 — Token revocation not checked in authentication middleware

| Field | Detail |
|-------|--------|
| **Severity** | High |
| **File** | `app/middleware/authentication.py:266` |

**Actual:** The comment explicitly documents the omission:
```python
# Note: Redis revocation check is skipped in middleware for performance
# Access tokens are short-lived, so revocation is less critical
```

The full-service `AuthManager.verify_token()` checks Redis for revoked JTIs. The middleware's `_blocking_verify_token()` skips this check. A token explicitly revoked via `POST /v1/auth/logout-access` continues to authenticate requests for up to 30 minutes.

**Fix:** Accept the documented risk in a security design document (ADR), or perform the async Redis JTI check inside the existing `run_in_executor` call in `_verify_token`. The infrastructure is already in place.

---

#### BUG-H03 — CSRF protection inconsistency: DELETE always protected, JWT POST is not

| Field | Detail |
|-------|--------|
| **Severity** | High |
| **File** | `app/middleware/csrf.py:92–111` |

**Actual:**
```python
if request.method == "DELETE":
    return True   # always require CSRF for DELETE

if request.headers.get("authorization", "").startswith("Bearer "):
    return False  # skip CSRF for Bearer-authenticated POST/PUT/PATCH
```

`DELETE /v1/sessions/{id}` from a JavaScript client that sends `Authorization: Bearer ...` receives HTTP 403 `CSRF_TOKEN_MISSING` because the `method == "DELETE"` carve-out fires before the Bearer-token exemption. This breaks all `DELETE` endpoints for standard API clients, requiring them to also manage CSRF cookies.

**Fix:** Reorder the checks — exempt all requests with a valid `Bearer` token from CSRF validation (REST APIs using JWT are not CSRF-vulnerable since cross-origin JavaScript cannot read HTTP-only cookies):
```python
if request.headers.get("authorization", "").startswith("Bearer "):
    return False  # JWT-authenticated REST calls: no CSRF needed
if request.method == "DELETE":
    return True   # form-based DELETE: protect
```

---

#### BUG-H04 — Webhook SSRF: DNS rebinding (TOCTOU between validation and delivery)

| Field | Detail |
|-------|--------|
| **Severity** | High |
| **File** | `app/services/webhook_manager.py:82–102` |

**Actual:** `_validate_webhook_url` resolves the hostname via `socket.getaddrinfo()` at request time and checks the resulting IPs against private ranges. The actual HTTP delivery via `aiohttp` resolves the hostname again (seconds or minutes later, especially after Celery retry delays). A DNS rebinding attack changes the DNS record between validation and delivery.

**Fix:** Pin the resolved IP at validation time and pass it to `aiohttp` via a custom resolver (`aiohttp.TCPConnector` with a pre-resolved address), or route all outbound webhook traffic through a dedicated egress proxy with an IP allowlist.

---

#### BUG-H05 — Expired API keys fetched from DB before expiry check

| Field | Detail |
|-------|--------|
| **Severity** | High |
| **File** | `app/middleware/authentication.py:317–344` |

**Actual:** The DB query filters only `is_active=True` but not `expires_at > now`. Expired keys (that were not explicitly deactivated) are fetched and put through a bcrypt comparison before being rejected. This wastes CPU time (bcrypt is intentionally slow) and increases timing-attack surface.

**Fix:** Add expiry filter at the query level:
```python
from sqlalchemy import or_
from datetime import datetime, timezone

now = datetime.now(timezone.utc)
active_keys = (
    db.query(APIKey)
    .filter(
        APIKey.is_active.is_(True),
        APIKey.key_prefix == prefix,
        or_(APIKey.expires_at.is_(None), APIKey.expires_at > now),
    )
    .all()
)
```

---

#### BUG-H06 — Default user credentials printed to stdout

| Field | Detail |
|-------|--------|
| **Severity** | High |
| **File** | `app/database/connection.py:122–128` |

**Actual:**
```python
if sys.stdout.isatty():
    print(f"Username: {secure_username}")
    print(f"Password: {secure_password}")
```

In Docker deployments with a pseudo-TTY (`docker run -it`), the password prints in plain text. CI pipelines that attach a TTY to capture stdout also log it. The `isatty()` guard is not a reliable security control.

**Fix:** Remove the `print` block. Write credentials to a secure file (`pathlib.Path("/run/secrets/default_user").write_text(...)` with mode 0600), or log via the structured logger at WARNING level without the plain-text password.

---

#### BUG-H07 — Payment route exposes raw Stripe exception messages to clients

| Field | Detail |
|-------|--------|
| **Severity** | High |
| **File** | `app/routes/payments.py:73–78` |

**Actual:**
```python
except Exception as e:
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(e),   # ← raw Stripe exception, may contain internal URLs/IDs
    )
```

Stripe exceptions include internal request IDs, partial API key fragments, and endpoint URLs in their string representations.

**Fix:** Return a generic message and log the full exception internally:
```python
logger.error("Stripe PaymentIntent creation failed", exc_info=True)
raise HTTPException(status_code=500, detail="Payment service temporarily unavailable")
```

---

#### BUG-H08 — Exponential retry backoff has no jitter (thundering herd risk)

| Field | Detail |
|-------|--------|
| **Severity** | High |
| **File** | `app/services/task_executor.py` (retry logic), `app/services/webhook_manager.py:150` |

**Actual:** Webhook retry delays `[5, 30, 300, 1800, 3600]` are deterministic. When many tasks fail simultaneously (downstream outage), all retries fire at identical timestamps, producing correlated load spikes on recovery.

**Fix:** Add ±20 % random jitter:
```python
import random
delay = delay * random.uniform(0.8, 1.2)
```

---

#### BUG-H09 — Task dependency cycle not prevented at insertion time

| Field | Detail |
|-------|--------|
| **Severity** | High |
| **File** | `app/database/models.py` (`TaskDependency`), `app/routes/tasks.py` |

**Actual:** The `TaskDependency` model allows any two task IDs to be linked. No cycle-detection query is performed when a new dependency is inserted. A cycle (A → B → A) causes the task executor to loop indefinitely when resolving dependencies.

**Fix:** On dependency creation, perform a depth-first search from the proposed dependency target back to the source using existing `TaskDependency` records. Reject with HTTP 409 if a cycle would be introduced.

---

#### BUG-H10 — Successful logins not written to `AuditLog`

| Field | Detail |
|-------|--------|
| **Severity** | High |
| **File** | `app/routes/auth.py:76–93` |

**Actual:** Only failed logins trigger a structured log entry. Successful logins call `create_tokens_for_user` immediately without recording to the `AuditLog` table. The `AuditLog` model exists and is used elsewhere but is not used in the auth path. This prevents SIEM/anomaly detection (impossible travel, credential stuffing success rate).

**Fix:** Insert an `AuditLog` record for every authentication event (success and failure) including `user_id`, source IP, user-agent, and timestamp.

---

#### BUG-H11 — `logout-access` rejects tokens that lack a JTI

| Field | Detail |
|-------|--------|
| **Severity** | High |
| **File** | `app/services/auth_manager.py:325–327`, `app/routes/auth.py:245–246` |

**Actual:**
```python
if not jti:
    logger.warning("Access token has no JTI, cannot revoke")
    return False   # → route raises InvalidTokenError → HTTP 400
```

A user attempting to log out with a pre-JTI token (issued before the JTI feature was added) receives an error instead of a successful logout. Their session cannot be terminated via this endpoint.

**Fix:** Return `True` (success) when no JTI is present — if the token cannot be individually tracked, the logout intent is satisfied by informing the client to discard it. The token will expire naturally within the TTL.

---

#### BUG-H12 — CSP allows `unsafe-inline` and `unsafe-eval`

| Field | Detail |
|-------|--------|
| **Severity** | High |
| **File** | `app/middleware/security_headers.py:67–70` |

**Actual:**
```python
"script-src 'self' 'unsafe-inline' 'unsafe-eval'; "  # Allow for admin interfaces
"style-src 'self' 'unsafe-inline'; "
```

`'unsafe-inline'` and `'unsafe-eval'` disable CSP's primary XSS mitigation. Any injected inline `<script>` or `eval()` call will execute in the page context.

**Fix:** Use nonces or SHA-256 hashes instead of `unsafe-inline`. Remove `unsafe-eval`. If the admin interface genuinely requires `eval`, apply a separate, stricter CSP header only on `/docs` and `/redoc` paths.

---

#### BUG-H13 — Default `HOST=0.0.0.0` binds to all network interfaces

| Field | Detail |
|-------|--------|
| **Severity** | High |
| **File** | `app/config.py:45`, `.env:2` |

**Actual:** `HOST=0.0.0.0` is set in `.env` and as the `config.py` default. Running locally exposes the API on all LAN interfaces. `app/main.py:375` correctly defaults `__main__` execution to `127.0.0.1`, but this is overridden by the `HOST` env var when run via `uvicorn app.main:app` directly (the standard Docker entrypoint).

**Fix:** Set `HOST=127.0.0.1` in `.env.development`. Set `HOST=0.0.0.0` only in the Docker/production environment file. Update `config.py` default to `127.0.0.1`.

---

### 3.3 Medium Severity

---

#### BUG-M01 — Passwords silently truncated at 72 bytes (bcrypt limit)

| Field | Detail |
|-------|--------|
| **Severity** | Medium |
| **File** | `app/services/auth_manager.py:125–131` |

**Actual:** Passwords longer than 72 UTF-8 bytes are silently truncated before hashing. Two passwords that share the same first 72 bytes are treated as identical. Users setting long passphrases receive no warning.

**Fix:** Either pre-hash with SHA-256 before bcrypt (full entropy preserved), switch to Argon2 (`argon2-cffi`), or reject passwords longer than 72 bytes with a clear validation error.

---

#### BUG-M02 — `WEBHOOK_SECRET_KEY` not required in non-production environments

| Field | Detail |
|-------|--------|
| **Severity** | Medium |
| **File** | `app/config.py:313–318`, `app/services/webhook_manager.py:220–227` |

**Actual:** When the webhook secret is absent in development/staging, webhook deliveries are sent **without an HMAC signature** (`X-Signature-256` header is omitted). Webhook consumers cannot verify authenticity in any non-production environment.

**Fix:** Require `WEBHOOK_SECRET_KEY` in all environments, or refuse to queue deliveries when the key is absent (fail-closed).

---

#### BUG-M03 — No per-user session count cap

| Field | Detail |
|-------|--------|
| **Severity** | Medium |
| **File** | `app/middleware/rate_limiting.py:48–56` |

**Actual:** Rate limits constrain the *rate* of session creation (10/min per user) but not the *total count*. A single authenticated user can create an unbounded number of sessions over time, exhausting the database.

**Fix:** Add a configurable per-user session cap enforced at session creation time. Recommended default: `MAX_SESSIONS_PER_USER=50`.

---

#### BUG-M04 — `get_db()` dependency does not explicitly rollback on exception

| Field | Detail |
|-------|--------|
| **Severity** | Medium |
| **File** | `app/database/connection.py:156–173` |

**Actual:**
```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

SQLAlchemy rolls back on `db.close()` with `autocommit=False`, so this is safe — but partial writes can remain pending until close, masking bugs. Explicit rollback on exception is a clearer, safer pattern.

**Fix:**
```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

---

#### BUG-M05 — Synchronous SQLAlchemy ORM called in `async def` route handlers

| Field | Detail |
|-------|--------|
| **Severity** | Medium |
| **File** | All route files (`app/routes/*.py`) |

**Actual:** Routes are declared `async def` but call synchronous SQLAlchemy ORM methods (`db.query(...).first()`, `db.commit()`, etc.) directly, blocking the asyncio event loop. Under concurrent load the thread pool can become saturated.

**Fix:** Either migrate to `sqlalchemy.ext.asyncio` (`AsyncSession`), or wrap all DB calls with `await run_in_executor(None, sync_func)`. The middleware already demonstrates this pattern for token verification.

---

#### BUG-M06 — Session `custom_config` accepted without schema validation

| Field | Detail |
|-------|--------|
| **Severity** | Medium |
| **File** | `app/services/session_manager.py` |

**Actual:** Session creation accepts a `custom_config` dict that is deep-merged into the APGI system config without schema validation. Arbitrary keys and deeply nested values can be injected.

**Fix:** Define a Pydantic model for `custom_config` with `extra="forbid"` and validate before merging.

---

#### BUG-M07 — No idempotency key support on mutating endpoints

| Field | Detail |
|-------|--------|
| **Severity** | Medium |
| **File** | All POST/PUT routes |

**Actual:** Network retries create duplicate resources (sessions, tasks, API keys, webhook deliveries). There is no `Idempotency-Key` mechanism.

**Fix:** Accept an `Idempotency-Key` header on all mutating endpoints. Cache the response keyed by `(user_id, idempotency_key)` in Redis with a 24-hour TTL. Return the cached response on duplicate requests.

---

#### BUG-M08 — `instrument_application()` is a dead no-op in `main.py`

| Field | Detail |
|-------|--------|
| **Severity** | Medium |
| **File** | `app/main.py:355–362` |

**Actual:**
```python
def instrument_application():
    """Placeholder - instrumentation now happens in lifespan."""
    pass
```

This function is defined, called, and wrapped in a `try/except ImportError` block that implies a dependency. All three are dead code left from a refactor. The misleading docstring suggests instrumentation happens elsewhere, but it does not.

**Fix:** Delete the function, its call site, and the surrounding `try/except`.

---

### 3.4 Low Severity

---

#### BUG-L01 — `Strict-Transport-Security` header sent over plaintext HTTP

| Field | Detail |
|-------|--------|
| **Severity** | Low |
| **File** | `app/middleware/security_headers.py:42` |

`Strict-Transport-Security: max-age=31536000; includeSubDomains; preload` is unconditionally added to every response, including development HTTP responses. Browsers that honour HSTS preload will refuse subsequent HTTP connections to the domain for one year.

**Fix:** Omit the HSTS header (or set `max-age=0`) when `ENVIRONMENT != "production"` or when the request was not received over TLS.

---

#### BUG-L02 — `RateLimitingMiddleware._instance` singleton is not thread-safe

| Field | Detail |
|-------|--------|
| **Severity** | Low |
| **File** | `app/middleware/rate_limiting.py:31,63` |

The class-level `_instance` attribute is set during `__init__` and read from a class method without a lock. Under test parallelism or multi-threaded scenarios the assignment is a race condition.

**Fix:** Use `threading.Lock` around the assignment, or replace the singleton pattern with dependency injection via FastAPI `Depends`.

---

#### BUG-L03 — `pool_size` / `max_overflow` not formally declared in `Settings`

| Field | Detail |
|-------|--------|
| **Severity** | Low |
| **File** | `app/database/connection.py:36–41` |

```python
pool_size=getattr(settings, "pool_size", 20),
```

These use `getattr` with fallback defaults, meaning they cannot be configured via environment variable in any discoverable way — operators setting `POOL_SIZE=10` in the environment have no effect.

**Fix:** Add `pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle` as proper `Settings` attributes with `os.getenv(...)`.

---

#### BUG-L04 — Inconsistent error response envelope across routes

| Field | Detail |
|-------|--------|
| **Severity** | Low |
| **File** | Multiple route files |

Three different error shapes are returned:
- Middleware: `{"error": {"code": ..., "message": ..., "timestamp": ...}}`
- FastAPI default: `{"detail": "..."}`
- Some custom exceptions: `{"error": "...", "detail": "..."}`

API clients must handle all three shapes.

**Fix:** Standardise all error responses through `app/exception_handlers.py` using a single envelope schema. Register handlers for `HTTPException`, `RequestValidationError`, and all custom exception types.

---

#### BUG-L05 — Request ID not propagated to downstream log records

| Field | Detail |
|-------|--------|
| **Severity** | Low |
| **File** | `app/middleware/logging.py` |

The logging middleware generates per-request IDs but does not inject them into the `StructuredLogger` context for log records emitted by service or database layers within that request's lifetime.

**Fix:** Use `contextvars.ContextVar` to store the request ID at middleware entry, then include it automatically in all `StructuredLogger` records emitted within that context.

---

## 4. Missing Features Log

| ID | Feature | Expected Behaviour | Current State | Priority |
|----|---------|-------------------|---------------|----------|
| MF-01 | **Password reset flow** | `POST /v1/users/reset-password` accepts email and sends a time-limited token; `POST /v1/users/reset-password/confirm` accepts token + new password | Email verification exists; no password reset endpoints implemented | High |
| MF-02 | **API key rotation** | `POST /v1/api-keys/{id}/rotate` generates a new secret, returns it once, invalidates the old one atomically | Keys can only be created or deleted; no rotation endpoint | High |
| MF-03 | **Webhook dead-letter management** | Admin endpoint to list, retry, and purge dead-letter webhook deliveries | `WebhookDelivery.status = "dead_letter"` is set in code but no admin endpoint exposes or reprocesses them | Medium |
| MF-04 | **Server-side payment amount calculation** | Amount derived from a product catalogue keyed by `items`; not client-supplied | `amount` hardcoded at `9900` cents; `items` list ignored | High |
| MF-05 | **Stripe webhook handler** | `POST /v1/payments/webhook` validates `Stripe-Signature` HMAC and processes events (refunds, disputes, subscriptions) | No Stripe webhook endpoint exists | High |
| MF-06 | **Atomic session state transitions** | Concurrent `STOP` calls on the same session produce exactly one state change | State check and update are separate ORM operations with no `SELECT FOR UPDATE` or optimistic locking | Medium |
| MF-07 | **MFA recovery codes** | On TOTP enrolment, generate a set of one-time backup codes in case device is lost | MFA enrolment exists (`/v1/users/mfa/enroll`) but no backup/recovery code mechanism | Medium |
| MF-08 | **OpenTelemetry trace export** | Distributed traces propagated to Celery tasks and outbound HTTP calls, exported to a collector | `configure_distributed_tracing()` called but `instrument_application()` is a no-op; no actual spans exported | Low |
| MF-09 | **Operations runbook** | `DEPLOYMENT.md` with pre-flight checklist, secrets rotation SOP, rollback steps, backup/restore procedure | No deployment documentation exists beyond inline README | Medium |
| MF-10 | **Database backup strategy** | Documented automated backup + point-in-time restore procedure | Not documented | Low |

---

## 5. Recommendations

Recommendations are grouped by effort and ordered by priority within each group. Effort labels: **XS** < 1h, **S** = 2–8h, **M** = 1–3 days, **L** = 1+ weeks.

### 5.1 Immediate (Day 0–1) — Do Before Any Further Commits

| # | Recommendation | Bugs / Features | Effort |
|---|---------------|-----------------|--------|
| R-01 | Untrack `.env` from git (`git rm --cached .env`), rotate the Stripe test key via dashboard.stripe.com | BUG-C01 | XS |
| R-02 | Remove `print("DEBUG: no match found")` from `authentication.py:339` | BUG-C02 | XS |
| R-03 | Delete duplicate `from app.routes import (...)` block at `main.py:72–86` | BUG-C04 | XS |
| R-04 | Fix `/v1/users/create-default` — remove from `PUBLIC_PATHS` and enforce auth, or redesign as a one-time bootstrap endpoint | BUG-C03 | S |
| R-05 | Replace naïve CIDR check in `is_trusted_proxy` with `ipaddress` module | BUG-C05 | S |

### 5.2 Sprint 1 (Week 1) — Release-Blocking

| # | Recommendation | Bugs / Features | Effort |
|---|---------------|-----------------|--------|
| R-06 | Implement password reset endpoints (`/reset-password`, `/reset-password/confirm`) | MF-01 | M |
| R-07 | Add API key rotation endpoint | MF-02 | S |
| R-08 | Implement Stripe webhook handler with `Stripe-Signature` validation | MF-05 | M |
| R-09 | Fix CSRF inconsistency — exempt all Bearer-token requests uniformly, including DELETE | BUG-H03 | S |
| R-10 | Write `AuditLog` entries for successful logins and lockout events | BUG-H10 | S |
| R-11 | Fix `logout-access` to return 204 (not error) when Redis is unavailable | BUG-H01 | S |
| R-12 | Replace `unsafe-inline`/`unsafe-eval` in CSP with nonces | BUG-H12 | M |
| R-13 | Return generic message from Stripe error handler; log internally | BUG-H07 | XS |
| R-14 | Fix payment mock detection — use `ENVIRONMENT` flag, not key prefix matching | BUG-C06 | S |
| R-15 | Implement server-side payment amount calculation from product catalogue | MF-04 | M |

### 5.3 Sprint 2 (Weeks 2–3) — Quality and Resilience

| # | Recommendation | Bugs / Features | Effort |
|---|---------------|-----------------|--------|
| R-16 | Add ±20 % jitter to retry backoff in task executor and webhook manager | BUG-H08 | XS |
| R-17 | Add cycle-detection query before inserting `TaskDependency` records | BUG-H09 | M |
| R-18 | Validate `custom_config` in session creation via Pydantic with `extra="forbid"` | BUG-M06 | S |
| R-19 | Implement `Idempotency-Key` support on all mutating POST/PUT endpoints | BUG-M07 | M |
| R-20 | Pre-hash passwords with SHA-256 before bcrypt, or enforce ≤72-byte limit explicitly | BUG-M01 | S |
| R-21 | Add `MAX_SESSIONS_PER_USER` cap enforced at session creation | BUG-M03 | S |
| R-22 | Fix webhook TOCTOU — pin resolved IP at validation and use it at delivery time | BUG-H04 | M |
| R-23 | Declare `pool_size`/`max_overflow` etc. as proper `Settings` attributes | BUG-L03 | XS |
| R-24 | Propagate request IDs via `contextvars.ContextVar` in structured logger | BUG-L05 | S |
| R-25 | Add expiry filter to API key DB query | BUG-H05 | XS |
| R-26 | Delete `instrument_application()` no-op | BUG-M08 | XS |
| R-27 | Add explicit `db.rollback()` on exception in `get_db()` | BUG-M04 | XS |

### 5.4 Backlog

| # | Recommendation | Bugs / Features | Effort |
|---|---------------|-----------------|--------|
| R-28 | Migrate to `sqlalchemy.ext.asyncio` (`AsyncSession`) across all routes | BUG-M05 | L |
| R-29 | Implement MFA recovery codes on enrolment | MF-07 | M |
| R-30 | Wire OpenTelemetry — instrument FastAPI, SQLAlchemy, Redis, aiohttp | MF-08 | M |
| R-31 | Write `DEPLOYMENT.md` with pre-flight checklist and secrets rotation SOP | MF-09 | S |
| R-32 | Standardise error response envelope across all exception handlers | BUG-L04 | M |
| R-33 | Implement atomic session state transitions (SELECT FOR UPDATE or optimistic lock) | MF-06 | M |
| R-34 | Omit HSTS header when serving over plaintext HTTP | BUG-L01 | XS |
| R-35 | Implement dead-letter webhook admin endpoint (list / retry / purge) | MF-03 | M |
| R-36 | Change `HOST` default to `127.0.0.1` in development config | BUG-H13 | XS |
| R-37 | Remove or secure `create_default_user()` credential print block | BUG-H06 | S |

---

## 6. Appendix — Positive Findings

The following security and quality controls were found to be correctly implemented and should be preserved in any refactor:

| Area | What Is Done Well | File / Lines |
|------|------------------|--------------|
| Password hashing | bcrypt with cost factor 12 and per-hash salt | `auth_manager.py:130` |
| JWT algorithm allowlist | Explicit `algorithms=["HS256"]` prevents `alg:none` downgrade attacks | `auth_manager.py:258` |
| Refresh token rotation | Old token revoked on every refresh; only one valid refresh token per user at a time | `auth_manager.py:544–561` |
| Account lockout | 5 failed attempts → 15-minute lockout; atomic DB update with proper rollback | `auth_manager.py:389–400` |
| MFA / TOTP | `pyotp` with window verification; secret stored per-user; QR provisioning URI generated | `auth_manager.py:158–172` |
| Access token revocation | JTI-based blocklist in Redis with TTL equal to remaining token lifetime | `auth_manager.py:296–348` |
| Webhook SSRF blocklist | RFC 1918, loopback, link-local, IPv6 private ranges, and cloud metadata endpoints all blocked | `webhook_manager.py:35–44` |
| HMAC webhook signature | `X-Signature-256` header generated; constant-time `hmac.compare_digest` used in delivery | `webhook_manager.py:221–225` |
| API key prefix lookup | HMAC prefix for fast DB lookup reduces bcrypt calls to near O(1) | `authentication.py:308–334` |
| Connection pooling | `pool_pre_ping=True`, configurable pool size, `pool_recycle`, and overflow management | `connection.py:36–41` |
| Security headers | HSTS, X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy, Permissions-Policy, CORP/COOP/COEP | `security_headers.py:40–64` |
| Request size limiting | Configurable hard cap (default 10 MB) as first middleware in the stack | `request_size_limit.py` |
| Redis-backed rate limiting | Per-endpoint limits, per-user keying, authenticated users separate from anonymous | `rate_limiting.py` |
| CORS wildcard + credentials guard | `Settings.__post_init__` raises `ValueError` in production if wildcard origins and credentials both enabled | `config.py:337–343` |
| Docker non-root user | Container runs as `appuser`, not `root` | `deployment/Dockerfile` |
| Soft deletes | `User.is_deleted` flag prevents accidental data loss | `models.py:97` |
| Structured logging | JSON-compatible structured logger with component/context fields throughout | `middleware/logging.py` |
| Dependency injection | Services injected via FastAPI `Depends`; no hidden global singletons in route handlers | Throughout |
| Property-based tests | Hypothesis with `dev` / `ci` / `thorough` profiles; integration and load tests present | `tests/` |
| Insecure key detection | `Settings.__post_init__` detects known-bad JWT/cursor/webhook keys and raises on startup | `config.py:251–334` |

---

*Report generated via automated full-codebase inspection. All line numbers reference the state of the codebase on 2026-03-09 (branch `claude/app-audit-security-PtO9y`). Verify against current HEAD before acting on specific line references.*
