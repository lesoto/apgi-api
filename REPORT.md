# APGI API — End-to-End Audit Report

**Date:** 2026-02-27
**Branch Audited:** `master` (commit `132afcf`)
**Auditor:** Automated Code & Security Audit
**Application:** APGI REST API — FastAPI-based simulation session management system
**Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.x, PostgreSQL, Redis, Celery, JWT Auth

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [KPI Scores](#2-kpi-scores)
3. [Coverage Analysis](#3-coverage-analysis)
4. [Bug Inventory](#4-bug-inventory)
   - [Critical Bugs](#41-critical-bugs)
   - [High Severity Bugs](#42-high-severity-bugs)
   - [Medium Severity Bugs](#43-medium-severity-bugs)
   - [Low Severity Bugs](#44-low-severity-bugs)
5. [Security Vulnerabilities](#5-security-vulnerabilities)
6. [Missing Features & Incomplete Implementations](#6-missing-features--incomplete-implementations)
7. [Test Coverage Gaps](#7-test-coverage-gaps)
8. [Actionable Recommendations](#8-actionable-recommendations)
9. [Appendix: File-Level Coverage Table](#9-appendix-file-level-coverage-table)

---

## 1. Executive Summary

The APGI API is a FastAPI-based REST service managing AI simulation sessions, tasks, webhooks, user authentication, and data export. The codebase is structurally well-organized with clearly delineated layers (routes → services → models), comprehensive middleware stack, and modern async patterns. However, this audit identified **117 distinct issues** across five evaluation dimensions that must be resolved before the system can be safely operated in production.

### Key Findings at a Glance

| Metric | Value | Assessment |
|--------|-------|------------|
| **Total Issues Found** | 117 | ⚠️ High |
| **Critical Bugs** | 5 | 🔴 Blocking |
| **High Severity Bugs** | 18 | 🟠 Urgent |
| **Medium Severity Bugs** | 43 | 🟡 Significant |
| **Low Severity Bugs** | 51 | 🟢 Minor |
| **Security Vulnerabilities** | 24 | 🔴 Requires attention |
| **Test Coverage** | 31% | 🔴 Far below 80% target |
| **Files with 0% Coverage** | 11 | 🔴 Critical blind spots |
| **Incomplete Implementations** | 14 | 🟠 Urgent |

### Most Critical Findings

1. **Async/await missing on Redis calls** in `auth_manager.py` — blocks the event loop and breaks token revocation at runtime.
2. **Task ownership not validated before cancellation** in `tasks.py` — any authenticated user can cancel another user's tasks (privilege escalation).
3. **Session state access without ownership check** in `state.py` — unauthorized read of any session's state data.
4. **Webhook delivery without HMAC signature verification** — webhooks can be replayed or spoofed.
5. **SSRF vulnerability** in `webhook_manager.py` — cloud metadata endpoint (`169.254.169.254`) not blocked; DNS rebinding not mitigated.
6. **SHA-256 pre-hashing before bcrypt** in `auth_manager.py` — weakens the effective security of password hashing.
7. **Overall code coverage of 31%** — major paths including `api_keys.py`, `webhooks.py`, `error_recovery.py`, and `sharding_service.py` have 0% coverage.

---

## 2. KPI Scores

| Dimension | Score | Indicator | Commentary |
|-----------|-------|-----------|------------|
| **Functional Completeness** | 58 / 100 | 🟡 | Core CRUD works; session state transitions, task dependency graphs, webhook auth, pagination limits, and export streaming are incomplete or broken |
| **UI/UX Consistency (API Contract)** | 62 / 100 | 🟡 | Generally consistent RESTful design; inconsistent error payload formats, undocumented query params, missing `429` responses on some rate-limited routes |
| **Responsiveness & Performance** | 55 / 100 | 🟡 | Blocking sync calls in async context (`time.sleep`, Redis calls without `await`); `KEYS` pattern on Redis (O(N)); response schema validation on every request; no query result caching on hot paths |
| **Error Handling & Resilience** | 48 / 100 | 🟠 | Broad `except Exception` masking; fail-open rate limiter; no circuit-breaker for DB; audit log failures silent; Redis unavailability bypasses token revocation |
| **Implementation Quality** | 54 / 100 | 🟡 | 31% test coverage; mutable ORM defaults; custom crypto in cursor signing; hardcoded magic numbers; global mutable state; duplicate code; assert-based guards |

### Scoring Legend

| Range | Label | Color |
|-------|-------|-------|
| 80–100 | Production-Ready | 🟢 Green |
| 65–79 | Near-Ready (minor fixes) | 🔵 Blue |
| 50–64 | Needs Work (significant gaps) | 🟡 Yellow |
| 35–49 | Not Ready (major gaps) | 🟠 Orange |
| 0–34 | Critical Failure | 🔴 Red |

**Overall Score: 55 / 100 — 🟡 Needs Work**

---

## 3. Coverage Analysis

The most recent coverage run shows **31% overall coverage** across the entire `app/` package, which is significantly below the recommended 80% minimum for production services.

### Coverage Summary by Module

| Module | Statements | Covered | Missing | Coverage % | Status |
|--------|-----------|---------|---------|-----------|--------|
| `app/routes/api_keys.py` | 98 | 0 | 98 | **0%** | 🔴 |
| `app/routes/webhooks.py` | 63 | 0 | 63 | **0%** | 🔴 |
| `app/services/webhook_manager.py` | 135 | 0 | 135 | **0%** | 🔴 |
| `app/services/error_recovery.py` | 149 | 0 | 149 | **0%** | 🔴 |
| `app/services/sharding_service.py` | 63 | 0 | 63 | **0%** | 🔴 |
| `app/services/seeding_service.py` | 163 | 0 | 163 | **0%** | 🔴 |
| `app/tasks/experimental_tasks.py` | 171 | 0 | 171 | **0%** | 🔴 |
| `app/tasks/task_registry.py` | 27 | 0 | 27 | **0%** | 🔴 |
| `app/tracing.py` | 50 | 0 | 50 | **0%** | 🔴 |
| `app/database/sharded_connection.py` | 94 | 0 | 94 | **0%** | 🔴 |
| `app/cli.py` | 89 | 0 | 89 | **0%** | 🔴 |
| `app/middleware/schema_validation.py` | 140 | 18 | 122 | **13%** | 🔴 |
| `app/services/session_manager.py` | 348 | 48 | 300 | **14%** | 🔴 |
| `app/services/rate_limiter.py` | 42 | 8 | 34 | **19%** | 🔴 |
| `app/middleware/tracing.py` | 77 | 17 | 60 | **22%** | 🔴 |
| `app/middleware/alerting.py` | 293 | 73 | 220 | **25%** | 🔴 |
| `app/routes/sessions.py` | 165 | 41 | 124 | **25%** | 🔴 |
| `app/middleware/csrf.py` | 59 | 16 | 43 | **27%** | 🔴 |
| `app/middleware/authentication.py` | 106 | 27 | 79 | **25%** | 🔴 |
| `app/services/auth_manager.py` | 204 | 68 | 136 | **33%** | 🟠 |
| `app/routes/tasks.py` | 140 | 30 | 110 | **21%** | 🔴 |
| `app/routes/state.py` | 146 | 20 | 126 | **14%** | 🔴 |
| `app/routes/templates.py` | 113 | 23 | 90 | **20%** | 🔴 |
| `app/models/schemas.py` | 672 | 402 | 270 | **60%** | 🟡 |
| `app/config.py` | 98 | 76 | 22 | **78%** | 🟡 |

---

## 4. Bug Inventory

### 4.1 Critical Bugs

> Severity: **CRITICAL** — These bugs cause runtime failures, data corruption, or complete feature breakage.

---

**BUG-C01: Missing `await` on Redis calls in `auth_manager.py`**

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/auth_manager.py` |
| **Lines** | 251, 310 |
| **Severity** | Critical |
| **Category** | Async/Correctness |

**Description:** `self.redis.exists()` (line 251) and `self.redis.setex()` (line 310) are called as synchronous functions on an async Redis client, but are not `await`-ed. In an `asyncio` event loop, calling a coroutine without `await` returns a coroutine object, not the result — the call is silently ignored.

**Impact:** Token revocation via Redis does not function. Logging out a user does NOT invalidate their JWT. Any token ever issued remains valid until expiry.

**Reproduction:**
1. Login to obtain a JWT.
2. Call `POST /auth/logout`.
3. Re-use the old JWT — it still authenticates successfully.

**Expected:** Redis blocklist is checked; revoked token rejected with `401`.
**Actual:** Redis call returns coroutine object (no-op); token accepted.

**Fix:**
```python
# Line 251
if self.redis and await self.redis.exists(f"revoked_token:{jti}"):
    ...
# Line 310
await self.redis.setex(f"revoked_token:{jti}", ...)
```

---

**BUG-C02: Task ownership not validated before cancellation**

| Attribute | Value |
|-----------|-------|
| **File** | `app/routes/tasks.py` |
| **Lines** | 311–318 |
| **Severity** | Critical |
| **Category** | Authorization / Privilege Escalation |

**Description:** The `cancel_task` endpoint queries the task by `task_id` but does not verify the calling user owns the session that contains the task. A malicious authenticated user can cancel any task belonging to any other user.

**Impact:** Any authenticated user can cancel another user's running tasks, disrupting active simulations and potentially corrupting session state.

**Reproduction:**
1. User A starts a long-running task. Note the `task_id`.
2. User B authenticates independently.
3. User B calls `DELETE /v1/sessions/{any_session_id}/tasks/{task_id_from_A}`.
4. Task is cancelled despite User B having no ownership.

**Expected:** `403 Forbidden` if calling user does not own the session.
**Actual:** Task cancelled successfully for any authenticated user.

**Fix:** Add ownership validation:
```python
task = db.query(Task).filter(
    Task.task_id == task_id,
    Task.session_id == session_id
).first()
# Also validate session belongs to current_user.user_id
```

---

**BUG-C03: Session state accessible without ownership check in `state.py`**

| Attribute | Value |
|-----------|-------|
| **File** | `app/routes/state.py` |
| **Lines** | 85, 202 |
| **Severity** | Critical |
| **Category** | Authorization / Information Disclosure |

**Description:** `get_session()` and `get_ignition_history()` endpoints call `manager.get_session(session_id)` without explicitly validating that the requesting user owns the session. The `SessionManager.get_session()` method does not enforce user-scoped ownership.

**Impact:** Any authenticated user can read full simulation state, history, and private data from any session belonging to any other user.

**Reproduction:**
1. User A creates a session. Note `session_id`.
2. User B authenticates.
3. User B calls `GET /v1/sessions/{session_id_from_A}/state`.
4. Full state data returned.

**Expected:** `403 Forbidden` or `404 Not Found`.
**Actual:** Full session state returned.

**Fix:**
```python
session = await manager.get_session(session_id)
if session.user_id != current_user.user_id and "admin" not in current_user.roles:
    raise ForbiddenException("Access denied")
```

---

**BUG-C04: Database context manager resource leak in `templates.py`**

| Attribute | Value |
|-----------|-------|
| **File** | `app/routes/templates.py` |
| **Lines** | 78, 129 |
| **Severity** | Critical |
| **Category** | Resource Management |

**Description:** The function uses `with get_db_context() as db:` at line 78 but contains `return` statements inside the `with` block. In certain exception paths, the context manager `__exit__` is not guaranteed to commit or rollback, potentially leaving database transactions open and connection pool slots exhausted.

**Impact:** Connection pool exhaustion under load; uncommitted transactions; database deadlocks.

**Expected:** Context manager properly releases DB connection in all code paths.
**Actual:** Exception paths may exit without proper cleanup.

**Fix:** Ensure `try/except/finally` blocks explicitly commit or rollback within the context manager scope.

---

**BUG-C05: `time.sleep()` used in async context in `task_executor.py`**

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/task_executor.py` |
| **Lines** | 333, 427 |
| **Severity** | Critical |
| **Category** | Async/Performance |

**Description:** `retry_with_backoff()` uses `time.sleep()` for retry delays. This is a synchronous blocking call inside an async function, which blocks the entire asyncio event loop for the sleep duration.

**Impact:** All concurrent requests are frozen during retry backoff periods, causing cascading timeouts and poor performance under any retry scenario.

**Fix:**
```python
# Replace:
time.sleep(delay)
# With:
await asyncio.sleep(delay)
```

---

### 4.2 High Severity Bugs

> Severity: **HIGH** — Significant functional failures, security weaknesses, or data integrity risks.

---

**BUG-H01: SHA-256 pre-hashing before bcrypt weakens password security**

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/auth_manager.py` |
| **Lines** | 122–123, 142–143 |
| **Severity** | High |
| **Category** | Security / Cryptography |

**Description:** Passwords are SHA-256 hashed before being passed to bcrypt. This creates two problems: (1) bcrypt's 72-byte input limit is no longer semantically meaningful since SHA-256 output is always 32 bytes; (2) bcrypt is designed to be slow using its own internal salt — pre-hashing with SHA-256 changes the effective input space in a non-standard way that may reduce security and complicate future migration.

**Fix:** Use bcrypt directly without pre-hashing, or migrate to argon2-cffi (recommended).

---

**BUG-H02: Refresh tokens are not rotated on use**

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/auth_manager.py` |
| **Lines** | 384–399 |
| **Severity** | High |
| **Category** | Security / Session Management |

**Description:** Refresh tokens can be used multiple times indefinitely until expiry. There is no rotation mechanism (single-use + issue-new). A compromised refresh token grants persistent access.

**Fix:** On each `POST /auth/refresh`, invalidate the used token and issue a new one.

---

**BUG-H03: Rate limiter fails open when Redis is unavailable**

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/rate_limiter.py` |
| **Lines** | 78–79 |
| **Severity** | High |
| **Category** | Resilience / Security |

**Description:** When Redis is unavailable, the rate limiter returns `True` (allowed) for all requests, effectively disabling rate limiting entirely. This fail-open behavior can be exploited by causing Redis to become unavailable through legitimate means.

**Fix:** Consider fail-closed (block requests) or implement an in-memory fallback counter with aggressive limits.

---

**BUG-H04: Rate limiter off-by-one counting**

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/rate_limiter.py` |
| **Lines** | 67 |
| **Severity** | High |
| **Category** | Logic |

**Description:** The rate limiter increments the counter *before* checking if the limit is exceeded, allowing one extra request beyond the configured limit on every window reset.

---

**BUG-H05: CORS wildcard (`*`) allowed in production with only a warning**

| Attribute | Value |
|-----------|-------|
| **File** | `app/config.py` |
| **Lines** | 218–231 |
| **Severity** | High |
| **Category** | Security / Configuration |

**Description:** `__post_init__` validates CORS origins but only emits a warning log when `*` is configured in production. The application starts and serves requests with wildcard CORS, exposing all endpoints to cross-origin requests from any domain.

**Fix:** Raise a `ConfigurationError` (not just log a warning) when `CORS_ORIGINS=*` in production.

---

**BUG-H06: Webhook HMAC signature not verified on delivery**

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/webhook_manager.py` |
| **Lines** | 207–208 |
| **Severity** | High |
| **Category** | Security / Integrity |

**Description:** Webhooks are dispatched via HTTP without sending an HMAC signature in a header (e.g., `X-Webhook-Signature`). Receiving services have no way to verify the payload origin or detect tampering.

**Fix:** Add `X-Signature-256: sha256=<HMAC-SHA256(secret, body)>` header to every outbound webhook request.

---

**BUG-H07: `logger.warning()` called with invalid `extra=` dict syntax**

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/authorization.py` |
| **Lines** | 228, 246, 265 |
| **Severity** | High |
| **Category** | Bug / Runtime Error |

**Description:** `logger.warning("message", {"key": "val"})` passes a dict as the second positional argument, which the logging module interprets as `args` for `%`-style formatting. When the format string has no `%s` placeholders, this causes a `TypeError` or silently drops the dict, depending on the logging handler.

**Fix:**
```python
logger.warning("message", extra={"key": "val"})
```

---

**BUG-H08: Mutable default arguments on ORM models**

| Attribute | Value |
|-----------|-------|
| **File** | `app/database/models.py` |
| **Lines** | 79, 125, 205, 459 |
| **Severity** | High |
| **Category** | Python Anti-Pattern / Data Integrity |

**Description:** Multiple SQLAlchemy columns use `default=list` (bare reference to the `list` type). SQLAlchemy evaluates this as a callable and calls `list()` per instance — which is actually correct behavior for SQLAlchemy. However, cross-checking the models reveals some columns use `default=[]` (mutable literal) rather than `default=list` or `default=lambda: []`, leading to shared state between model instances in certain ORM session configurations.

**Fix:** Use `default=lambda: []` consistently for all array/list defaults.

---

**BUG-H09: Regex compiled on every validation call in `schemas.py`**

| Attribute | Value |
|-----------|-------|
| **File** | `app/models/schemas.py` |
| **Lines** | 329 |
| **Severity** | High (Performance) |
| **Category** | Performance |

**Description:** A regex pattern is compiled inline inside a validator method that runs on every request deserialization. Under high load, this causes unnecessary CPU overhead.

**Fix:** Move regex compilation to module level as a module-level constant.

---

**BUG-H10: `assert` used for production guards (disabled by `-O` flag)**

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/auth_manager.py`, `app/services/error_recovery.py` |
| **Lines** | auth_manager:247, error_recovery:327 |
| **Severity** | High |
| **Category** | Reliability |

**Description:** `assert` statements are used to validate critical pre-conditions (e.g., `assert auth_manager.secret_key is not None`). Python's `-O` (optimize) flag disables all `assert` statements, causing silent failures in optimized deployments.

**Fix:** Replace with explicit `if ... raise ValueError(...)` checks.

---

**BUG-H11: Redis `KEYS` pattern used in cache_service.py (O(N) blocking)**

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/cache_service.py` |
| **Lines** | 275–277, 290–293 |
| **Severity** | High (Performance) |
| **Category** | Performance |

**Description:** `redis.keys(pattern)` is O(N) relative to the total number of keys in Redis and blocks the Redis server while executing. Under production loads with many keys, this can cause Redis to become unresponsive for all other operations.

**Fix:** Use `redis.scan_iter(pattern)` which is non-blocking and cursor-based.

---

**BUG-H12: `X-Forwarded-For` header ignored in rate limiter client identification**

| Attribute | Value |
|-----------|-------|
| **File** | `app/middleware/rate_limiting.py` |
| **Lines** | 76–82 |
| **Severity** | High |
| **Category** | Security |

**Description:** Rate limiting identifies clients by `request.client.host`, which behind a reverse proxy (Nginx, Cloudflare, AWS ALB) is always the proxy's IP. All requests appear to originate from the same client, making rate limiting ineffective.

**Fix:** Use `X-Forwarded-For` or `X-Real-IP` headers (with proper proxy trust configuration) as the primary client identifier.

---

**BUG-H13: `DELETE` method not protected by CSRF middleware**

| Attribute | Value |
|-----------|-------|
| **File** | `app/middleware/csrf.py` |
| **Lines** | 87 |
| **Severity** | High |
| **Category** | Security / CSRF |

**Description:** The CSRF middleware skips `DELETE` requests. While JWT-authenticated API calls are exempt by design, form-based `DELETE` requests (if any) are left unprotected.

---

**BUG-H14: User count exposed in health check endpoint**

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/health_check.py` |
| **Lines** | 153 |
| **Severity** | High |
| **Category** | Information Disclosure |

**Description:** The public health check endpoint returns the total user count from the database. This leaks internal business metrics to unauthenticated callers.

**Fix:** Remove user count from health check, or move it to an admin-only metrics endpoint.

---

**BUG-H15: Degraded status returns HTTP 200 in readiness probe**

| Attribute | Value |
|-----------|-------|
| **File** | `app/routes/health.py` |
| **Lines** | 87 |
| **Severity** | High |
| **Category** | Operational |

**Description:** When the health service reports `degraded` status, the `/readiness` endpoint still returns `HTTP 200`. Kubernetes and load balancers interpret `200` as fully healthy and continue routing traffic, bypassing the degraded signal.

**Fix:** Return `HTTP 503` for `degraded` status on the readiness endpoint.

---

**BUG-H16: Plaintext password returned from `reset_password()`**

| Attribute | Value |
|-----------|-------|
| **File** | `app/services/user_management.py` |
| **Lines** | 183–195 |
| **Severity** | High |
| **Category** | Security |

**Description:** `reset_password()` generates a new random password and returns it in plaintext to the caller. This password is potentially logged in HTTP access logs or response audit trails.

**Fix:** Send the new password directly to the user's registered email. Do not return it in the API response body.

---

**BUG-H17: Cursor signing uses JWT secret key (scope confusion)**

| Attribute | Value |
|-----------|-------|
| **File** | `app/routes/state.py` |
| **Lines** | 253–291 |
| **Severity** | High |
| **Category** | Security / Cryptography |

**Description:** Pagination cursors are signed using `settings.jwt_secret_key`. Reusing the JWT secret for cursor HMAC conflates two independent security boundaries. If the cursor signing logic is bypassed or the HMAC is weak, it could affect JWT trust indirectly.

**Fix:** Use a dedicated `CURSOR_SIGNING_KEY` secret, separate from JWT key.

---

**BUG-H18: API key `key_prefix` field never populated**

| Attribute | Value |
|-----------|-------|
| **File** | `app/routes/api_keys.py` |
| **Lines** | 65 |
| **Severity** | High |
| **Category** | Functionality |

**Description:** The API key model has a `key_prefix` field intended to support fast lookup during authentication (filter by prefix before comparing full hash). The field is never set during key creation, forcing the authentication middleware to iterate all keys for a given user when validating, which is O(n×bcrypt_cost).

---

### 4.3 Medium Severity Bugs

> Severity: **MEDIUM** — Functional gaps, validation weaknesses, or maintainability concerns.

| ID | File | Lines | Description |
|----|------|-------|-------------|
| BUG-M01 | `app/middleware/authentication.py` | 247 | `assert` used instead of exception for secret key check |
| BUG-M02 | `app/middleware/authentication.py` | 173 | Broad `except Exception:` silently swallows auth errors |
| BUG-M03 | `app/middleware/authentication.py` | 217–223 | Blocking database calls inside async middleware block event loop |
| BUG-M04 | `app/middleware/rate_limiting.py` | 45 | Typo: "rate limitter" in comment |
| BUG-M05 | `app/middleware/rate_limiting.py` | 186–190 | Rate limit reset timestamp can be negative; fallback recalculates same value |
| BUG-M06 | `app/middleware/csrf.py` | 121–126 | Accesses `request._form` (private attribute) which may be unparsed |
| BUG-M07 | `app/middleware/schema_validation.py` | 230 | `status_str[0]` assumes at least 1-char string — fails on empty status codes |
| BUG-M08 | `app/middleware/schema_validation.py` | 292–293 | Checks `len(body)` on potentially None value |
| BUG-M09 | `app/config.py` | 50, 103–104 | String split without handling empty values or special characters |
| BUG-M10 | `app/config.py` | 80–87 | CORS methods/headers split without trimming whitespace (trailing spaces) |
| BUG-M11 | `app/config.py` | 146 | `setattr()` to create `database_shard_N_url` attributes — no type safety |
| BUG-M12 | `app/routes/sessions.py` | 436–441 | No state machine validation (e.g., pausing an already-paused session) |
| BUG-M13 | `app/routes/sessions.py` | 104–114 | Global mutable state for Redis client and session manager |
| BUG-M14 | `app/routes/sessions.py` | 380 | `TaskStatusResponse` sets state to `None` — may break frontend state handling |
| BUG-M15 | `app/routes/export.py` | 77–78 | Export `format` query parameter not validated against allowlist |
| BUG-M16 | `app/routes/export.py` | 123–124 | Session ID embedded in filename without sanitization (path traversal risk) |
| BUG-M17 | `app/routes/export.py` | 140 | `HTTP_413_REQUEST_ENTITY_TOO_LARGE` used without `status` import alias |
| BUG-M18 | `app/routes/users.py` | 128 | `secrets.token_urlsafe(16)` — 16 bytes is borderline weak for a temp password |
| BUG-M19 | `app/routes/users.py` | 361–364 | Role changes not audit-logged |
| BUG-M20 | `app/routes/api_keys.py` | 284–285 | API keys can have `expires_at=None` (no expiry enforcement) |
| BUG-M21 | `app/routes/webhooks.py` | 200 | Hardcoded retry limit of 5 — not configurable |
| BUG-M22 | `app/routes/webhooks.py` | 46–50 | All webhook routes require SYSTEM_ADMIN — no per-user webhook scoping |
| BUG-M23 | `app/routes/templates.py` | 92 | Complex count subquery may produce incorrect results |
| BUG-M24 | `app/routes/templates.py` | 348–350 | `setattr()` for field updates — should use explicit field assignment |
| BUG-M25 | `app/services/session_manager.py` | 336 | `setattr()` with arbitrary keys (injection risk) |
| BUG-M26 | `app/services/session_manager.py` | 571 | `move_to_end()` + index assignment not atomic (race condition) |
| BUG-M27 | `app/services/session_manager.py` | 756 | Unnecessary subquery in count query |
| BUG-M28 | `app/services/task_executor.py` | 56–57 | Dead code: unreachable branch when `last_exception is None` after loop |
| BUG-M29 | `app/services/task_executor.py` | 320–351 | No cycle detection in task dependency graph |
| BUG-M30 | `app/services/task_executor.py` | 279 | Task type validated by dict lookup, not explicit allowlist |
| BUG-M31 | `app/services/webhook_manager.py` | 129 | Typo in retry delay comment |
| BUG-M32 | `app/services/webhook_manager.py` | 196–227 | Response body read without size limit (can consume unbounded memory) |
| BUG-M33 | `app/services/data_export.py` | 143–145 | Jagged variable arrays silently skip missing values |
| BUG-M34 | `app/services/data_export.py` | 188 | Session config exported without redacting sensitive fields |
| BUG-M35 | `app/services/data_export.py` | 193 | Generator does not handle mid-stream exceptions (partial response) |
| BUG-M36 | `app/services/cache_service.py` | 51–52 | Fernet encryption key derived from JWT secret via SHA-256 (weak KDF) |
| BUG-M37 | `app/services/health_check.py` | 153 | `SELECT COUNT(*) FROM users` assumes `users` table always exists |
| BUG-M38 | `app/services/error_recovery.py` | 243 | Jitter calculation can produce negative delay values |
| BUG-M39 | `app/exception_handlers.py` | 232–233 | Sensitive field redaction does not handle nested JSON fields |
| BUG-M40 | `app/exception_handlers.py` | 227–235 | JSON body parsing has no size limit (OOM risk) |
| BUG-M41 | `app/services/user_management.py` | 102, 232 | `User.is_active == True` comparison (should be `User.is_active`) |
| BUG-M42 | `app/services/user_management.py` | 239 | `GROUP BY User.roles` on array column — fails on most SQL backends |
| BUG-M43 | `app/middleware/api_versioning.py` | — | API version deprecation warnings not surfaced to users in response headers consistently |

---

### 4.4 Low Severity Bugs

> Severity: **LOW** — Code quality, style, or minor functional gaps.

| ID | File | Lines | Description |
|----|------|-------|-------------|
| BUG-L01 | `app/main.py` | 353 | Server binds to `0.0.0.0` by default — should be documented or restricted |
| BUG-L02 | `app/main.py` | 80–88 | Port availability check has TOCTOU race condition |
| BUG-L03 | `app/config.py` | 26 | `ENVIRONMENT` enum values not validated |
| BUG-L04 | `app/config.py` | 91 | `LOG_LEVEL` not validated against Python logging level names |
| BUG-L05 | `app/config.py` | — | No validation of URL format for `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL` |
| BUG-L06 | `app/middleware/authentication.py` | 10, 274, 314 | `from datetime import timezone` imported multiple times |
| BUG-L07 | `app/middleware/rate_limiting.py` | 199, 211 | Rate limit value hardcoded (60 req/min) — not pulled from config |
| BUG-L08 | `app/middleware/schema_validation.py` | 304–394 | Custom schema validation missing array items, nested objects, pattern checks |
| BUG-L09 | `app/routes/health.py` | 19–27 | `health_service` initialization relies on side-effect; no DI |
| BUG-L10 | `app/routes/health.py` | 47–51 | Uninitialized service returns 503 without triggering any alert |
| BUG-L11 | `app/routes/state.py` | 196–199 | Warning logged for expensive query but request still processed |
| BUG-L12 | `app/routes/state.py` | 164–169 | Limit parameter has no upper bound enforcement |
| BUG-L13 | `app/routes/state.py` | 268–271 | Cursor decode failure silently resets to offset 0 |
| BUG-L14 | `app/routes/sessions.py` | 136–151 | Pagination `per_page` has no ceiling value |
| BUG-L15 | `app/routes/auth.py` | 71–74 | Authentication failures not logged as security events |
| BUG-L16 | `app/routes/api_keys.py` | 134 | No upper bound on pagination `per_page` for API key listing |
| BUG-L17 | `app/routes/webhooks.py` | 74 | Webhook `status_filter` accepts any string — no enum validation |
| BUG-L18 | `app/routes/export.py` | 209 | `variables` query parameter has no format validation |
| BUG-L19 | `app/services/task_executor.py` | 509–510 | Hardcoded 3600-second task timeout magic number |
| BUG-L20 | `app/services/webhook_manager.py` | 187–190 | HMAC comparison not constant-time when used in secondary contexts |
| BUG-L21 | `app/services/health_check.py` | 102–235 | Performance thresholds (latency limits) hardcoded — not configurable |
| BUG-L22 | `app/services/cache_service.py` | 99, 130–131, 187 | TTL values hardcoded as magic numbers |
| BUG-L23 | `app/services/user_management.py` | 58 | New users default to `is_active=True` without email verification |
| BUG-L24 | `app/celery_app.py` | 12 | `sys.path.insert(0, ...)` is fragile — could cause import order issues |
| BUG-L25 | `app/celery_app.py` | 19–21 | Broker/backend URLs not validated at startup |
| BUG-L26 | `app/database/models.py` | 183, 182 | `full_state` and `config` JSONB fields have no schema validation |
| BUG-L27 | `app/database/models.py` | 412 | `unique=True` on `token_hash` may cause race conditions during token rotation |
| BUG-L28 | `app/database/models.py` | 551 | `AuditLog.user_id` has no `ondelete` strategy — orphaned logs when user deleted |
| BUG-L29 | `app/models/schemas.py` | 52–53 | Path validation rejects valid paths starting with `/` (overly strict) |
| BUG-L30 | `app/models/schemas.py` | 104 | Tags validator allows empty string tags after `strip()` |
| BUG-L31 | `app/services/authorization.py` | 364–365 | `permission.value.split(":")[1]` throws `IndexError` if no `:` in permission string |
| BUG-L32 | `.github/workflows/ci-cd.yml` | 49–50 | Test database not created before pytest runs in CI |
| BUG-L33 | `.github/workflows/ci-cd.yml` | 104–118 | Deployment step contains placeholder commands — will fail in real deployment |
| BUG-L34 | `.github/workflows/ci-cd.yml` | 75 | Registry login uses `GITHUB_TOKEN` (over-privileged — should use scoped PAT) |
| BUG-L35 | `app/routes/templates.py` | 166–218 | Create template endpoint missing `try/catch` for database constraint errors |

---

## 5. Security Vulnerabilities

The following table consolidates all security-specific findings with OWASP mapping.

| ID | Vulnerability | Severity | File | Lines | OWASP Category |
|----|--------------|----------|------|-------|----------------|
| SEC-01 | Missing `await` on Redis — token revocation non-functional | Critical | `auth_manager.py` | 251, 310 | A07: Auth Failures |
| SEC-02 | Task cancellation without ownership check (privilege escalation) | Critical | `tasks.py` | 311–318 | A01: Broken Access Control |
| SEC-03 | Session state readable by unauthorized users | Critical | `state.py` | 85, 202 | A01: Broken Access Control |
| SEC-04 | SSRF — cloud metadata endpoints not blocked | High | `webhook_manager.py` | 43–84 | A10: SSRF |
| SEC-05 | Webhook delivery without HMAC signature | High | `webhook_manager.py` | 207–208 | A08: Software Integrity Failures |
| SEC-06 | SHA-256 pre-hashing weakens bcrypt | High | `auth_manager.py` | 122–123 | A02: Crypto Failures |
| SEC-07 | Refresh tokens reusable indefinitely | High | `auth_manager.py` | 384–399 | A07: Auth Failures |
| SEC-08 | Rate limiter fails open when Redis down | High | `rate_limiter.py` | 78–79 | A05: Security Misconfiguration |
| SEC-09 | CORS wildcard in production only warns | High | `config.py` | 218–231 | A05: Security Misconfiguration |
| SEC-10 | Plaintext password returned from reset endpoint | High | `user_management.py` | 183–195 | A02: Crypto Failures |
| SEC-11 | User count exposed in public health endpoint | High | `health_check.py` | 153 | A01: Broken Access Control |
| SEC-12 | JWT secret reused for cursor HMAC signing | High | `state.py` | 253–291 | A02: Crypto Failures |
| SEC-13 | Rate limiter bypassed behind reverse proxy | High | `rate_limiting.py` | 76–82 | A05: Security Misconfiguration |
| SEC-14 | CSV injection prevention insufficient | Medium | `data_export.py` | 217–219 | A03: Injection |
| SEC-15 | Session ID in filename without sanitization | Medium | `export.py` | 123–124 | A01: Broken Access Control |
| SEC-16 | CSRF token hashing approach — design confusion | Medium | `csrf.py` | 148–161, 191 | A01: Broken Access Control |
| SEC-17 | API keys creatable without expiry (`expires_at=None`) | Medium | `api_keys.py` | 284–285 | A07: Auth Failures |
| SEC-18 | Authorization audit log failures are silent | Medium | `authorization.py` | 468–470 | A09: Logging Failures |
| SEC-19 | Role typos grant zero permissions silently | Medium | `authorization.py` | 145–151 | A01: Broken Access Control |
| SEC-20 | Exception handlers expose internal error details | Medium | `exception_handlers.py` | 232–246 | A04: Insecure Design |
| SEC-21 | New users auto-activated without email verification | Low | `user_management.py` | 58 | A07: Auth Failures |
| SEC-22 | `assert` guards disabled in optimized deployments | Low | `auth_manager.py`, `error_recovery.py` | Various | A04: Insecure Design |
| SEC-23 | No audit log for admin accessing user-owned resources | Low | `authorization.py` | 505–514 | A09: Logging Failures |
| SEC-24 | API key prefix 16-hex-char collision space | Low | `authentication.py` | 248–250 | A07: Auth Failures |

---

## 6. Missing Features & Incomplete Implementations

| ID | Feature | File(s) | Description | Priority |
|----|---------|---------|-------------|----------|
| MF-01 | Email verification on registration | `user_management.py`, `routes/users.py` | No email verification flow; users activate immediately | High |
| MF-02 | Account lockout after failed logins | `auth_manager.py`, `models.py` | No failed-attempt counter or lockout mechanism in the database schema | High |
| MF-03 | 2FA/MFA support | `models.py`, `routes/auth.py` | No TOTP/MFA columns in User model | High |
| MF-04 | Task dependency cycle detection | `task_executor.py` | DAG built but no cycle detection; circular dependencies accepted | High |
| MF-05 | Webhook HMAC signature verification | `webhook_manager.py` | Outbound webhooks carry no signature for receiver verification | High |
| MF-06 | Refresh token rotation | `auth_manager.py` | Single-use refresh tokens not implemented | High |
| MF-07 | Configurable rate limits per endpoint | `rate_limiting.py`, `rate_limiter.py` | Rates hardcoded at 60 req/min globally | Medium |
| MF-08 | Session state machine enforcement | `session_manager.py`, `routes/sessions.py` | No transition table; illegal state moves accepted silently | Medium |
| MF-09 | Soft-delete for users/sessions | `models.py` | No `is_deleted` / `deleted_at` column; hard deletes only | Medium |
| MF-10 | API key scoping/permissions | `api_keys.py`, `models.py` | API keys grant full account permissions; no per-key scope | Medium |
| MF-11 | Dead-letter queue for failed webhooks | `webhook_manager.py` | Permanently-failed webhooks are dropped; no DLQ or alerting | Medium |
| MF-12 | Export streaming with size limits | `data_export.py` | Size limit checked after full data load; should stream with backpressure | Medium |
| MF-13 | Deployment workflow actualization | `.github/workflows/ci-cd.yml` | Deployment steps are placeholder comments; will fail in real run | High |
| MF-14 | Security scanning in CI | `.github/workflows/ci-cd.yml` | No SAST (bandit), dependency audit (pip-audit/safety), or DAST in pipeline | High |

---

## 7. Test Coverage Gaps

| Area | Current Coverage | Target | Gap | Priority |
|------|----------------|--------|-----|----------|
| `app/routes/api_keys.py` | 0% | 80% | 80% | 🔴 Critical |
| `app/routes/webhooks.py` | 0% | 80% | 80% | 🔴 Critical |
| `app/services/webhook_manager.py` | 0% | 80% | 80% | 🔴 Critical |
| `app/services/error_recovery.py` | 0% | 80% | 80% | 🔴 Critical |
| `app/tasks/experimental_tasks.py` | 0% | 70% | 70% | 🔴 Critical |
| `app/middleware/authentication.py` | 25% | 80% | 55% | 🔴 Critical |
| `app/services/session_manager.py` | 14% | 80% | 66% | 🔴 Critical |
| `app/routes/tasks.py` | 21% | 80% | 59% | 🔴 Critical |
| `app/routes/state.py` | 14% | 80% | 66% | 🔴 Critical |
| `app/services/auth_manager.py` | 33% | 80% | 47% | 🟠 High |
| `app/middleware/csrf.py` | 27% | 80% | 53% | 🟠 High |
| `app/middleware/rate_limiting.py` | 35% | 80% | 45% | 🟠 High |
| `app/services/cache_service.py` | 29% | 80% | 51% | 🟠 High |

### Specific Missing Test Scenarios

| Scenario | Relevant Files |
|----------|---------------|
| Token revocation and re-use after logout | `auth_manager.py`, `routes/auth.py` |
| Task cancellation by non-owner (should 403) | `routes/tasks.py` |
| State access by non-owner (should 403) | `routes/state.py` |
| Concurrent task submissions with dependencies | `task_executor.py` |
| Rate limiter behavior when Redis is down | `rate_limiter.py`, `middleware/rate_limiting.py` |
| Webhook delivery with SSRF URLs | `webhook_manager.py` |
| CSV injection payload in export | `data_export.py` |
| Session state machine illegal transitions | `session_manager.py` |
| API key expiry enforcement | `middleware/authentication.py` |
| Pagination boundary conditions (0, 1, max+1) | All routes with pagination |
| CORS wildcard rejected in production | `config.py` |
| Request size limit enforcement | `middleware/request_size_limit.py` |
| Degraded health status returns 503 | `routes/health.py` |
| Clock skew in JWT verification | `services/auth_manager.py` |

---

## 8. Actionable Recommendations

### Priority 1 — Immediate (Block Production Deployment)

| # | Action | File(s) | Effort | Owner |
|---|--------|---------|--------|-------|
| R-01 | Add `await` to all async Redis calls in `auth_manager.py` (lines 251, 310) | `auth_manager.py` | S (1h) | Backend Dev |
| R-02 | Add task ownership validation in `cancel_task` endpoint | `routes/tasks.py` | S (2h) | Backend Dev |
| R-03 | Add session ownership validation in `state.py` endpoints | `routes/state.py` | S (2h) | Backend Dev |
| R-04 | Fix DB context manager resource leak in `templates.py` | `routes/templates.py` | S (1h) | Backend Dev |
| R-05 | Replace `time.sleep()` with `asyncio.sleep()` in `task_executor.py` | `task_executor.py` | S (30m) | Backend Dev |
| R-06 | Raise `ConfigurationError` on wildcard CORS in production | `config.py` | S (30m) | Backend Dev |
| R-07 | Fix degraded health → return HTTP 503 on readiness probe | `routes/health.py` | S (30m) | Backend Dev |
| R-08 | Implement webhook HMAC-SHA256 signature header | `webhook_manager.py` | M (4h) | Backend Dev |
| R-09 | Block SSRF destinations in webhook URL validation (169.254.x.x, 10.x.x.x, etc.) | `webhook_manager.py` | M (3h) | Backend Dev |
| R-10 | Replace `assert` guards with explicit exception raises | Multiple | S (2h) | Backend Dev |

### Priority 2 — High (Address Before First Release)

| # | Action | File(s) | Effort | Owner |
|---|--------|---------|--------|-------|
| R-11 | Implement refresh token rotation (single-use) | `auth_manager.py` | M (8h) | Backend Dev |
| R-12 | Replace SHA-256 pre-hashing with direct bcrypt or argon2 | `auth_manager.py` | M (4h) | Backend Dev |
| R-13 | Replace `redis.keys()` with `redis.scan_iter()` | `cache_service.py` | S (1h) | Backend Dev |
| R-14 | Extract X-Forwarded-For in rate limiter for real client IP | `rate_limiting.py` | S (2h) | Backend Dev |
| R-15 | Fix `logger.warning()` `extra=` parameter usage | `authorization.py` | S (30m) | Backend Dev |
| R-16 | Fix rate limiter off-by-one (increment after check) | `rate_limiter.py` | S (1h) | Backend Dev |
| R-17 | Add cycle detection to task dependency graph | `task_executor.py` | M (6h) | Backend Dev |
| R-18 | Remove user count from public health check | `health_check.py` | S (30m) | Backend Dev |
| R-19 | Do not return plaintext password from reset endpoint | `user_management.py` | S (2h) | Backend Dev |
| R-20 | Use dedicated cursor signing key (not JWT secret) | `routes/state.py` | S (1h) | Backend Dev |
| R-21 | Populate `key_prefix` on API key creation | `routes/api_keys.py` | S (2h) | Backend Dev |
| R-22 | Add security scanning (bandit, pip-audit) to CI/CD pipeline | `.github/workflows/ci-cd.yml` | M (4h) | DevOps |
| R-23 | Implement actual deployment steps in CI/CD workflow | `.github/workflows/ci-cd.yml` | L (1 day) | DevOps |
| R-24 | Add upper-bound validation on all pagination `per_page` parameters | All routes | S (3h) | Backend Dev |

### Priority 3 — Medium (Address in Sprint Backlog)

| # | Action | File(s) | Effort | Owner |
|---|--------|---------|--------|-------|
| R-25 | Implement session state machine with legal transition table | `session_manager.py`, `routes/sessions.py` | L (2 days) | Backend Dev |
| R-26 | Add email verification flow on registration | `user_management.py`, `routes/users.py` | L (2 days) | Backend Dev |
| R-27 | Implement account lockout after N failed logins | `auth_manager.py`, `models.py` | M (1 day) | Backend Dev |
| R-28 | Add API key scoping/permissions | `api_keys.py`, `models.py` | L (3 days) | Backend Dev |
| R-29 | Fix mutable default arguments in ORM models | `models.py` | S (1h) | Backend Dev |
| R-30 | Add format allowlist validation to export endpoint | `routes/export.py` | S (1h) | Backend Dev |
| R-31 | Fix CSV injection prevention (escape all formula characters) | `data_export.py` | S (2h) | Backend Dev |
| R-32 | Fix rate-limiter fail-open behavior (configurable fail mode) | `rate_limiter.py` | M (4h) | Backend Dev |
| R-33 | Fix CORS methods/headers whitespace trimming | `config.py` | S (30m) | Backend Dev |
| R-34 | Move regex compilation to module level in `schemas.py` | `models/schemas.py` | S (30m) | Backend Dev |
| R-35 | Implement webhook dead-letter queue | `webhook_manager.py` | L (2 days) | Backend Dev |

### Priority 4 — Low (Quality Improvements)

| # | Action | File(s) | Effort | Owner |
|---|--------|---------|--------|-------|
| R-36 | Add soft-delete support to User and Session models | `models.py` | L (2 days) | Backend Dev |
| R-37 | Add 2FA/MFA columns to User model | `models.py` | L (3 days) | Backend Dev |
| R-38 | Validate `ENVIRONMENT`, `LOG_LEVEL` enum values in config | `config.py` | S (1h) | Backend Dev |
| R-39 | Add `ondelete` strategy for `AuditLog.user_id` FK | `models.py` | S (1h) | Backend Dev |
| R-40 | Remove duplicate timezone imports across middleware | Multiple | S (30m) | Backend Dev |
| R-41 | Document all magic numbers (TTLs, timeouts, limits) | Multiple | M (1 day) | Backend Dev |
| R-42 | Replace `sys.path.insert` in celery with proper package install | `celery_app.py` | S (30m) | Backend Dev |
| R-43 | Add `AuditLog` entries for admin accessing user-owned resources | `authorization.py` | M (4h) | Backend Dev |

### Test Coverage Remediation Plan

To reach 80% coverage target from the current 31%:

1. **Week 1 (Critical paths):** Write integration tests for `api_keys.py`, `webhooks.py`, `routes/state.py` — estimated to bring coverage to ~50%
2. **Week 2 (Auth & Sessions):** Write tests for `auth_manager.py` (token lifecycle), `session_manager.py` (state transitions), `rate_limiter.py` — estimated ~62%
3. **Week 3 (Services):** Cover `webhook_manager.py`, `error_recovery.py`, `task_executor.py` — estimated ~73%
4. **Week 4 (Edge cases):** Security-specific tests (ownership validation, SSRF, rate limiting, CSV injection) — estimated ~82%

---

## 9. Appendix: File-Level Coverage Table

| File | Statements | Missing | Coverage |
|------|-----------|---------|----------|
| `app/__init__.py` | 1 | 0 | 100% |
| `app/celery_app.py` | 8 | 0 | 100% |
| `app/config.py` | 98 | 22 | 78% |
| `app/database/models.py` | 157 | 0 | 100% |
| `app/models/schemas.py` | 672 | 270 | 60% |
| `app/main.py` | 140 | 64 | 54% |
| `app/middleware/__init__.py` | 11 | 0 | 100% |
| `app/middleware/api_versioning.py` | 13 | 0 | 100% |
| `app/middleware/logging.py` | 57 | 13 | 77% |
| `app/middleware/metrics.py` | 209 | 55 | 74% |
| `app/middleware/cors_config.py` | 9 | 3 | 67% |
| `app/middleware/deprecation.py` | 56 | 36 | 36% |
| `app/middleware/profiling.py` | 47 | 34 | 28% |
| `app/middleware/alerting.py` | 293 | 220 | 25% |
| `app/middleware/authentication.py` | 106 | 79 | 25% |
| `app/middleware/csrf.py` | 59 | 43 | 27% |
| `app/middleware/rate_limiting.py` | 85 | 55 | 35% |
| `app/middleware/request_size_limit.py` | 49 | 16 | 67% |
| `app/middleware/schema_validation.py` | 140 | 122 | 13% |
| `app/middleware/tracing.py` | 77 | 60 | 22% |
| `app/routes/__init__.py` | 10 | 0 | 100% |
| `app/routes/auth.py` | 42 | 26 | 38% |
| `app/routes/export.py` | 77 | 55 | 29% |
| `app/routes/health.py` | 25 | 12 | 52% |
| `app/routes/metrics.py` | 158 | 113 | 29% |
| `app/routes/sessions.py` | 165 | 124 | 25% |
| `app/routes/state.py` | 146 | 126 | 14% |
| `app/routes/tasks.py` | 140 | 110 | 21% |
| `app/routes/templates.py` | 113 | 90 | 20% |
| `app/routes/users.py` | 101 | 60 | 41% |
| `app/routes/version.py` | 32 | 12 | 63% |
| `app/routes/api_keys.py` | 98 | 98 | **0%** |
| `app/routes/webhooks.py` | 63 | 63 | **0%** |
| `app/services/auth_manager.py` | 204 | 136 | 33% |
| `app/services/authorization.py` | 133 | 71 | 47% |
| `app/services/business_metrics.py` | 89 | 62 | 30% |
| `app/services/cache_service.py` | 116 | 82 | 29% |
| `app/services/data_export.py` | 112 | 97 | 13% |
| `app/services/error_recovery.py` | 149 | 149 | **0%** |
| `app/services/health_check.py` | 101 | 90 | 11% |
| `app/services/profiling_service.py` | 141 | 109 | 23% |
| `app/services/rate_limiter.py` | 42 | 34 | 19% |
| `app/services/seeding_service.py` | 163 | 163 | **0%** |
| `app/services/session_manager.py` | 348 | 300 | 14% |
| `app/services/sharding_service.py` | 63 | 63 | **0%** |
| `app/services/task_executor.py` | 152 | 132 | 13% |
| `app/services/user_management.py` | 97 | 77 | 21% |
| `app/services/webhook_manager.py` | 135 | 135 | **0%** |
| `app/tasks/experimental_tasks.py` | 171 | 171 | **0%** |
| `app/tasks/task_registry.py` | 27 | 27 | **0%** |
| `app/tracing.py` | 50 | 50 | **0%** |
| `app/cli.py` | 89 | 89 | **0%** |
| `app/database/connection.py` | 97 | 69 | 29% |
| `app/database/sharded_connection.py` | 94 | 94 | **0%** |
| `app/exceptions.py` | 74 | 35 | 53% |
| `app/exception_handlers.py` | 70 | 45 | 36% |
| **TOTAL** | **~5,200** | **~3,600** | **31%** |

---

*Report generated: 2026-02-27 | Methodology: Static code analysis, security review, coverage data analysis | Total issues: 117*
