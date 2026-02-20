# APGI REST API — Comprehensive Application Audit Report

**Date:** 2026-02-20
**Auditor:** Claude Code (Automated End-to-End Audit)
**Branch:** `claude/app-audit-testing-X8RlG`
**Project:** APGI Standalone REST API (`lesoto/apgi-api`)
**Stack:** Python 3.10+, FastAPI, PostgreSQL, Redis, Celery, SQLAlchemy, Alembic

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [KPI Scores](#2-kpi-scores)
3. [Application Overview](#3-application-overview)
4. [Bug Inventory](#4-bug-inventory)
   - 4.1 [Critical Bugs](#41-critical-bugs)
   - 4.2 [High Bugs](#42-high-bugs)
   - 4.3 [Medium Bugs](#43-medium-bugs)
   - 4.4 [Low Bugs](#44-low-bugs)
5. [Missing Features & Incomplete Implementations](#5-missing-features--incomplete-implementations)
6. [Security Audit](#6-security-audit)
7. [Performance Assessment](#7-performance-assessment)
8. [Code Quality Assessment](#8-code-quality-assessment)
9. [Test Coverage Assessment](#9-test-coverage-assessment)
10. [Deployment & Infrastructure Assessment](#10-deployment--infrastructure-assessment)
11. [Actionable Recommendations](#11-actionable-recommendations)
12. [Remediation Priority Matrix](#12-remediation-priority-matrix)

---

## 1. Executive Summary

The APGI (Allostatic Precision-Gated Ignition) Standalone REST API is a Python/FastAPI backend designed for consciousness-modeling simulations. It provides session lifecycle management, asynchronous task execution, real-time state access, data export, and observability tooling. The project demonstrates strong architectural intent — clean layering, thorough middleware stack, comprehensive dependency injection, and a well-structured test suite — but contains several **critical runtime bugs** that would prevent the application from functioning correctly in production.

### Key Findings at a Glance

| Category | Count |
|---|---|
| Critical Bugs | 4 |
| High Bugs | 9 |
| Medium Bugs | 9 |
| Low Bugs | 6 |
| Missing Features | 12 |
| Security Issues | 6 |

### Most Urgent Issues

1. **`GET /v1/client-docs` is completely broken** — a Python syntax error (set literal `{{ }}` instead of dict `{ }`) causes a `TypeError` crash on every call.
2. **API key authentication never works** — the SHA-256 hash of any supplied key is compared against unhashed plain-text keys in a mock dictionary, so every API key attempt fails silently.
3. **Sessions are always attributed to the hardcoded user `"default_user"`** — the authenticated user's identity is not passed to `SessionManager.create_session()`, breaking all multi-user isolation.
4. **Session ownership is never validated** — any authenticated user can read, start, pause, stop, reset, or delete any other user's session.

Despite these issues, the overall architecture is sound and most defects are isolated and remediable without structural refactoring.

---

## 2. KPI Scores

| KPI | Score (1–100) | Rationale |
|---|---|---|
| **Functional Completeness** | 58 / 100 | Core CRUD for sessions, tasks, templates, and users works. However, the step-execution endpoint is missing, client-docs crashes, API key auth is broken, session ownership is never enforced, and state restoration on resume is a placeholder. |
| **UI/UX Consistency** | 72 / 100 | OpenAPI documentation is thorough and consistent. Error response schema is standardised. Pagination is inconsistent (offset-based vs. cursor-based within the same `PaginationInfo` model). The HTML dashboard contains only placeholder charts. `DELETE /v1/tasks/{id}` returns HTTP 200 with a body instead of 204. |
| **Responsiveness & Performance** | 70 / 100 | Redis caching, GZip compression, rate limiting, Celery async tasks, and DB connection pooling are all present. However, template list counting fetches all rows into Python memory instead of using a SQL `COUNT`. Several async route handlers call synchronous SQLAlchemy operations that can block the event loop. |
| **Error Handling & Resilience** | 71 / 100 | Custom exception hierarchy, global handlers, database rollbacks, and Celery retry logic with exponential backoff are implemented. Rate limiter gracefully degrades. However, the `/v1/client-docs` endpoint crashes unhandled, API key auth silently swallows all exceptions, and several service exceptions bubble up with raw internal details. |
| **Overall Implementation Quality** | 65 / 100 | Separation of concerns, dependency injection, and the middleware stack are architectural strengths. Critical production bugs, hardcoded credentials, unimplemented core features, deprecated API usages, and several security gaps weigh down the score. |

**Composite Score: 67 / 100**

---

## 3. Application Overview

### Technology Stack

| Layer | Technology |
|---|---|
| Web Framework | FastAPI ≥ 0.110.0 + Uvicorn ≥ 0.28.0 |
| Database | PostgreSQL (async: asyncpg; sync: psycopg2) + SQLAlchemy 2.x ORM |
| Migrations | Alembic ≥ 1.13.0 |
| Cache / Broker | Redis 7 |
| Task Queue | Celery ≥ 5.3.4 |
| Auth | PyJWT + python-jose + bcrypt |
| Observability | Prometheus, OpenTelemetry, Jaeger/OTLP |
| Testing | pytest, pytest-asyncio, hypothesis, locust |

### Route Map

| Prefix | Router File | Endpoints |
|---|---|---|
| `/v1/auth` | `routes/auth.py` | POST login, POST refresh |
| `/v1/users` | `routes/users.py` | POST register, POST create-default, GET list, GET me, GET stats, GET/{id}, PUT/{id}, POST/{id}/reset-password, DELETE/{id} |
| `/v1/sessions` | `routes/sessions.py` | GET list, POST create, GET/{id}, GET/{id}/metrics, GET/{id}/tasks, POST/{id}/start, POST/{id}/pause, POST/{id}/stop, POST/{id}/reset, DELETE/{id} |
| `/v1/sessions/{id}` | `routes/state.py` | GET state, GET ignition-history, GET interoception, GET prediction-errors, GET somatic-markers |
| `/v1/sessions/{id}` | `routes/export.py` | GET export, GET export/summary |
| `/templates` ⚠️ | `routes/templates.py` | GET list, POST create, GET/{id}, PUT/{id}, DELETE/{id} |
| `/v1` | `routes/tasks.py` | GET tasks, POST sessions/{id}/tasks, GET tasks/{id}, GET tasks/{id}/result, DELETE tasks/{id}, POST tasks/{id}/dependencies, GET tasks/{id}/dependencies, DELETE tasks/{id}/dependencies/{dep_id} |
| `/v1` | `routes/metrics.py` | GET metrics, GET dashboard/*, GET profiling/*, POST profiling/memory/start\|stop |
| `/v1` | `routes/version.py` | GET version, GET client-docs |
| (root) | `routes/health.py` | GET /health, GET /health/ready, GET /health/live |

---

## 4. Bug Inventory

### 4.1 Critical Bugs

---

#### BUG-C01 — `GET /v1/client-docs` crashes with `TypeError` on every request

| Field | Detail |
|---|---|
| **Severity** | Critical |
| **File** | `app/routes/version.py` |
| **Lines** | 239–272 |
| **Affected URL** | `GET /v1/client-docs?language=<any>` |

**Description:**
The `get_client_documentation()` handler uses Python set-literal syntax (`{{ }}`) instead of dict-literal syntax (`{ }`) in two return statements. A Python `set` cannot contain `dict` items (dicts are unhashable), so both code paths raise `TypeError: unhashable type: 'dict'` before any response is ever sent.

**Reproduction Steps:**
1. Authenticate and obtain a valid JWT token.
2. Send `GET /v1/client-docs?language=python`.
3. Observe HTTP 500 Internal Server Error with `TypeError` in logs.

**Code Evidence:**
```python
# Line 239 – error path: set literal, not dict
return JSONResponse(
    status_code=400,
    content={          # outer brace is correct
        {              # ← THIS is a set literal, not a dict key
            "error": f"Unsupported language: {language}",
            "supported_languages": supported_languages,
        }
    },
)

# Lines 249–272 – success path: same problem
return {
    {                  # ← set literal again
        "language": language,
        ...
    }
}
```

**Expected:** Returns JSON with client SDK examples.
**Actual:** `TypeError: unhashable type: 'dict'` → HTTP 500.

**Fix:** Replace every `{ { ... } }` with `{ ... }` (single braces for dicts).

---

#### BUG-C02 — API key authentication always fails silently

| Field | Detail |
|---|---|
| **Severity** | Critical |
| **File** | `app/middleware/authentication.py` |
| **Lines** | 252–280 |
| **Affected URLs** | All protected endpoints when using `X-API-Key` header |

**Description:**
The `_verify_api_key()` method computes a SHA-256 hex digest of the supplied API key and then looks up that hash in a dictionary whose keys are **plain-text** strings (e.g. `"test_key_123"`). A SHA-256 hex string (64 hex characters) will never match a plain-text key string, so `if key_hash not in mock_api_keys` is always `True`, and `ValueError("Invalid API key")` is always raised.

Furthermore, the entire mock dictionary is hardcoded in the source code — there is no database table for API keys — making the feature entirely non-functional.

**Code Evidence:**
```python
key_hash = hashlib.sha256(api_key.encode()).hexdigest()  # e.g. "a3f9c..."

mock_api_keys = {
    "test_key_123": { ... }   # plain-text key, never matches a hash
}

if key_hash not in mock_api_keys:   # always True → always raises
    raise ValueError("Invalid API key")
```

**Expected:** `X-API-Key: test_key_123` is accepted and resolves to a user.
**Actual:** Every API key is silently rejected; the middleware falls back to "no credentials present," which lets the route's own `require_permission` dependency raise a 403.

**Fix:** Either (a) compare `api_key` directly (not its hash) against a properly stored and hashed database table, or (b) implement a real `api_keys` database table with hashed key storage and correct lookup.

---

#### BUG-C03 — Sessions always attributed to hardcoded user `"default_user"`

| Field | Detail |
|---|---|
| **Severity** | Critical |
| **File** | `app/services/session_manager.py` (create_session), `app/routes/sessions.py` line 183 |
| **Lines** | sessions.py:183 |
| **Affected URL** | `POST /v1/sessions` |

**Description:**
`SessionManager.create_session()` defaults `user_id` to `"default_user"`. The `create_session` route handler calls `await manager.create_session(request)` without passing `current_user.user_id`. Every session created by any user is therefore owned by `"default_user"` in the database, breaking per-user isolation, filtering, and access control.

**Code Evidence:**
```python
# routes/sessions.py:183
session_id = await manager.create_session(request)  # current_user never passed

# SessionManager.create_session() signature (session_manager.py)
async def create_session(self, request, user_id: str = "default_user"):
    ...
```

**Expected:** Sessions are created with the authenticated user's `user_id`.
**Actual:** All sessions are stored under `user_id = "default_user"`.

**Fix:** Pass `current_user.user_id` explicitly: `await manager.create_session(request, user_id=current_user.user_id)`.

---

#### BUG-C04 — Session ownership never validated (IDOR vulnerability)

| Field | Detail |
|---|---|
| **Severity** | Critical |
| **File** | `app/routes/sessions.py` |
| **Lines** | All per-session endpoints (GET/{id}, start, pause, stop, reset, delete) |
| **Affected URLs** | `GET/POST/DELETE /v1/sessions/{session_id}` and sub-routes |

**Description:**
Every session-specific endpoint fetches a session by `session_id` without verifying that the session belongs to `current_user`. Any authenticated user can read, control, or delete any other user's session by guessing or knowing its UUID. This is a classic Insecure Direct Object Reference (IDOR).

**Reproduction Steps:**
1. Authenticate as `user_A` and create a session; note its `session_id`.
2. Authenticate as `user_B`.
3. Send `POST /v1/sessions/{user_A_session_id}/start` as `user_B`.
4. Observe the session starts successfully.

**Expected:** HTTP 403 Forbidden — user does not own this session.
**Actual:** HTTP 200 — session is controlled by the wrong user.

**Fix:** After fetching the session, compare `sim_session.user_id` against `current_user.user_id` and raise HTTP 403 if they differ.

---

### 4.2 High Bugs

---

#### BUG-H01 — `POST /v1/sessions/{session_id}/step` endpoint is missing

| Field | Detail |
|---|---|
| **Severity** | High |
| **File** | `app/routes/sessions.py` |
| **Affected URL** | `POST /v1/sessions/{session_id}/step` |

**Description:**
The `SimulationSession` class implements a `step()` method for single-step execution of the simulation. This is a core scientific feature of the system. However, no HTTP route exists that exposes this endpoint. The route is referenced in documentation and test fixtures but never registered in the sessions router.

**Expected:** `POST /v1/sessions/{session_id}/step` returns the updated state after one simulation tick.
**Actual:** HTTP 404 Not Found — route does not exist.

**Fix:** Add a `POST /{session_id}/step` route handler in `routes/sessions.py` that calls `sim_session.step()` and returns the resulting state.

---

#### BUG-H02 — Pause/resume does not restore full simulation state

| Field | Detail |
|---|---|
| **Severity** | High |
| **File** | `app/services/session_manager.py` |
| **Lines** | ~276–282 (restore_state block) |
| **Affected URLs** | `POST /v1/sessions/{id}/pause`, `POST /v1/sessions/{id}/start` (resume) |

**Description:**
The `_restore_state()` method only restores `time` and `history` from the persisted state blob, leaving all internal subsystem states (allostasis, body, precision, workspace, self-model, etc.) at their default initial values. The code comment explicitly acknowledges this: *"This is a simplified restoration — in production, you'd need to carefully restore each subsystem's internal state."* Pausing and resuming a session therefore effectively resets the simulation, discarding all computed state.

**Expected:** Resume continues the simulation exactly where it paused.
**Actual:** Resume starts with subsystems at default values; only the simulation clock and ignition history carry over.

**Fix:** Implement full serialisation and deserialisation for all `APGISystem` subsystem states in `_restore_state()`.

---

#### BUG-H03 — Templates router missing `/v1/` prefix

| Field | Detail |
|---|---|
| **Severity** | High |
| **File** | `app/routes/templates.py` line 27 |
| **Affected URLs** | All `/v1/templates/*` endpoints |

**Description:**
The templates router is declared with `prefix="/templates"` instead of `prefix="/v1/templates"`. All other routers use the `/v1` versioned prefix. The templates endpoints are exposed at `/templates/` instead of `/v1/templates/`, breaking API versioning consistency and causing all documented API calls to return 404.

**Code Evidence:**
```python
# routes/templates.py:27
router = APIRouter(prefix="/templates", tags=["Templates"])
# Should be:
router = APIRouter(prefix="/v1/templates", tags=["Templates"])
```

**Expected:** Templates accessible at `GET /v1/templates`.
**Actual:** Templates accessible at `GET /templates` (undocumented path); `GET /v1/templates` returns 404.

---

#### BUG-H04 — Template list count loads all rows into Python memory

| Field | Detail |
|---|---|
| **Severity** | High |
| **File** | `app/routes/templates.py` |
| **Lines** | 96–97 |
| **Affected URL** | `GET /templates` (also `/v1/templates` after BUG-H03 fix) |

**Description:**
The total-count query for pagination fetches all matching rows from the database into Python memory using `fetchall()` and then calls `len()`. This is a full table scan materialised in the application process. With a large number of templates this will cause excessive memory usage and slow response times.

**Code Evidence:**
```python
# routes/templates.py:96-97
total_result = db_session.execute(select(SessionTemplate).where(query.whereclause))
total = len(total_result.fetchall())  # loads EVERY row just to count
```

**Fix:** Use `SELECT COUNT(*)`:
```python
from sqlalchemy import func
count_stmt = select(func.count()).select_from(SessionTemplate).where(query.whereclause)
total = db_session.execute(count_stmt).scalar()
```

---

#### BUG-H05 — Template listing returns `Row` proxy objects, not ORM model instances

| Field | Detail |
|---|---|
| **Severity** | High |
| **File** | `app/routes/templates.py` |
| **Lines** | 104–122 |
| **Affected URL** | `GET /templates` |

**Description:**
`result.fetchall()` on a `select(Model)` statement returns `Row` proxy objects (essentially named tuples with one element), not ORM model instances directly. Accessing `template.template_id` on a `Row` works only because `Row` proxies attribute access to the first column — but this is fragile and will break if the query structure changes. The correct approach is `result.scalars().all()`.

**Fix:**
```python
result = db_session.execute(query)
templates_db = result.scalars().all()  # returns actual SessionTemplate instances
```

---

#### BUG-H06 — Ignition history annotates all events with current (not historical) signal values

| Field | Detail |
|---|---|
| **Severity** | High |
| **File** | `app/routes/state.py` |
| **Lines** | 225–238 |
| **Affected URL** | `GET /v1/sessions/{session_id}/ignition-history` |

**Description:**
When building the ignition event list, `ignition_data` is fetched once from the current state **outside** the loop, then used for every historical event. All ignition events are therefore annotated with the same `trigger_signal` and `threshold` — the values at the present moment, not the values at the time each event occurred.

**Code Evidence:**
```python
for i, (time_val, ignition_val) in enumerate(zip(times, ignitions)):
    if ignition_val:
        ignition_data = state.get("ignition", {})  # ← same current value every iteration
        total_signal = ignition_data.get("total_signal", 0.0)
        threshold = ignition_data.get("threshold", 2.0)
```

**Fix:** Store per-timestep signal and threshold in `history`, or use the histogrammed data if available. At a minimum, move the `ignition_data` lookup outside the loop and document that it represents the current (not historical) threshold.

---

#### BUG-H07 — Middleware ordering causes CSRF to execute before Authentication

| Field | Detail |
|---|---|
| **Severity** | High |
| **File** | `app/main.py` (middleware registration block) |
| **Affected URLs** | All state-mutating endpoints (`POST`, `PUT`, `DELETE`) |

**Description:**
Starlette applies `add_middleware` registrations in **reverse order** (last registered = outermost). If `AuthenticationMiddleware` is registered after `CSRFMiddleware`, then CSRF token validation runs before the user is authenticated. This means unauthenticated requests are checked for CSRF tokens (which they will never have), producing confusing 403 errors instead of 401 Unauthorized. The correct order is: Auth → CSRF → business logic.

**Fix:** Register `AuthenticationMiddleware` **after** (i.e., outermost, highest in the chain) all other middleware.

---

#### BUG-H08 — Missing `POST /v1/auth/logout` endpoint

| Field | Detail |
|---|---|
| **Severity** | High |
| **File** | `app/routes/auth.py` |
| **Affected URL** | `POST /v1/auth/logout` (absent) |

**Description:**
`AuthManager` implements `revoke_refresh_token()` and the `RefreshToken` model has a `revoked` column, but no HTTP endpoint exposes token revocation. Users have no way to invalidate their tokens on logout. Access tokens remain valid until expiry even after the user explicitly logs out.

**Fix:** Add `POST /v1/auth/logout` that calls `auth_manager.revoke_refresh_token(refresh_token)` and clears any client-side token storage.

---

#### BUG-H09 — `cancel_task` marks task status as `"failed"` instead of `"cancelled"`

| Field | Detail |
|---|---|
| **Severity** | High |
| **File** | `app/services/task_executor.py` |
| **Lines** | 519–524 |
| **Affected URL** | `DELETE /v1/tasks/{task_id}` |

**Description:**
When a task is cancelled, its database status is set to `TaskStatus.FAILED` with the message `"Task cancelled by user"`. This conflates cancellation (a normal user action) with failure (an error condition). Downstream analytics, dashboards, and dependency logic cannot distinguish between a failed task and a cancelled one.

**Fix:** Add `CANCELLED` to the `TaskStatus` enum and use it in `cancel_task()`.

---

### 4.3 Medium Bugs

---

#### BUG-M01 — `POST /v1/users/create-default` hardcodes password `"secure_password"`

| Field | Detail |
|---|---|
| **Severity** | Medium |
| **File** | `app/routes/users.py` |
| **Lines** | 123–126 |
| **Affected URL** | `POST /v1/users/create-default` |

**Description:**
The default admin user is always created with the literal password `"secure_password"`, which is returned in the response. This default credential is a well-known security risk if left unchanged.

**Fix:** Generate a cryptographically random password and return it once; or require the caller to supply a password in the request body.

---

#### BUG-M02 — Password reset response returns new password in plaintext

| Field | Detail |
|---|---|
| **Severity** | Medium |
| **File** | `app/routes/users.py` |
| **Lines** | 406–412 |
| **Affected URL** | `POST /v1/users/{user_id}/reset-password` |

**Description:**
`PasswordResetResponse` includes the new password in the JSON response body. This password appears in server logs, reverse-proxy logs, SIEM outputs, and browser developer tools, significantly increasing exposure risk.

**Fix:** Do not return passwords in API responses. Return only a success indicator. Deliver new passwords via out-of-band channels (e.g., email) or require the client to supply the new password explicitly.

---

#### BUG-M03 — `GET /v1/users` has no pagination

| Field | Detail |
|---|---|
| **Severity** | Medium |
| **File** | `app/routes/users.py` |
| **Lines** | 152–182 |
| **Affected URL** | `GET /v1/users` |

**Description:**
`list_users()` calls `user_service.list_users(active_only=active_only)` which returns all matching users without any limit. On a large system this can return hundreds of thousands of rows, exhausting memory and causing slow responses.

**Fix:** Add `page` and `per_page` query parameters matching the pattern used in `list_sessions()` and `list_templates()`.

---

#### BUG-M04 — Dashboard HTML contains only placeholder charts (no real data)

| Field | Detail |
|---|---|
| **Severity** | Medium |
| **File** | `app/routes/metrics.py` |
| **Lines** | 340–354 |
| **Affected URL** | `GET /v1/dashboard/html` |

**Description:**
The HTML dashboard endpoint renders metric numbers correctly but replaces all data visualisations with grey `<div class="chart-placeholder">` boxes containing only static text ("Performance Chart - Last N days", "Endpoint Usage Chart"). No actual charts are rendered.

**Expected:** Performance trend charts and endpoint usage charts display real data.
**Actual:** Placeholder boxes with no data.

---

#### BUG-M05 — `version.py` duplicates `typing` imports

| Field | Detail |
|---|---|
| **Severity** | Medium (code quality) |
| **File** | `app/routes/version.py` |
| **Lines** | 10 and 14 |

**Description:**
`from typing import Dict, List, Optional` is imported twice. This causes a lint warning and may confuse static analysis tools.

---

#### BUG-M06 — `GET /v1/sessions/{session_id}/metrics` uses placeholder comment labels

| Field | Detail |
|---|---|
| **Severity** | Medium |
| **File** | `app/routes/sessions.py` |
| **Lines** | 277–287 |
| **Affected URL** | `GET /v1/sessions/{session_id}/metrics` |

**Description:**
Several metric fields are computed with inline `# Placeholder` comments, indicating that the mapping between internal state keys and metric fields has not been fully validated.

```python
"ignition_frequency": ignition.get("intensity", 0.0),  # Placeholder
"free_energy":        allostatic.get("load", 0.0),       # Placeholder
"metabolic_load":     body.get("energy", 0.0),           # Placeholder
```

The keys (`"intensity"`, `"load"`, `"energy"`) may not correspond to the actual keys present in the simulation state dictionary, resulting in all metrics returning `0.0`.

---

#### BUG-M07 — `PaginationInfo` schema is reused with incompatible field sets

| Field | Detail |
|---|---|
| **Severity** | Medium |
| **File** | `app/models/schemas.py`, `app/routes/sessions.py`, `app/routes/state.py` |
| **Affected URLs** | `GET /v1/sessions`, `GET /v1/sessions/{id}/ignition-history` |

**Description:**
`PaginationInfo` is used both with `(page, per_page, total)` fields (offset-based pagination in session list) and with `(next_cursor, has_more)` fields (cursor-based in ignition history). The same model is used for two incompatible pagination schemes, forcing optional fields and making the schema ambiguous for API consumers.

**Fix:** Define separate `OffsetPaginationInfo` and `CursorPaginationInfo` schemas.

---

#### BUG-M08 — Task priority not exposed in task-submission route

| Field | Detail |
|---|---|
| **Severity** | Medium |
| **File** | `app/routes/tasks.py` |
| **Lines** | 104–151 |
| **Affected URL** | `POST /v1/sessions/{session_id}/tasks` |

**Description:**
`TaskExecutor.submit_task()` accepts a `priority` parameter (1–10), and the `Task` model stores `priority` in the database. However, `TaskSubmitRequest` does not include a `priority` field, and `execute_task()` never passes one to `submit_task()`. All tasks are submitted at the default priority of 5.

---

#### BUG-M09 — `datetime.utcnow()` used throughout (deprecated since Python 3.12)

| Field | Detail |
|---|---|
| **Severity** | Medium |
| **File** | Multiple (`task_executor.py`, `version.py`, `auth_manager.py`, etc.) |

**Description:**
`datetime.utcnow()` has been deprecated since Python 3.12 and will emit `DeprecationWarning` in newer runtimes. The project targets Python ≥ 3.10, so this will become a problem as adoption of 3.12+ grows.

**Fix:** Replace all `datetime.utcnow()` with `datetime.now(timezone.utc)`.

---

### 4.4 Low Bugs

---

#### BUG-L01 — `_is_public_path` uses prefix matching for `/docs/` but `/docs` is not a prefix endpoint

| Field | Detail |
|---|---|
| **Severity** | Low |
| **File** | `app/middleware/authentication.py` |
| **Lines** | 133–140 |

**Description:**
The middleware allows prefix `/docs/` to bypass auth (for static assets), but the Swagger UI is served at exact path `/docs`. A request to `/docs` (without trailing slash) hits the exact match in `PUBLIC_PATHS`. A request to `/docs/oauth2-redirect` (used by Swagger) hits the prefix check. This is functionally correct but could be tightened to avoid inadvertently bypassing auth for any path starting with `/docs/`.

---

#### BUG-L02 — bcrypt silently truncates passwords longer than 72 bytes

| Field | Detail |
|---|---|
| **Severity** | Low |
| **File** | `app/services/auth_manager.py` |

**Description:**
The bcrypt algorithm truncates input at 72 bytes. Two passwords that share the same first 72 bytes are functionally identical. No warning or validation prevents users from setting passwords longer than 72 bytes while believing the full length is checked.

**Fix:** Add a pre-hash step (e.g., HMAC-SHA256) before bcrypt hashing, or validate password length ≤ 72 bytes with an explicit error.

---

#### BUG-L03 — `GET /health/ready` performs the same checks as `GET /health`

| Field | Detail |
|---|---|
| **Severity** | Low |
| **File** | `app/routes/health.py` |
| **Lines** | 83–89 |

**Description:**
Readiness and full health checks are semantically distinct in Kubernetes: readiness indicates the pod is ready to receive traffic, liveness indicates the process is alive. Both `GET /health` and `GET /health/ready` call identical `perform_health_check()` logic, making the distinction meaningless. The liveness probe (`GET /health/live`) correctly returns a lightweight 200 without dependency checks.

**Fix:** `GET /health/ready` should check only critical dependencies (database, Redis). `GET /health` can include optional/advisory component checks.

---

#### BUG-L04 — `register_user` requires `USER_CREATE` permission, blocking self-registration

| Field | Detail |
|---|---|
| **Severity** | Low |
| **File** | `app/routes/users.py` |
| **Lines** | 51–52 |
| **Affected URL** | `POST /v1/users/register` |

**Description:**
The `POST /v1/users/register` endpoint requires `Permission.USER_CREATE`, which is an admin-level permission. This means new users cannot self-register without an existing admin account. If the intent is to allow public registration, this endpoint should be unauthenticated.

---

#### BUG-L05 — `TaskExecutor.check_and_start_pending_tasks()` is never called automatically

| Field | Detail |
|---|---|
| **Severity** | Low |
| **File** | `app/services/task_executor.py` |
| **Lines** | 382–427 |

**Description:**
`check_and_start_pending_tasks()` checks for tasks whose dependencies have become satisfied and starts them. However, this method is never called when a task completes. Tasks with dependencies will remain stuck in `PENDING` status indefinitely unless the caller manually triggers this check.

**Fix:** Call `check_and_start_pending_tasks(session_id)` at the end of each Celery task's completion callback.

---

#### BUG-L06 — Excessive `# type: ignore` annotations throughout route files

| Field | Detail |
|---|---|
| **Severity** | Low |
| **File** | `app/routes/users.py`, `app/routes/tasks.py`, `app/routes/sessions.py` |

**Description:**
Over 30 `# type: ignore[arg-type]` annotations are used when passing SQLAlchemy ORM column values to Pydantic models. This suppresses real type mismatch warnings that indicate the ORM model and Pydantic schema types are misaligned, hiding potential runtime errors.

**Fix:** Ensure ORM model columns and Pydantic response schema fields use compatible types, then remove `# type: ignore` annotations.

---

## 5. Missing Features & Incomplete Implementations

| ID | Feature | Expected Location | Status |
|---|---|---|---|
| MF-01 | `POST /v1/sessions/{id}/step` — single simulation step execution | `app/routes/sessions.py` | Not implemented (method exists in service, no route) |
| MF-02 | `POST /v1/auth/logout` — token revocation / session invalidation | `app/routes/auth.py` | Not implemented (service method exists, no route) |
| MF-03 | API key management — create, list, revoke API keys | `app/routes/api_keys.py` (missing) | Entirely absent; auth middleware has non-functional stub |
| MF-04 | Real-time data streaming / WebSocket support | N/A | No WebSocket or SSE endpoints for live simulation data |
| MF-05 | Dashboard data visualisation charts | `GET /v1/dashboard/html` | Placeholder `<div>` boxes only; no real chart rendering |
| MF-06 | Full simulation state serialisation on pause | `app/services/session_manager.py` | Only `time` and `history` serialised; all subsystem state is lost |
| MF-07 | User email verification workflow | `app/routes/users.py`, `app/services/` | No email sending, no verification token, no confirm endpoint |
| MF-08 | Webhook delivery management endpoints | `app/routes/webhooks.py` (missing) | `WebhookDelivery` model and `WebhookManager` service exist; no routes |
| MF-09 | OpenTelemetry instrumentation wiring | `app/tracing.py` | `configure_distributed_tracing()` is a stub; no actual spans configured |
| MF-10 | `GET /v1/sessions/{id}/step` (idempotent step info) | `app/routes/sessions.py` | Not documented, not implemented |
| MF-11 | `DELETE /v1/tasks/{id}` response model | `app/routes/tasks.py` | Returns raw dict; no declared `response_model` |
| MF-12 | `PATCH` endpoints for partial updates | All resource routes | Only `PUT` (full replacement) is implemented; no `PATCH` |

---

## 6. Security Audit

| Issue | Severity | Location | Detail |
|---|---|---|---|
| **SEC-01** API Key auth non-functional | Critical | `middleware/authentication.py:257–280` | SHA-256 hash compared to plain-text keys; no DB table for API keys. |
| **SEC-02** IDOR — session ownership not checked | Critical | `routes/sessions.py` (all `/{session_id}/*`) | Any authenticated user can access any session by UUID. |
| **SEC-03** Hardcoded default admin password | High | `routes/users.py:125` | `"secure_password"` is hardcoded and returned in response. |
| **SEC-04** Plaintext password in reset response | High | `routes/users.py:411` | New password returned in JSON body — appears in logs. |
| **SEC-05** No logout / token revocation endpoint | High | `routes/auth.py` | Tokens cannot be invalidated; stolen tokens remain valid until expiry. |
| **SEC-06** bcrypt 72-byte truncation unhandled | Low | `services/auth_manager.py` | Passwords > 72 bytes silently truncated; users may believe full length is enforced. |

---

## 7. Performance Assessment

| Area | Finding | Impact |
|---|---|---|
| **Template count query** | `fetchall()` used to count rows (BUG-H04) | High — full table scan in Python memory |
| **Synchronous DB in async routes** | `SessionLocal()` (sync) called inside `async def` handlers in authentication middleware | Medium — can block the event loop under load |
| **Redis caching** | Dashboard data cached for 15 min; API responses cached | Positive |
| **GZip compression** | Enabled via Starlette middleware (min 1 KB) | Positive |
| **Connection pooling** | SQLAlchemy connection pool configured | Positive |
| **Celery retry with backoff** | `retry_with_backoff()` implemented for Celery submissions | Positive |
| **Rate limiting** | Redis sliding-window rate limiter; configurable per-user and per-IP | Positive |
| **Session state** | `get_state()` called multiple times per request in some endpoints (state + metrics) | Low — redundant async calls |

---

## 8. Code Quality Assessment

| Metric | Observation |
|---|---|
| **Architecture** | Clean separation: routes → services → models → database. Middleware stack well-defined. Dependency injection via FastAPI `Depends`. |
| **Typing** | Pydantic v2 schemas throughout. However, 30+ `# type: ignore` annotations suppress real mismatches. |
| **Async consistency** | Routes are `async def`; however, some use synchronous SQLAlchemy sessions (`SessionLocal`) rather than `AsyncSession`, risking event-loop blocking. |
| **Error handling** | Custom exception classes (`SessionNotFoundError`, `ServiceUnavailableError`, etc.) and global handlers registered in `main.py`. |
| **Logging** | Structured per-module logging; request/response timing in `RequestLoggingMiddleware`. |
| **Duplication** | `_is_public_path` logic and `PUBLIC_PATHS` are defined only once; minor import duplication in `version.py`. |
| **Dead code** | `_redis_client` and `_session_manager` globals in `templates.py` are initialised to `None` and never used. |
| **Deprecated APIs** | `datetime.utcnow()` used in 6+ files; deprecated since Python 3.12. |

---

## 9. Test Coverage Assessment

| Test Category | Files Found | Quality Observation |
|---|---|---|
| **Unit** | `tests/unit/` | Present; covers individual service components |
| **Integration** | `tests/integration/` | Smoke tests, user/session/task/state/monitoring integration present |
| **End-to-End** | `tests/e2e/` | Full workflow scenarios present |
| **Property-based** | `tests/property/` | Hypothesis tests for auth, sessions, tasks, config, CORS, CSRF, logging, compression |
| **Load** | `tests/load/` | Locust configuration present |
| **Gaps** | — | No test validates that `create_session` assigns the correct `user_id`. No test covers API key auth path. No test for `GET /v1/client-docs` (which crashes). No test for session IDOR. No test for `POST /v1/sessions/{id}/step` (endpoint is missing). |

---

## 10. Deployment & Infrastructure Assessment

| Area | Status | Notes |
|---|---|---|
| **Docker** | Production-ready | Multi-stage build, non-root UID 1000, health checks, 4 Uvicorn workers |
| **Docker Compose** | Present | PostgreSQL 14, Redis 7, API, Celery worker — all with health checks |
| **Kubernetes** | Manifests present | Deployment, Service, ConfigMap, HPA indicated |
| **Terraform** | Configs present | IaC for infrastructure provisioning |
| **Database migrations** | Alembic configured | 4 migration versions present |
| **Environment files** | `.env.example`, `.env.development`, `.env.production.template` present | Production file requires secure values before deployment |
| **Health probes** | `/health/live`, `/health/ready`, `/health` | Liveness is correct lightweight check; readiness duplicates full health check (see BUG-L03) |
| **Secrets management** | No secrets manager integration | JWT secret and DB credentials loaded from env vars only; no Vault / AWS Secrets Manager |

---

## 11. Actionable Recommendations

### Immediate (Pre-Production Blockers)

1. **Fix `/v1/client-docs` crash (BUG-C01):** Replace `{{ }}` set literals with `{ }` dict literals in `routes/version.py`.

2. **Fix API key authentication (BUG-C02):** Either implement a proper `api_keys` database table with hashed key lookup, or disable the API key auth path until it is implemented. Do not leave a silently failing auth path in production.

3. **Fix session user attribution (BUG-C03):** Pass `current_user.user_id` to `SessionManager.create_session()`.

4. **Add session ownership checks (BUG-C04):** After loading a session in each route, verify `session.user_id == current_user.user_id`; raise HTTP 403 otherwise.

5. **Remove hardcoded credentials (BUG-M01, SEC-03):** Replace the hardcoded `"secure_password"` with a generated random password or a required request body field.

### Short-term (Next Sprint)

6. **Add `POST /v1/sessions/{id}/step` route (BUG-H01):** Wire the existing `SimulationSession.step()` method to an HTTP endpoint.

7. **Fix templates router prefix (BUG-H03):** Change `prefix="/templates"` to `prefix="/v1/templates"`.

8. **Replace template count `fetchall()` with SQL `COUNT` (BUG-H04):** Use `select(func.count()).select_from(...)`.

9. **Add `POST /v1/auth/logout` endpoint (BUG-H08):** Wire `auth_manager.revoke_refresh_token()` to a logout route.

10. **Fix middleware ordering (BUG-H07):** Ensure `AuthenticationMiddleware` is outermost (registered last via `add_middleware`).

11. **Stop returning plaintext passwords in responses (BUG-M02, SEC-04):** Remove `password` / `new_password` from `UserCreateResponse` and `PasswordResetResponse`.

### Medium-term (Backlog)

12. **Implement full state serialisation for pause/resume (BUG-H02, MF-06):** Serialise all `APGISystem` subsystem states to the database on pause; restore them fully on resume.

13. **Implement API key management routes (MF-03):** Create `POST /v1/api-keys`, `GET /v1/api-keys`, `DELETE /v1/api-keys/{id}` with proper database-backed hashed key storage.

14. **Add pagination to `GET /v1/users` (BUG-M03):** Apply the same offset-based pagination pattern used in sessions.

15. **Add `CANCELLED` task status (BUG-H09):** Distinguish cancelled tasks from failed tasks in the `TaskStatus` enum.

16. **Add `priority` field to `TaskSubmitRequest` (BUG-M08):** Expose the existing priority parameter in the task submission API.

17. **Fix ignition history signal/threshold values (BUG-H06):** Store per-timestep ignition signal and threshold in the `history` data structure.

18. **Separate `PaginationInfo` schemas (BUG-M07):** Define `OffsetPaginationInfo` and `CursorPaginationInfo` to avoid schema ambiguity.

19. **Wire OpenTelemetry instrumentation (MF-09):** Implement `configure_distributed_tracing()` with actual span creation and exporter configuration.

20. **Implement webhook delivery routes (MF-08):** Expose `WebhookManager` functionality via API endpoints.

21. **Replace `datetime.utcnow()` everywhere (BUG-M09):** Use `datetime.now(timezone.utc)` throughout the codebase.

22. **Implement bcrypt pre-hash (BUG-L02):** Add HMAC-SHA256 pre-hashing or a max-length validation to prevent silent password truncation.

23. **Wire `check_and_start_pending_tasks()` to task completion (BUG-L05):** Call this method in Celery task completion callbacks so dependency chains execute automatically.

---

## 12. Remediation Priority Matrix

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         REMEDIATION PRIORITY                             │
│                                                                          │
│  HIGH IMPACT │ BUG-C01  BUG-C02  BUG-C03  BUG-C04  SEC-03  SEC-04      │
│  (Fix Now)   │ BUG-H01  BUG-H03  BUG-H07  BUG-H08  BUG-H09             │
│──────────────┼──────────────────────────────────────────────────────────│
│  HIGH IMPACT │ BUG-H02  BUG-H04  BUG-H05  BUG-H06  MF-03   MF-06       │
│  (Next       │ BUG-M01  BUG-M02  BUG-M03  BUG-M08  MF-08   BUG-L05     │
│   Sprint)    │                                                            │
│──────────────┼──────────────────────────────────────────────────────────│
│  LOW-MED     │ BUG-M04  BUG-M06  BUG-M07  BUG-M09  MF-04   MF-05       │
│  IMPACT      │ BUG-L01  BUG-L02  BUG-L03  BUG-L04  BUG-L06  MF-09      │
│  (Backlog)   │                                                            │
└──────────────────────────────────────────────────────────────────────────┘
```

---

*Report generated by automated end-to-end audit on 2026-02-20. All findings are based on static code analysis of the committed source at branch `claude/app-audit-testing-X8RlG`. Dynamic runtime testing against a live environment is recommended to validate fixes and discover additional runtime-only defects.*
