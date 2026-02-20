# APGI API — Comprehensive Application Audit Report

**Date:** 2026-02-20
**Auditor:** Claude Code (Automated Static & Structural Analysis)
**Repository:** `lesoto/apgi-api`
**Branch audited:** `main`
**Audit scope:** Full codebase static analysis — routes, services, middleware, models, tests, configuration, deployment assets

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [KPI Scores](#2-kpi-scores)
3. [Application Overview](#3-application-overview)
4. [Bug Inventory](#4-bug-inventory)
   - [Critical Severity](#41-critical-severity)
   - [High Severity](#42-high-severity)
   - [Medium Severity](#43-medium-severity)
   - [Low Severity](#44-low-severity)
5. [Missing Features & Incomplete Implementations](#5-missing-features--incomplete-implementations)
6. [Test Coverage Analysis](#6-test-coverage-analysis)
7. [Security Findings](#7-security-findings)
8. [Actionable Recommendations](#8-actionable-recommendations)
9. [Appendix — Route Inventory](#9-appendix--route-inventory)

---

## 1. Executive Summary

The APGI API is a FastAPI-based REST backend for a consciousness-modeling simulation system ("APGI System"). It provides session lifecycle management, experimental task execution via Celery, user/auth management, data export, Prometheus metrics, and webhook delivery. The codebase is **structurally well-organised** with a clear layer separation (routes → services → models → database), strong exception taxonomy, good middleware coverage, and production-ready deployment assets.

However, this audit uncovered **3 critical bugs**, **4 high-severity bugs**, **8 medium-severity bugs**, and **8 low-severity bugs**, plus **8 missing or incomplete feature areas**. The most severe findings are:

- **The rate-limiter is a non-functional stub** — it never throttles any request regardless of configuration.
- **The core `apgi_system` dependency is absent from `requirements.txt`** — every session-creation call will throw `ModuleNotFoundError` on a clean install.
- **Two entire route groups (`/v1/api-keys`, `/v1/webhooks`) are implemented but never registered** — they return 404 for all calls.
- **The default `"user"` RBAC role has zero permissions** — newly registered users cannot perform any protected operation after logging in.
- **Session ownership is not enforced on task submission or data export endpoints**, creating a cross-user data-access vulnerability.

Overall test coverage stands at **48%**, with several critical service files at 0%.

The application should not be promoted to a production environment until the critical and high-severity issues are remediated.

---

## 2. KPI Scores

| # | KPI | Score | Rationale |
|---|-----|-------|-----------|
| 1 | **Functional Completeness** | **52 / 100** | Core auth, session CRUD, task dispatch, export, health, and Prometheus metrics are structurally present. However: rate limiting is a stub (never fires), two route groups are unreachable, the core APGI engine dependency is missing from requirements, and the default RBAC role grants no permissions. |
| 2 | **UI/UX Consistency** | **61 / 100** | Mostly consistent REST design — uniform error envelope, versioned prefixes, standard HTTP status codes. Deductions for: no pagination metadata on `GET /v1/users`, inconsistent session-ownership enforcement, inconsistent route-init pattern (templates vs others), and ignition-history pagination silently discarded. |
| 3 | **Responsiveness & Performance** | **58 / 100** | Async FastAPI, Redis caching, Celery task queue, and PostgreSQL connection pooling are correctly applied. Deductions for: entire user list fetched to memory before Python-slice pagination, rate limiting completely disabled (no actual throttling), and the missing APGI engine would block all simulation work at runtime. |
| 4 | **Error Handling & Resilience** | **63 / 100** | Rich exception hierarchy, global handlers covering `APIError`, Pydantic validation, HTTP exceptions, and a catch-all 500 handler are well-designed. Deductions for: error-recovery service at 0% coverage and unclear integration, unreachable null-checks creating maintenance confusion, opaque Celery errors for unknown task types, and webhook/task result-fetching paths not covered by tests. |
| 5 | **Overall Implementation Quality** | **58 / 100** | Code style is consistent and idiomatic FastAPI/SQLAlchemy. Deductions for: stub implementations masked as production-ready features, 48% test coverage, missing `README.md`, critical dependency absent from requirements, bcrypt version constraint violated in the installed environment, and non-UUID primary key set for the default system user. |

---

## 3. Application Overview

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.110+ / Uvicorn |
| ORM | SQLAlchemy 2.0 |
| Database | PostgreSQL (psycopg2 / asyncpg) |
| Cache / Broker | Redis 5.0+ |
| Task Queue | Celery 5.3+ |
| Auth | JWT (PyJWT) + bcrypt, API-key support |
| Metrics | Prometheus (`prometheus-client`) |
| Tracing | OpenTelemetry (optional / conditional import) |
| Deployment | Docker + docker-compose, Kubernetes manifests, Terraform |

### Registered Route Groups

| Prefix | Tags | Status |
|--------|------|--------|
| `/v1/auth` | Authentication | ✅ Registered |
| `/v1/users` | User Management | ✅ Registered |
| `/v1/sessions` | Session Management | ✅ Registered |
| `/v1/sessions` | Session State | ✅ Registered |
| `/v1/sessions` | Data Export | ✅ Registered |
| `/v1` | Tasks | ✅ Registered |
| `/v1` | Metrics / Dashboard | ✅ Registered |
| `/v1/templates` | Session Templates | ✅ Registered |
| `/health` | Health Checks | ✅ Registered |
| `/version` | Version Info | ✅ Registered |
| `/v1/api-keys` | API Key Management | ❌ **NOT registered** |
| `/v1/webhooks` | Webhook Delivery Mgmt | ❌ **NOT registered** |

---

## 4. Bug Inventory

### 4.1 Critical Severity

---

#### BUG-C01 — Rate Limiter Is a Non-Functional Stub

| Field | Detail |
|-------|--------|
| **Severity** | Critical |
| **Component** | `app/services/rate_limiter.py` |
| **Affected Endpoints** | All protected endpoints |

**Description:**
`RateLimiter.check_rate_limit()` unconditionally returns `(True, 60, 60)` and `increment()` unconditionally returns `1`. No Redis calls are made. The rate-limiting middleware invokes this service and believes all requests are within limits.

**Reproduction Steps:**
1. Configure `RATE_LIMIT_ENABLED=true`, `RATE_LIMIT_PER_MINUTE=1`.
2. Send 100 rapid successive authenticated requests to any endpoint.
3. **Observed:** All requests succeed (200/201/202).
4. **Expected:** Requests 2–100 receive `429 Too Many Requests`.

**Root Cause (code reference):**
```python
# app/services/rate_limiter.py  lines 39-50
async def check_rate_limit(self, key: str) -> tuple[bool, int, int]:
    # Stub implementation for testing
    return (True, self.requests_per_minute, 60)   # ← always allowed

async def increment(self, key: str) -> int:
    # Stub implementation
    return 1                                        # ← no Redis write
```

**Expected vs Actual:**

| | Expected | Actual |
|-|----------|--------|
| Behavior | Enforces `RATE_LIMIT_PER_MINUTE` using Redis sliding window | Never throttles any request |
| Redis usage | Increments key, sets TTL | No Redis interaction |

---

#### BUG-C02 — Core `apgi_system` Dependency Missing From `requirements.txt`

| Field | Detail |
|-------|--------|
| **Severity** | Critical |
| **Component** | `app/services/session_manager.py:25`, `requirements.txt` |
| **Affected Endpoints** | `POST /v1/sessions`, all session state/step endpoints |

**Description:**
`SessionManager` imports `from apgi_system.system import APGISystem` at module load time. The `apgi_system` package is **not listed** in `requirements.txt`, `requirements-dev.txt`, or `pyproject.toml` dependencies. Running `pip install -r requirements.txt` on a fresh environment produces `ModuleNotFoundError: No module named 'apgi_system'`, preventing the application from starting.

**Reproduction Steps:**
1. Clone the repository into a fresh virtualenv.
2. Run `pip install -r requirements.txt`.
3. Run `python -m app.main` (or `uvicorn app.main:app`).
4. **Observed:** `ModuleNotFoundError: No module named 'apgi_system'` — application fails to start.
5. **Expected:** Application starts successfully.

**Expected vs Actual:**

| | Expected | Actual |
|-|----------|--------|
| `requirements.txt` | Declares all runtime dependencies | Missing `apgi_system` |
| Fresh install | Application starts | `ModuleNotFoundError` at import |

---

#### BUG-C03 — API Key and Webhook Route Groups Implemented but Never Registered

| Field | Detail |
|-------|--------|
| **Severity** | Critical |
| **Component** | `app/routes/api_keys.py`, `app/routes/webhooks.py`, `app/routes/__init__.py`, `app/main.py:316-325` |
| **Affected Endpoints** | `/v1/api-keys/*`, `/v1/webhooks/*` |

**Description:**
Two complete route modules exist with full CRUD implementations:
- `app/routes/api_keys.py` — create, list, get, update, delete, rotate API keys
- `app/routes/webhooks.py` — list, retry, get webhook deliveries

Neither module is imported in `app/routes/__init__.py` nor passed to `app.include_router()` in `app/main.py`. Every request to these paths returns **404 Not Found**.

**Reproduction Steps:**
1. Start the application.
2. `GET /v1/api-keys` with a valid Bearer token.
3. **Observed:** `404 Not Found`.
4. **Expected:** List of API keys for the authenticated user.

**Root Cause:**
```python
# app/main.py lines 316-325 — missing includes:
app.include_router(auth.router)
app.include_router(users.router)
...
# app/routes/api_keys.router  ← MISSING
# app/routes/webhooks.router  ← MISSING
```

---

### 4.2 High Severity

---

#### BUG-H01 — RBAC `"user"` Role Has Zero Permissions; Newly Registered Users Cannot Do Anything

| Field | Detail |
|-------|--------|
| **Severity** | High |
| **Component** | `app/routes/users.py:79`, `app/services/authorization.py:70-130`, `app/database/connection.py:136` |
| **Affected Endpoints** | All permission-gated endpoints for users registered via `POST /v1/users/register` |

**Description:**
`POST /v1/users/register` assigns `roles=["user"]` to every new account. The `ROLE_PERMISSIONS` map in `authorization.py` only defines permissions for `Role.ADMIN`, `Role.RESEARCHER`, and `Role.VIEWER` — the string `"user"` is absent. `get_permissions_for_roles(["user"])` returns an empty set, so every `require_permission()` check fails with `403 Forbidden`.

**Reproduction Steps:**
1. `POST /v1/users/register` with valid credentials → 201 Created.
2. `POST /v1/auth/login` with the new credentials → 200, receive tokens.
3. `GET /v1/sessions` with Bearer token.
4. **Observed:** `403 Forbidden — Insufficient permissions`.
5. **Expected:** Empty session list with 200.

**Root Cause:**
```python
# app/routes/users.py:79
roles=["user"],          # ← "user" not in ROLE_PERMISSIONS

# app/services/authorization.py:70-130
ROLE_PERMISSIONS = {
    Role.ADMIN: { ... },      # "admin"
    Role.RESEARCHER: { ... }, # "researcher"
    Role.VIEWER: { ... },     # "viewer"
    # "user" ← missing
}
```

---

#### BUG-H02 — Task Submission Lacks Session Ownership Validation

| Field | Detail |
|-------|--------|
| **Severity** | High |
| **Component** | `app/routes/tasks.py:98-145` |
| **Affected Endpoints** | `POST /v1/sessions/{session_id}/tasks` |

**Description:**
`execute_task()` does not call `validate_session_ownership()`. Any authenticated user with `TASK_CREATE` permission can submit tasks to a session owned by another user, consuming resources and potentially manipulating another user's experiment.

**Reproduction Steps:**
1. User A creates session `sess-A`.
2. User B (with `TASK_CREATE` permission) submits `POST /v1/sessions/sess-A/tasks` with a valid task payload.
3. **Observed:** `202 Accepted` — task queued against User A's session.
4. **Expected:** `403 Forbidden` (or `404` to avoid session enumeration).

---

#### BUG-H03 — Data Export Endpoints Lack Session Ownership Validation

| Field | Detail |
|-------|--------|
| **Severity** | High |
| **Component** | `app/routes/export.py:75-140, 144-210, 214-280, 284-350` |
| **Affected Endpoints** | `GET /v1/sessions/{session_id}/export`, `/summary`, `/events`, `/metrics` |

**Description:**
None of the four export endpoints call `validate_session_ownership()`. A user with `DATA_EXPORT` or `DATA_READ` permission can download the full simulation history of any other user's session by guessing or enumerating a session UUID.

---

#### BUG-H04 — `bcrypt` Version Constraint Violated in Installed Environment

| Field | Detail |
|-------|--------|
| **Severity** | High |
| **Component** | `requirements.txt:15` |
| **Affected Systems** | All deployment environments |

**Description:**
`requirements.txt` declares `bcrypt>=4.0.0,<5.0.0`, but bcrypt 5.0.0 is installed. bcrypt 5.x introduced API changes (`bcrypt.checkpw` signature changes, `__about__` module removal). Deployments that `pip install -r requirements.txt` may silently install 5.x (pip resolves `>=4.0.0` ignoring `<5.0.0` if the constraint is not honoured by the resolver), and authentication may break depending on the Python/pip version.

---

### 4.3 Medium Severity

---

#### BUG-M01 — Ignition History Pagination Cursor Silently Discarded

| Field | Detail |
|-------|--------|
| **Severity** | Medium |
| **Component** | `app/routes/state.py:265-280` |
| **Affected Endpoints** | `GET /v1/sessions/{session_id}/ignition-history` |

**Description:**
`next_cursor` is computed correctly and base64-encoded, but `IgnitionHistoryResponse` is instantiated with `pagination=None`, discarding it. Clients cannot paginate through ignition history regardless of how many events exist.

**Root Cause:**
```python
# app/routes/state.py lines 276-279
next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()

response = IgnitionHistoryResponse(
    events=paginated_events,
    pagination=None,          # ← next_cursor is computed above but never used
)
```

**Expected vs Actual:**

| | Expected | Actual |
|-|----------|--------|
| Response `pagination` field | Contains `next_cursor` when more data exists | Always `null` |

---

#### BUG-M02 — Prometheus Metrics Endpoint Not in `PUBLIC_PATHS`

| Field | Detail |
|-------|--------|
| **Severity** | Medium |
| **Component** | `app/middleware/authentication.py:54-65`, `app/routes/metrics.py:42` |
| **Affected Endpoints** | `GET /v1/metrics` |

**Description:**
`AuthenticationMiddleware.PUBLIC_PATHS` includes `"/metrics"` but the Prometheus endpoint is mounted at `/v1/metrics` (via `APIRouter(prefix="/v1")`). Prometheus scrapers sending unauthenticated requests receive `401 Unauthorized`.

**Root Cause:**
```python
# app/middleware/authentication.py:62
PUBLIC_PATHS = { "/metrics", ... }   # ← /metrics

# app/routes/metrics.py:42 — served at /v1/metrics
@router.get("/metrics")              # prefix="/v1" → /v1/metrics
```

---

#### BUG-M03 — `extero_input` Declared as Query Parameter Instead of Request Body

| Field | Detail |
|-------|--------|
| **Severity** | Medium |
| **Component** | `app/routes/sessions.py:646` |
| **Affected Endpoints** | `POST /v1/sessions/{session_id}/step` |

**Description:**
`extero_input: Optional[Dict[str, Any]] = None` lacks a `Body()` annotation. FastAPI interprets untyped dict parameters without `Body()` as query parameters. Dictionaries cannot be serialised into URL query strings; any caller sending a JSON body for `extero_input` will find it silently ignored, and the step will always execute with an empty input.

**Root Cause:**
```python
# app/routes/sessions.py:646
async def step_session(
    session_id: str,
    extero_input: Optional[Dict[str, Any]] = None,   # ← missing Body()
    ...
```

**Expected vs Actual:**

| | Expected | Actual |
|-|----------|--------|
| `extero_input` source | JSON request body | Query string (not parseable for dicts) |
| Behaviour with body payload | Reads input | Silently uses `{}` |

---

#### BUG-M04 — `GET /v1/users` Loads All Users into Memory Before Pagination

| Field | Detail |
|-------|--------|
| **Severity** | Medium |
| **Component** | `app/routes/users.py:178-182`, `app/services/user_management.py:73-84` |
| **Affected Endpoints** | `GET /v1/users` |

**Description:**
`user_service.list_users(active_only=active_only)` is called without the `skip`/`limit` parameters the service supports. All matching users are fetched into memory, then Python list-slicing is used for pagination. For large user bases this causes excess memory consumption and slow responses.

**Root Cause:**
```python
# app/routes/users.py:178-182
users = user_service.list_users(active_only=active_only)  # fetches ALL
offset = (page - 1) * per_page
paginated_users = users[offset : offset + per_page]        # then slices
```

---

#### BUG-M05 — `GET /v1/users` Returns Plain List Without Pagination Metadata

| Field | Detail |
|-------|--------|
| **Severity** | Medium |
| **Component** | `app/routes/users.py:147, 184-199` |
| **Affected Endpoints** | `GET /v1/users` |

**Description:**
All other list endpoints (`/v1/sessions`, `/v1/tasks`, `/v1/templates`, etc.) return a `*ListResponse` wrapper with a `PaginationInfo` object (total count, page, per_page). `GET /v1/users` returns a bare `List[UserResponse]`, forcing clients to guess the total count and detect end-of-list by receiving fewer results than requested.

---

#### BUG-M06 — Unreachable `if not user:` Null Check in Route Handlers

| Field | Detail |
|-------|--------|
| **Severity** | Medium (code quality / maintenance) |
| **Component** | `app/routes/users.py:223, 298` |
| **Affected Endpoints** | `GET /v1/users/me`, `GET /v1/users/{user_id}` |

**Description:**
`UserManagementService.get_user()` always raises `UserNotFoundError` when a user is not found — it never returns `None`. Both `get_current_user_profile` and `get_user` route handlers contain `if not user: raise HTTPException(404)` which is **dead code**. The `UserNotFoundError` is handled correctly by the global `api_error_handler`, so the observed 404 response is correct — but the dead guard creates a false impression of safety and obscures the actual control flow from maintainers.

---

#### BUG-M07 — Task Type Not Validated Against Known Task Types at Submission Time

| Field | Detail |
|-------|--------|
| **Severity** | Medium |
| **Component** | `app/models/schemas.py:729-737`, `app/services/task_executor.py:TASK_MAP` |
| **Affected Endpoints** | `POST /v1/sessions/{session_id}/tasks` |

**Description:**
`TaskSubmitRequest.validate_task_type()` only rejects empty strings. Any non-empty string (e.g. `"invalid_task"`) passes schema validation. The task is submitted to Celery, which then fails with an opaque internal error when it tries to look up an unrecognised Celery task name. Clients receive a `500 Internal Server Error` instead of a descriptive `400 Bad Request`.

---

#### BUG-M08 — Negative Numeric Task Parameter Values Unconditionally Rejected

| Field | Detail |
|-------|--------|
| **Severity** | Medium |
| **Component** | `app/models/schemas.py:750-753` |
| **Affected Endpoints** | `POST /v1/sessions/{session_id}/tasks` |

**Description:**
`validate_parameters()` raises `ValueError` for any negative numeric value. This is overly restrictive: parameters like `start_time_ms=-500` (relative offsets), `temperature_delta=-2.0`, or other signed floats are legitimate in experimental contexts. The restriction is not documented in the API spec or parameter descriptions.

---

### 4.4 Low Severity

---

#### BUG-L01 — Default System User Created with Non-UUID `user_id`

| Field | Detail |
|-------|--------|
| **Severity** | Low |
| **Component** | `app/database/connection.py:133` |

**Description:**
`init_db()` sets `user_id=secure_username` where `secure_username` is `"apgi_<16-char-hex>"` (e.g. `apgi_a1b2c3d4e5f6a7b8`). The `User.user_id` column is typed `String(36)` and by convention stores UUIDs (`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`). This creates a schema-convention violation and may break UUID-validation utilities that operate on user IDs.

---

#### BUG-L02 — Undefined `"session_manager"` Role Assigned to Default System User

| Field | Detail |
|-------|--------|
| **Severity** | Low |
| **Component** | `app/database/connection.py:136` |

**Description:**
The default user created by `init_db()` receives `roles=["user", "session_manager"]`. Neither role exists in `ROLE_PERMISSIONS`. The `"session_manager"` role grants no permissions and exists nowhere else in the codebase.

---

#### BUG-L03 — `X-API-Key` Authenticated Requests Not Excluded From CSRF Protection

| Field | Detail |
|-------|--------|
| **Severity** | Low |
| **Component** | `app/middleware/csrf.py:_should_protect()` |

**Description:**
`_should_protect()` skips CSRF for `Authorization: Bearer` (JWT) requests but not for `X-API-Key` requests. Non-JWT API-key clients sending `POST`/`PUT`/`DELETE` with form-encoded bodies (`application/x-www-form-urlencoded`) will be blocked by the CSRF middleware even though API keys are not susceptible to CSRF.

---

#### BUG-L04 — `init_template_routes()` Defined but Never Called

| Field | Detail |
|-------|--------|
| **Severity** | Low |
| **Component** | `app/routes/templates.py:32`, `app/main.py:151-165` |

**Description:**
Every other router that requires state initialisation (`sessions`, `tasks`, `export`, `health`) is initialised via a dedicated `init_*_routes()` call in `main.py`'s startup lifecycle. `init_template_routes()` is defined in `templates.py` but never called. The templates router works because it directly calls `get_db_context()` inline, but the inconsistency is a maintenance hazard.

---

#### BUG-L05 — OpenTelemetry Dependencies Not Listed in `requirements.txt`

| Field | Detail |
|-------|--------|
| **Severity** | Low |
| **Component** | `app/tracing.py`, `app/middleware/tracing.py`, `requirements.txt` |

**Description:**
Both tracing modules import `opentelemetry.*` packages that are absent from `requirements.txt`. The imports are wrapped in `try/except` with a graceful fallback, so the application continues running — but tracing is silently disabled on every install, and the feature is effectively non-deployable without undocumented additional steps.

---

#### BUG-L06 — `create_default_user` API Endpoint Creates User With No Permissions

| Field | Detail |
|-------|--------|
| **Severity** | Low |
| **Component** | `app/routes/users.py:102-135`, `app/services/user_management.py:85-96` |

**Description:**
`POST /v1/users/create-default` (admin-only) calls `create_default_user()` which calls `create_user(roles=["user"])`. The resulting "default" user has no permissions (see BUG-H01). The endpoint's own docstring says "Create a default admin user for initial system setup", yet the created user is not an admin.

---

#### BUG-L07 — `UserStatsResponse` Role Counts Use Array Stringification as Key

| Field | Detail |
|-------|--------|
| **Severity** | Low |
| **Component** | `app/services/user_management.py:241-243` |

**Description:**
`get_user_stats()` groups users by the `roles` ARRAY column and stringifies the result: `{str(roles): count}`. This produces keys like `"['admin', 'researcher']"` instead of per-role counts. Consumers of `GET /v1/users/stats` receive an unparseable role breakdown.

---

#### BUG-L08 — No `README.md` at Project Root

| Field | Detail |
|-------|--------|
| **Severity** | Low |
| **Component** | Repository root |

**Description:**
`pyproject.toml` declares `readme = "README.md"`, but no such file exists. `pip install .` emits a warning. New contributors and the GitHub repository page show no documentation.

---

## 5. Missing Features & Incomplete Implementations

| # | Feature | Location | Status | Notes |
|---|---------|----------|--------|-------|
| MF-01 | **API Key Management** | `app/routes/api_keys.py` | Code complete, **not registered** | Full CRUD exists; router not included in `main.py`. See BUG-C03. |
| MF-02 | **Webhook Delivery Management** | `app/routes/webhooks.py` | Code complete, **not registered** | Retry, list, get endpoints exist; router not included in `main.py`. See BUG-C03. |
| MF-03 | **Rate Limiting** | `app/services/rate_limiter.py` | **Stub only** | Both methods return hardcoded constants. See BUG-C01. |
| MF-04 | **APGI Engine Integration** | `requirements.txt` | **Dependency missing** | `apgi_system` package not declared. See BUG-C02. |
| MF-05 | **Distributed Tracing** | `app/tracing.py`, `app/middleware/tracing.py` | Silently disabled | OpenTelemetry packages not in requirements. Falls back gracefully but feature never activates. |
| MF-06 | **Error Recovery Service** | `app/services/error_recovery.py` | 0% test coverage | Service exists but no integration point found in route handlers or startup; unclear if wired. |
| MF-07 | **Pagination metadata on `GET /v1/users`** | `app/routes/users.py` | Incomplete | Returns raw list; no `PaginationInfo` wrapper unlike all other list endpoints. See BUG-M05. |
| MF-08 | **Project README** | Repository root | Missing | `pyproject.toml` references it; file absent. See BUG-L08. |

---

## 6. Test Coverage Analysis

**Overall coverage: 48.2%** (2,833 / 5,882 statements executed)

### Files With Zero Coverage

| File | Statements | Notes |
|------|-----------|-------|
| `app/cli.py` | 89 | CLI entry points untested |
| `app/database/sharded_connection.py` | 94 | Sharding layer never exercised |
| `app/routes/api_keys.py` | 72 | Router not registered (BUG-C03) |
| `app/routes/webhooks.py` | 58 | Router not registered (BUG-C03) |
| `app/services/error_recovery.py` | 146 | No integration path found |
| `app/services/seeding_service.py` | 163 | Only used in CLI seeding scripts |
| `app/services/sharding_service.py` | 63 | Feature disabled by default |
| `app/tracing.py` | 50 | OpenTelemetry silently disabled |

### Files With Critically Low Coverage

| File | Coverage | Key Risk |
|------|---------|---------|
| `app/middleware/schema_validation.py` | 13% | Response contract violations go undetected |
| `app/services/data_export.py` | 14% | Export data integrity not validated |
| `app/services/webhook_manager.py` | 18% | Webhook retry logic untested |
| `app/tasks/experimental_tasks.py` | 18% | Core simulation task workers untested |
| `app/routes/templates.py` | 20% | Template CRUD largely untested |
| `app/services/profiling_service.py` | 23% | Profiling correctness not verified |

### Well-Covered Files (≥ 80%)

| File | Coverage |
|------|---------|
| `app/exceptions.py` | 100% |
| `app/models/schemas.py` | ~85% |
| `app/services/authorization.py` | ~82% |
| `app/services/auth_manager.py` | ~79% |
| `app/middleware/authentication.py` | ~76% |

---

## 7. Security Findings

| ID | Finding | Severity | Location |
|----|---------|---------|---------|
| SEC-01 | Rate limiting is a stub — no actual DoS protection | Critical | `app/services/rate_limiter.py` |
| SEC-02 | Cross-user task submission (no ownership check on task creation) | High | `app/routes/tasks.py` |
| SEC-03 | Cross-user data exfiltration (no ownership check on export) | High | `app/routes/export.py` |
| SEC-04 | New users registered with `"user"` role cannot function, but the role name leaks internal implementation detail | Medium | `app/routes/users.py` |
| SEC-05 | `POST /v1/users/register` is unauthenticated and unthrottled — vulnerable to account enumeration via timing + username/email uniqueness errors | Medium | `app/routes/users.py` |
| SEC-06 | JWT development default key (`development-secret-key-change-in-production-32-chars-min`) is hardcoded in config and logged as a warning but NOT blocked in non-production environments | Low | `app/config.py:191` |
| SEC-07 | `X-API-Key` clients not excluded from CSRF guard for form-body requests | Low | `app/middleware/csrf.py` |
| SEC-08 | Default user credentials logged at `WARNING` level (visible in aggregated log systems) | Low | `app/database/connection.py:122-129` |

---

## 8. Actionable Recommendations

### Priority 1 — Fix Before Any Production Deployment

1. **Implement `RateLimiter` with real Redis logic** (`app/services/rate_limiter.py`).
   Replace the stub with a sliding-window or token-bucket implementation using `EXPIRE`/`INCR` Redis commands.

2. **Add `apgi_system` to `requirements.txt`**.
   Determine the correct package name/source and pin the version. If it is a private package, add install instructions to `docs/DEPLOYMENT.md`.

3. **Register the `api_keys` and `webhooks` routers** in `app/main.py` and `app/routes/__init__.py`.

4. **Add `"user"` role to `ROLE_PERMISSIONS`** (`app/services/authorization.py`) **or** change `POST /v1/users/register` to assign `Role.RESEARCHER` (or similar valid role) by default.
   Consider whether open self-registration is the correct design; if not, require admin authentication for registration.

5. **Add `validate_session_ownership()` to task submission and all export endpoints**.
   Reuse the existing helper from `app/routes/sessions.py`.

### Priority 2 — Fix Within the Current Sprint

6. **Fix ignition history pagination**: pass `next_cursor` into `IgnitionHistoryResponse.pagination` (`app/routes/state.py:278`).

7. **Add `/v1/metrics` to `PUBLIC_PATHS`** in `app/middleware/authentication.py`.

8. **Fix `extero_input` to use `Body()`**:
   ```python
   from fastapi import Body
   extero_input: Optional[Dict[str, Any]] = Body(None)
   ```

9. **Push pagination down to the database** for `GET /v1/users`: pass `skip=(page-1)*per_page` and `limit=per_page` to `list_users()`, and return a `UserListResponse` wrapper with `PaginationInfo`.

10. **Validate task type at schema layer** against `TaskExecutor.TASK_MAP` keys; return `400` for unknown types.

### Priority 3 — Technical Debt (Next Release)

11. **Pin `bcrypt<5.0.0`** or upgrade and test against 5.x. Update `requirements.txt` to use `bcrypt>=4.0.0,<5.0.0` and pin in `requirements-dev.txt`.

12. **Add `README.md`** with quickstart, environment variable reference, and a link to `docs/`.

13. **Wire `error_recovery.py`** into the global exception handler or remove it if unused.

14. **Add OpenTelemetry packages** to an optional `requirements-tracing.txt` and document the opt-in.

15. **Fix `init_db()` default user**: use `str(uuid.uuid4())` as `user_id`, assign a valid role (`"admin"` or `Role.ADMIN.value`), and remove the undefined `"session_manager"` role.

16. **Call `init_template_routes()`** in `app/main.py` startup to match the pattern of all other route groups.

17. **Fix `UserStatsResponse` role counts**: group by individual role names, not array stringification.

18. **Remove unreachable `if not user:` guards** in `get_current_user_profile` and `get_user` routes; add `except UserNotFoundError` blocks to make the control flow explicit and testable.

19. **Increase test coverage** to ≥ 80%, prioritising: `experimental_tasks.py`, `data_export.py`, `webhook_manager.py`, `routes/api_keys.py`, `routes/webhooks.py`.

20. **Relax negative-value parameter validation** to only reject values where negativity is definitively invalid (document which parameters those are).

---

## 9. Appendix — Route Inventory

| Method | Path | Auth | Permission | Status |
|--------|------|------|-----------|--------|
| POST | `/v1/auth/login` | None | — | ✅ |
| POST | `/v1/auth/refresh` | None | — | ✅ |
| POST | `/v1/auth/logout` | Bearer | — | ✅ |
| POST | `/v1/users/register` | None | — | ✅ (open) |
| POST | `/v1/users/create-default` | Bearer | `USER_CREATE` | ⚠️ creates no-permission user |
| GET | `/v1/users` | Bearer | `USER_READ` | ⚠️ no pagination metadata |
| GET | `/v1/users/me` | Bearer | — | ✅ |
| GET | `/v1/users/stats` | Bearer | `USER_READ` | ⚠️ broken role-count key format |
| GET | `/v1/users/{user_id}` | Bearer | `USER_READ` | ✅ |
| PUT | `/v1/users/{user_id}` | Bearer | — (self or admin) | ✅ |
| POST | `/v1/users/{user_id}/reset-password` | Bearer | — (self or admin) | ✅ |
| DELETE | `/v1/users/{user_id}` | Bearer | `USER_DELETE` | ✅ |
| GET | `/v1/sessions` | Bearer | `SESSION_READ` | ✅ |
| POST | `/v1/sessions` | Bearer | `SESSION_CREATE` | ✅ |
| GET | `/v1/sessions/{session_id}` | Bearer | `SESSION_READ` | ✅ |
| DELETE | `/v1/sessions/{session_id}` | Bearer | `SESSION_DELETE` | ✅ |
| POST | `/v1/sessions/{session_id}/start` | Bearer | `SESSION_CONTROL` | ✅ |
| POST | `/v1/sessions/{session_id}/pause` | Bearer | `SESSION_CONTROL` | ✅ |
| POST | `/v1/sessions/{session_id}/stop` | Bearer | `SESSION_CONTROL` | ✅ |
| POST | `/v1/sessions/{session_id}/reset` | Bearer | `SESSION_CONTROL` | ✅ |
| POST | `/v1/sessions/{session_id}/step` | Bearer | `SESSION_CONTROL` | ⚠️ BUG-M03 (extero_input) |
| GET | `/v1/sessions/{session_id}/state` | Bearer | `SESSION_READ` | ✅ |
| GET | `/v1/sessions/{session_id}/ignition-history` | Bearer | `SESSION_READ` | ⚠️ BUG-M01 (pagination) |
| GET | `/v1/sessions/{session_id}/export` | Bearer | `DATA_EXPORT` | ⚠️ BUG-H03 (no ownership) |
| GET | `/v1/sessions/{session_id}/summary` | Bearer | `DATA_READ` | ⚠️ BUG-H03 (no ownership) |
| GET | `/v1/sessions/{session_id}/events` | Bearer | `DATA_READ` | ⚠️ BUG-H03 (no ownership) |
| GET | `/v1/sessions/{session_id}/metrics` | Bearer | `DATA_READ` | ⚠️ BUG-H03 (no ownership) |
| GET | `/v1/tasks` | Bearer | `TASK_READ` | ✅ |
| POST | `/v1/sessions/{session_id}/tasks` | Bearer | `TASK_CREATE` | ⚠️ BUG-H02 (no ownership) |
| GET | `/v1/tasks/{task_id}` | Bearer | `TASK_READ` | ✅ |
| GET | `/v1/tasks/{task_id}/result` | Bearer | `TASK_READ` | ✅ |
| DELETE | `/v1/tasks/{task_id}` | Bearer | `TASK_DELETE` | ✅ |
| POST | `/v1/tasks/{task_id}/dependencies` | Bearer | `TASK_CREATE` | ✅ |
| GET | `/v1/tasks/{task_id}/dependencies` | Bearer | `TASK_READ` | ✅ |
| DELETE | `/v1/tasks/{task_id}/dependencies/{id}` | Bearer | `TASK_DELETE` | ✅ |
| GET | `/v1/templates` | Bearer | — | ✅ |
| POST | `/v1/templates` | Bearer | — | ✅ |
| GET | `/v1/templates/{template_id}` | Bearer | — | ✅ |
| PUT | `/v1/templates/{template_id}` | Bearer | — | ✅ |
| DELETE | `/v1/templates/{template_id}` | Bearer | — | ✅ |
| GET | `/v1/metrics` | **Requires auth** | — | ⚠️ BUG-M02 (should be public) |
| GET | `/v1/dashboard/overview` | Bearer | `DATA_READ` | ✅ |
| GET | `/health` | None | — | ✅ |
| GET | `/health/ready` | None | — | ✅ |
| GET | `/health/live` | None | — | ✅ |
| GET | `/version` | None | — | ✅ |
| ALL | `/v1/api-keys/*` | — | — | ❌ BUG-C03 (not registered) |
| ALL | `/v1/webhooks/*` | — | — | ❌ BUG-C03 (not registered) |

---

*Report generated by automated static analysis of the `lesoto/apgi-api` repository on 2026-02-20.*
*For questions or clarifications, open an issue against the repository or contact the auditing team.*
