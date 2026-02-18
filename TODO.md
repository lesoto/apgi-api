## Bugs

## Missing Features

1. **Advanced Session Features**
   - Session templates: ❌ Not implemented
   - Batch session operations: ❌ Not implemented
   - Session cloning: ❌ Not implemented
   - Advanced configuration validation: ✅ Basic validation exists
   - Session sharing/collaboration: ❌ Not implemented

2. **Enhanced Task Management**
   - Task scheduling: ❌ Not implemented
   - Task dependencies: ❌ Not implemented
   - Task prioritization: ❌ Not implemented
   - Batch task operations: ❌ Not implemented
   - Task result caching: ❌ Not implemented

3. **Security Enhancements**
   - API key authentication: ❌ Not implemented
   - OAuth2 integration: ❌ Not implemented
   - Multi-factor authentication: ❌ Not implemented
   - Advanced rate limiting (user-based, tier-based): ⚠️ Basic rate limiting exists but has bugs
   - IP whitelisting/blacklisting: ❌ Not implemented

4. **Monitoring & Observability**
   - Distributed tracing: ❌ Not implemented
   - Business metrics dashboard: ❌ Not implemented
   - Alerting integration (Slack, PagerDuty): ⚠️ Basic alerting exists
   - Performance profiling: ❌ Not implemented
   - Error tracking integration: ❌ Not implemented

5. **Scalability Features**
   - Horizontal auto-scaling configuration: ❌ Not implemented
   - Load balancing setup: ❌ Not implemented
   - Database sharding strategy: ❌ Not implemented
   - Cache clustering: ❌ Not implemented

6. **Development Tools**
   - Comprehensive CLI tools: ❌ Not implemented
   - Development Docker Compose enhancements: ❌ Not implemented
   - Database seeding utilities: ❌ Not implemented
   - Performance testing tools: ❌ Not implemented
   - Missing integration test depth
   - No end-to-end testing
   - Limited performance testing

7. **Documentation**
   - Missing deployment examples
   - Limited troubleshooting guides
   - No developer tutorial

### 🔒 Security Concerns

1. **Default Credentials Risk**
   - Development JWT secret needs stronger warnings
   - Default user creation with predictable credentials
   - Missing secrets rotation strategy

2. **Authentication Gaps**
   - No API key authentication for service accounts
   - Missing multi-factor authentication
   - Limited session management security

3. **Rate Limiting Issues**
   - Implementation incomplete
   - No user-based rate limiting
   - Missing DDoS protection

4. **Caching Strategy**
   - Limited Redis usage
   - No query result caching
   - Missing session state caching

5. **Database Optimization**
   - No query optimization
   - Missing database performance monitoring
   - Limited connection pool tuning

6. **Scalability Limitations**
   - No horizontal scaling guidance
   - Missing load balancing configuration
   - Limited performance metrics

7. **Production Configuration**
   - Missing production environment templates
   - No deployment automation scripts
   - Limited monitoring integration

8. **Infrastructure as Code**
   - No Terraform/CloudFormation templates
   - Missing Kubernetes manifests
   - No CI/CD pipeline examples


#### BUG-001 · `UserManagementService` is an unimplemented stub — all user routes fail at runtime

| Field | Detail |
|---|---|
| **Severity** | Critical |
| **Component** | `app/services/user_management.py` |
| **Affected Endpoints** | `POST /v1/users/register`, `POST /v1/users/create-default`, `GET /v1/users`, `GET /v1/users/me`, `GET /v1/users/{user_id}`, `PUT /v1/users/{user_id}`, `POST /v1/users/{user_id}/reset-password`, `DELETE /v1/users/{user_id}`, `GET /v1/users/stats` |
| **Expected Behavior** | All user management endpoints execute their business logic and return the documented responses. |
| **Actual Behavior** | Every endpoint raises `AttributeError: 'UserManagementService' object has no attribute 'create_user'` (or similar). The service class contains only `__init__`; the following required methods are absent: `create_user`, `create_default_user`, `list_users`, `get_user`, `update_user`, `reset_password`, `delete_user`, `get_user_stats`. |
| **Reproduction Steps** | 1. Start the API. 2. Send `POST /v1/users/register` with valid JSON. 3. Observe 500 Internal Server Error. |
| **File:Line** | `app/services/user_management.py:1–21` |

---

#### BUG-002 · `TokenResponse` schema mismatch — login and token refresh always fail Pydantic validation

| Field | Detail |
|---|---|
| **Severity** | Critical |
| **Component** | `app/models/schemas.py`, `app/services/auth_manager.py` |
| **Affected Endpoints** | `POST /v1/auth/login`, `POST /v1/auth/refresh` |
| **Expected Behavior** | Login returns a valid `TokenResponse` with `access_token`, `refresh_token`, `token_type`, `expires_in`, and `refresh_expires_in`. |
| **Actual Behavior** | `create_tokens_for_user` returns a dict without `refresh_expires_in` → Pydantic validation raises `ValidationError` → 422 Unprocessable Entity on every login. `refresh_access_token` returns a dict without `refresh_token` and without `refresh_expires_in` → same failure on token refresh. |
| **Reproduction Steps** | 1. Send `POST /v1/auth/login` with valid credentials. 2. Observe 422 error. |
| **File:Line** | `app/services/auth_manager.py:311–319` (login dict), `app/services/auth_manager.py:383–389` (refresh dict); schema at `app/models/schemas.py:66–80` |

---

#### BUG-003 · `WebhookManager` used in Celery tasks but never imported — worker crashes on task completion

| Field | Detail |
|---|---|
| **Severity** | Critical |
| **Component** | `app/tasks/experimental_tasks.py` |
| **Affected Functionality** | All five Celery experimental tasks (Iowa Gambling, Masking Paradigm, Attentional Blink, Change Blindness, Binocular Rivalry) whenever a `webhook_url` is configured |
| **Expected Behavior** | On task completion with a webhook URL, the webhook delivery is triggered. |
| **Actual Behavior** | `NameError: name 'WebhookManager' is not defined` raised at line 71, crashing the Celery worker task. |
| **Reproduction Steps** | 1. Submit a task with a `webhook_url`. 2. Wait for task to complete. 3. Observe `NameError` in Celery worker log; task marked failed. |
| **File:Line** | `app/tasks/experimental_tasks.py:71` |

---

### HIGH Severity

---

#### BUG-004 · Health check uses SQLAlchemy 2.0–incompatible raw string SQL — readiness probe always reports unhealthy

| Field | Detail |
|---|---|
| **Severity** | High |
| **Component** | `app/services/health_check.py` |
| **Affected Endpoints** | `GET /v1/health`, `GET /v1/health/ready` |
| **Expected Behavior** | Health check returns `{"status": "healthy"}` when database is accessible. |
| **Actual Behavior** | `conn.execute("SELECT 1")` raises `ObjectNotExecutableError` in SQLAlchemy 2.0 (raw strings are not accepted; `text()` wrapper required). Database check always fails → overall status is `unhealthy` → `/v1/health/ready` returns 503. |
| **Reproduction Steps** | 1. Start API with a reachable PostgreSQL instance. 2. `GET /v1/health`. 3. Observe `"database": {"status": "unhealthy", ...}`. |
| **File:Line** | `app/services/health_check.py:47` |
| **Fix** | Replace `conn.execute("SELECT 1")` with `from sqlalchemy import text; conn.execute(text("SELECT 1"))` |

---

#### BUG-005 · Rate limiting middleware instantiated but Redis client never propagated to the active middleware instance

| Field | Detail |
|---|---|
| **Severity** | High |
| **Component** | `app/main.py` |
| **Affected Functionality** | Rate limiting on all endpoints |
| **Expected Behavior** | After Redis initializes, rate limiting middleware uses the Redis client to enforce limits. |
| **Actual Behavior** | `main.py` creates a local `rate_limiting_middleware` instance, then adds a second independent instance via `app.add_middleware(rate_limiting_middleware.__class__, ...)`. The `set_redis_client()` call updates the local variable, **not** the instance actually processing requests. Rate limiting is effectively non-functional. |
| **File:Line** | `app/main.py:239–248` |

---

#### BUG-006 · `User` ORM model missing `is_active` and `updated_at` columns — user endpoints return 500 or wrong data

| Field | Detail |
|---|---|
| **Severity** | High |
| **Component** | `app/database/models.py`, `app/models/schemas.py` |
| **Affected Endpoints** | All `GET /v1/users/*` endpoints that return `UserResponse` |
| **Expected Behavior** | `UserResponse` includes `is_active` and `updated_at` fields. |
| **Actual Behavior** | The `User` SQLAlchemy model has no `is_active` column and no `updated_at` column. Accessing `user.is_active` or `user.updated_at` in route handlers raises `AttributeError`. The Alembic migration (`001_initial_schema.py`) also omits these columns, so they are absent from the database schema. |
| **File:Line** | `app/database/models.py:58–91`; schema `app/models/schemas.py:105–122` |

---

#### BUG-007 · Route ordering conflict — `GET /v1/users/stats` unreachable

| Field | Detail |
|---|---|
| **Severity** | High |
| **Component** | `app/routes/users.py` |
| **Affected Endpoint** | `GET /v1/users/stats` |
| **Expected Behavior** | `GET /v1/users/stats` returns aggregate user statistics. |
| **Actual Behavior** | In FastAPI, routes are matched in registration order. `GET /v1/users/{user_id}` is registered at line 219, **before** `GET /v1/users/stats` at line 420. The path segment `"stats"` is captured as `user_id`, routing to `get_user` instead. The stats endpoint is effectively dead code. |
| **Reproduction Steps** | 1. `GET /v1/users/stats` with admin token. 2. Observe 404 "User not found" (stats treated as user ID). |
| **File:Line** | `app/routes/users.py:219` (conflicting route), `app/routes/users.py:420` (unreachable route) |
| **Fix** | Move the `GET /stats` route registration **before** `GET /{user_id}`. |

---

#### BUG-008 · `refresh_access_token` performs incorrect token verification using `constant_time_compare`

| Field | Detail |
|---|---|
| **Severity** | High |
| **Component** | `app/services/auth_manager.py` |
| **Affected Endpoint** | `POST /v1/auth/refresh` |
| **Expected Behavior** | Refresh tokens are securely verified. |
| **Actual Behavior** | Line 354 hashes the provided `refresh_token` via bcrypt (`token_hash = self.hash_password(refresh_token)`), then the DB lookup at line 362 queries for a row where `token_hash == token_hash` (the bcrypt hash). However, line 373 then compares the **plain token** against `db_token.token_hash` (the bcrypt hash) using `constant_time_compare` — this comparison will **always fail** because the plain token can never equal a bcrypt hash string. Any valid refresh attempt is rejected with "Invalid refresh token". |
| **File:Line** | `app/services/auth_manager.py:373` |

---

#### BUG-009 · `/v1/users/register` does not require authentication — open user registration

| Field | Detail |
|---|---|
| **Severity** | High |
| **Component** | `app/routes/users.py` |
| **Affected Endpoint** | `POST /v1/users/register` |
| **Expected Behavior** | Only authenticated users (or admins) can create accounts, or registration is gated by invite/configuration. |
| **Actual Behavior** | `POST /v1/users/register` has no authentication dependency. Any unauthenticated caller can create arbitrary user accounts, including accounts with arbitrary roles (the route accepts `roles` from request body without authorization checks). |
| **File:Line** | `app/routes/users.py:45–96` |

---

### MEDIUM Severity

---

#### BUG-010 · Health check path conflict — two `/health` endpoints with different behaviors

| Field | Detail |
|---|---|
| **Severity** | Medium |
| **Component** | `app/main.py`, `app/routes/health.py` |
| **Expected Behavior** | A single, unambiguous health endpoint hierarchy. |
| **Actual Behavior** | `main.py` registers a simple `GET /health` that always returns `{"status": "healthy"}` (no dependency checks). The health router registers `GET /v1/health` with full dependency checks. The README documents `/health` as the primary endpoint, but Docker/K8s probes would likely target `/health/ready` while the detailed check is at a different version prefix. The basic `/health` at root will always return 200 regardless of actual system health. |
| **File:Line** | `app/main.py:262–271`, `app/routes/health.py:25–55` |

---

#### BUG-011 · `Celery` status in health check always returns `"unknown"` — incomplete implementation

| Field | Detail |
|---|---|
| **Severity** | Medium |
| **Component** | `app/services/health_check.py` |
| **Affected Endpoints** | `GET /v1/health`, `GET /v1/health/ready` |
| **Expected Behavior** | Health check reports actual Celery worker availability. |
| **Actual Behavior** | Line 53–54: `dependencies["celery"] = {"status": "unknown", "message": "Not checked"}`. Celery status is hard-coded as unknown and never actually checked, making the health check incomplete. |
| **File:Line** | `app/services/health_check.py:52–54` |

---

#### BUG-012 · `TokenResponse.refresh_token` missing from refresh endpoint response

| Field | Detail |
|---|---|
| **Severity** | Medium |
| **Component** | `app/services/auth_manager.py`, `app/routes/auth.py` |
| **Affected Endpoint** | `POST /v1/auth/refresh` |
| **Expected Behavior** | Refresh endpoint returns a new access token (optionally a new refresh token). |
| **Actual Behavior** | `refresh_access_token` returns only `{"access_token", "token_type", "expires_in"}`, but `TokenResponse` declares `refresh_token` as a **required** field (no default). This produces a 422 validation error independently of BUG-002 (even if `refresh_expires_in` were added). |
| **File:Line** | `app/services/auth_manager.py:383–389`, `app/models/schemas.py:66` |

---

#### BUG-013 · `config.py` references `csrf_protection_enabled` and `request_size_limit_enabled` settings that are never defined

| Field | Detail |
|---|---|
| **Severity** | Medium |
| **Component** | `app/main.py`, `app/config.py` |
| **Expected Behavior** | Middleware configuration reads cleanly from settings. |
| **Actual Behavior** | `main.py` uses `getattr(settings, "csrf_protection_enabled", True)` and `getattr(settings, "request_size_limit_enabled", True)` — using `getattr` with a default is a workaround indicating these settings are missing from `Settings`. They are not defined in `config.py`, which means they silently fall back to hardcoded defaults and cannot be configured via environment variables. |
| **File:Line** | `app/main.py:218–225` |

---

#### BUG-014 · `constant_time_compare` in `revoke_refresh_token` also compares plain token against bcrypt hash

| Field | Detail |
|---|---|
| **Severity** | Medium |
| **Component** | `app/services/auth_manager.py` |
| **Affected Endpoint** | `POST /v1/auth/logout` |
| **Expected Behavior** | Logout revokes the provided refresh token. |
| **Actual Behavior** | Same logical error as BUG-008: `revoke_refresh_token` finds the DB token by bcrypt-hashed lookup, but does not call `constant_time_compare` during revocation (only checks if `db_token` is truthy), so revocation itself may succeed if the lookup matches, but the double-hash issue means the wrong token may be revoked or none at all. |
| **File:Line** | `app/services/auth_manager.py:406–437` |

---

#### BUG-015 · `revoke_all_user_tokens` uses `not RefreshToken.revoked` incorrectly in SQLAlchemy filter

| Field | Detail |
|---|---|
| **Severity** | Medium |
| **Component** | `app/services/auth_manager.py` |
| **Expected Behavior** | Filters for non-revoked tokens correctly. |
| **Actual Behavior** | `not RefreshToken.revoked` in Python evaluates to `False` at class definition time (SQLAlchemy column objects are truthy), producing a filter of `False`. The correct expression is `RefreshToken.revoked == False` or `~RefreshToken.revoked`. This bug appears in three places: `refresh_access_token` (line 362), `revoke_refresh_token` (line 420), and `revoke_all_user_tokens` (line 466). Queries may return all tokens (including revoked ones) instead of filtering them. |
| **File:Line** | `app/services/auth_manager.py:362`, `app/services/auth_manager.py:420`, `app/services/auth_manager.py:466` |

---

#### BUG-016 · State routes bypass authorization dependency — use manual `is_authenticated` check instead of `require_permission`

| Field | Detail |
|---|---|
| **Severity** | Medium |
| **Component** | `app/routes/state.py` |
| **Affected Endpoints** | `GET /v1/sessions/{id}/state`, `GET /v1/sessions/{id}/ignition-history`, `GET /v1/sessions/{id}/interoception`, `GET /v1/sessions/{id}/prediction-errors`, `GET /v1/sessions/{id}/somatic-markers` |
| **Expected Behavior** | State endpoints enforce RBAC using `require_permission(Permission.SESSION_READ)` consistent with other routes. |
| **Actual Behavior** | State routes use the manual `is_authenticated(request)` helper (a boolean check) rather than the `require_permission` FastAPI dependency. This means RBAC is not enforced — any authenticated user (regardless of role) can access state data. Viewer-only users can access state endpoints of sessions they do not own. |
| **File:Line** | `app/routes/state.py:76–81`, `app/routes/state.py:147–152`, etc. |

---

### LOW Severity

---

#### BUG-017 · `Session.updated_at` `onupdate` trigger uses server-side `func.now()` — not automatically called on ORM updates

| Field | Detail |
|---|---|
| **Severity** | Low |
| **Component** | `app/database/models.py` |
| **Expected Behavior** | `updated_at` is refreshed on every update. |
| **Actual Behavior** | `onupdate=func.now()` only works for SQL-level `UPDATE` statements. ORM-level attribute updates may not trigger it without `Session.refresh()` or explicit assignment. Sessions may show stale `updated_at` timestamps. |
| **File:Line** | `app/database/models.py:124–130` |

---

#### BUG-018 · Alerting middleware `alert_manager` may be uninitialized when exception handler calls `record_error`

| Field | Detail |
|---|---|
| **Severity** | Low |
| **Component** | `app/exception_handlers.py`, `app/middleware/alerting.py` |
| **Expected Behavior** | Alerting works from application startup. |
| **Actual Behavior** | `alert_manager` is imported at module level in `exception_handlers.py`. If `configure_alerting()` has not completed before the first unhandled exception (during startup), the manager may be in an uninitialised state. |
| **File:Line** | `app/exception_handlers.py:14` |

---

#### BUG-019 · `delete_pycache.py` at root is 35 KB of dead code committed to the repository

| Field | Detail |
|---|---|
| **Severity** | Low |
| **Component** | `delete_pycache.py` |
| **Expected Behavior** | Repository contains only application code; cache cleanup is in `.gitignore` or a Makefile. |
| **Actual Behavior** | A 35 KB utility script is committed at the repository root. It has no function in production and inflates repository size. |

---

#### BUG-020 · `validation_error_handler` sets `timestamp` to `None` in response body

| Field | Detail |
|---|---|
| **Severity** | Low |
| **Component** | `app/exception_handlers.py` |
| **Expected Behavior** | All error responses include a populated `timestamp`. |
| **Actual Behavior** | `http_exception_handler` and `validation_error_handler` both set `"timestamp": None`. Only `unhandled_exception_handler` provides an actual timestamp. Clients relying on `error.timestamp` receive null for the most common error types. |
| **File:Line** | `app/exception_handlers.py:96`, `app/exception_handlers.py:134` |

---

## Missing Features & Incomplete Implementations

### MISSING-001 · `GET /v1/sessions/{id}/metrics` endpoint absent

| Field | Detail |
|---|---|
| **Priority** | High |
| **Documented In** | `docs/README.md` — "State Queries" section |
| **Expected** | Returns computed simulation metrics for the session. |
| **Actual** | No route handler for this path exists in `sessions.py`, `state.py`, or any other router. |

---

### MISSING-002 · `GET /v1/tasks/{task_id}/result` endpoint absent

| Field | Detail |
|---|---|
| **Priority** | High |
| **Documented In** | `docs/README.md` — "Async Tasks" section |
| **Expected** | Returns the complete result payload for a completed task (separate from status). |
| **Actual** | The task result is embedded inside `TaskStatusResponse`, but the documented dedicated `/result` sub-resource endpoint does not exist in `tasks.py`. |

---

### MISSING-003 · `UserManagementService` methods entirely absent

| Field | Detail |
|---|---|
| **Priority** | Critical |
| **Missing Methods** | `create_user`, `create_default_user`, `list_users`, `get_user`, `update_user`, `reset_password`, `delete_user`, `get_user_stats` |
| **Impact** | All user management endpoints are non-functional (see BUG-001). |

---

### MISSING-004 · `User` database model missing `is_active` and `updated_at` columns

| Field | Detail |
|---|---|
| **Priority** | High |
| **Expected** | `UserResponse` schema fields `is_active` and `updated_at` map to database columns. |
| **Actual** | Neither column exists on the `User` ORM model or in the Alembic migration `001_initial_schema.py`. A migration must be created to add them. |

---

### MISSING-005 · Celery worker health check not implemented

| Field | Detail |
|---|---|
| **Priority** | Medium |
| **Expected** | `/v1/health` reports actual Celery worker availability. |
| **Actual** | Always returns `{"status": "unknown"}`. No actual Celery inspection is performed. |

---

### MISSING-006 · `csrf_protection_enabled` and `request_size_limit_enabled` not in `Settings` class

| Field | Detail |
|---|---|
| **Priority** | Medium |
| **Expected** | Both settings configurable via environment variables. |
| **Actual** | `config.py` does not define these fields; `main.py` uses `getattr` fallbacks. |

---

### MISSING-007 · No session listing endpoint (`GET /v1/sessions`)

| Field | Detail |
|---|---|
| **Priority** | Medium |
| **Expected** | API consumers can list their sessions. |
| **Actual** | The sessions router only supports `POST /v1/sessions` (create) and `GET /v1/sessions/{id}` (get one). There is no list endpoint; clients cannot discover existing sessions without knowing their IDs. |

---

### MISSING-008 · No task listing by session (`GET /v1/sessions/{id}/tasks`)

| Field | Detail |
|---|---|
| **Priority** | Medium |
| **Expected** | Clients can list all tasks associated with a session. |
| **Actual** | Only `POST /v1/sessions/{id}/tasks` (submit) and `GET /v1/tasks/{task_id}` (get one by ID) exist. There is no endpoint to enumerate tasks for a given session. |

---

### MISSING-009 · No pagination on session/task lists

| Field | Detail |
|---|---|
| **Priority** | Low |
| **Expected** | List endpoints support cursor-based pagination consistent with ignition history and time series endpoints. |
| **Actual** | No list endpoints currently exist for sessions or tasks, so pagination cannot be evaluated. However, when added, they should follow the cursor pattern used elsewhere. |

---

### MISSING-010 · `apgi-api` CLI entry point (`apgi-migrate`, `apgi-worker`) not implemented

| Field | Detail |
|---|---|
| **Priority** | Low |
| **Documented In** | `pyproject.toml` `[project.scripts]` |
| **Expected** | `apgi-api`, `apgi-migrate`, and `apgi-worker` CLI commands are installed and functional. |
| **Actual** | `apgi-api` maps to `app.main:cli` which does not exist. `apgi-migrate` and `apgi-worker` map to `app.cli:migrate` / `app.cli:worker` but `app/cli.py` does not exist in the repository. |

---

## Detailed Findings by Module

### `app/main.py`

- **Good:** Clean lifespan management, dependency injection order, middleware stack ordering is logically correct (size limit → GZip → metrics → logging → auth → schema validation → CSRF → deprecation → rate limiting → CORS).
- **Bug BUG-005:** Rate limiting middleware dual-instantiation — the global variable and the active middleware are different objects.
- **Bug BUG-013:** `csrf_protection_enabled` and `request_size_limit_enabled` settings referenced but not defined.
- **Issue:** The root `GET /health` always returns healthy regardless of dependency state — inconsistent with detailed health probes.

### `app/routes/auth.py`

- **Good:** Endpoint structure, HTTP verbs, and status codes are correct. Uses proper FastAPI dependencies.
- **Bug BUG-002:** `TokenResponse` requires `refresh_expires_in`; service dict does not include it.
- **Bug BUG-012:** Refresh endpoint returns dict without `refresh_token` (required field).

### `app/routes/users.py`

- **Bug BUG-001:** All routes call methods on a stub `UserManagementService`.
- **Bug BUG-007:** `GET /v1/users/stats` route registered after `GET /v1/users/{user_id}` — unreachable.
- **Bug BUG-009:** `POST /v1/users/register` requires no authentication — open registration.
- **Issue:** `roles` field in `UserCreateRequest` is accepted from callers with no role restriction — a non-admin user could create an admin account.

### `app/routes/sessions.py`

- **Good:** Session CRUD and lifecycle operations (create, get, start, pause, stop, reset, delete) are implemented. State transitions properly reflected.
- **Missing MISSING-007:** No `GET /v1/sessions` list endpoint.

### `app/routes/tasks.py`

- **Good:** Submit, status, list, and cancel are present.
- **Missing MISSING-002:** `GET /v1/tasks/{task_id}/result` endpoint absent.

### `app/routes/state.py`

- **Good:** Rich state endpoints (system state, ignition history, interoception, prediction errors, somatic markers) with pagination.
- **Bug BUG-016:** Uses `is_authenticated()` instead of `require_permission()` — RBAC not enforced.
- **Missing MISSING-001:** `GET /v1/sessions/{id}/metrics` absent.

### `app/routes/health.py`

- **Bug BUG-011:** Celery status always `"unknown"`.
- **Bug BUG-010:** Two `/health` endpoints at different path prefixes.

### `app/services/auth_manager.py`

- **Good:** bcrypt for password hashing, JWT with typed payload, token revocation stored in DB, access and refresh token separation.
- **Bug BUG-008:** `constant_time_compare(plain_token, bcrypt_hash)` always fails.
- **Bug BUG-015:** `not RefreshToken.revoked` is a Python-level negation of a SQLAlchemy column (always `False`) — filter logic broken in three places.

### `app/services/health_check.py`

- **Bug BUG-004:** SQLAlchemy 2.0 incompatible `conn.execute("SELECT 1")`.
- **Bug BUG-011:** Celery check not implemented.

### `app/services/user_management.py`

- **Bug BUG-001:** Stub class — only `__init__` defined.

### `app/database/models.py`

- **Good:** Well-indexed tables, correct foreign key constraints, JSONB for flexible configuration, comprehensive webhook delivery tracking model.
- **Bug BUG-006:** `User` model missing `is_active` and `updated_at` columns.
- **Bug BUG-017:** `updated_at` `onupdate` may not fire reliably for ORM operations.

### `app/tasks/experimental_tasks.py`

- **Bug BUG-003:** `WebhookManager` used at line 71 but not imported anywhere in the file.

---

## Security Assessment

| Area | Finding | Severity |
|---|---|---|
| Open user registration | `POST /v1/users/register` requires no auth; callers can self-assign any role | High |
| RBAC bypass on state routes | State endpoints use simple auth check instead of permission dependency | Medium |
| CSRF protection | CSRF middleware is present and configurable | ✓ OK |
| JWT algorithm | HS256 with minimum 32-char key enforced | ✓ OK |
| Password hashing | bcrypt with cost 12; 72-byte truncation documented | ✓ OK |
| Rate limiting | Infrastructure present but non-functional due to BUG-005 | High |
| Secrets in dev environment | Dev JWT secret provided with warning, fails fast in production | ✓ OK |
| CORS wildcard in dev | `http://localhost:3000` and `http://localhost:8000` as dev defaults, production validated | ✓ OK |
| Sensitive headers filtered | Authorization, Cookie, X-API-Key excluded from error metadata | ✓ OK |
| JWT secret validation | Insecure defaults rejected in production | ✓ OK |
| SQL injection | UUID format validation on session IDs present | ✓ OK |
| Request size limiting | Middleware present (10 MB default) | ✓ OK |

---

## Test Coverage Assessment

| Metric | Value |
|---|---|
| Test execution status | **Blocked** — dependencies not installed in current environment |
| Reported low-coverage modules | `app/routes/tasks.py` (14%), `app/routes/health.py` (31%), `app/routes/state.py` (32%), `app/routes/version.py` (31%), `app/services/health_check.py` (15%), `app/services/authorization.py` (53%), `app/services/data_export.py` (42%) |
| Test types present | Unit, Integration, Property-based, Load |
| Missing test dependency | `bcrypt`, `celery`, `fastapi` not installed in test environment |
| Documented target | >80% for critical paths |

---

## Actionable Recommendations

Recommendations are listed in priority order for developer handoff.

### P1 — Fix Before Any Deployment

1. **Implement `UserManagementService`** (BUG-001, MISSING-003): Add all eight missing methods (`create_user`, `create_default_user`, `list_users`, `get_user`, `update_user`, `reset_password`, `delete_user`, `get_user_stats`). Refer to `app/database/models.py` for the `User` ORM model and `app/routes/users.py` for required signatures.

2. **Fix `TokenResponse` schema** (BUG-002, BUG-012): Either:
   - Add `refresh_expires_in` to the dict returned by `create_tokens_for_user`; and make `refresh_token` optional (with default `None`) in `TokenResponse` for the refresh endpoint; or
   - Create a separate `TokenRefreshResponse` schema without `refresh_token`/`refresh_expires_in` for use by the refresh endpoint.

3. **Import `WebhookManager`** (BUG-003): Add the missing import to `experimental_tasks.py`. If no `WebhookManager` class exists, implement it or remove the dead webhook code path.

4. **Fix SQLAlchemy 2.0 health check query** (BUG-004): Change `conn.execute("SELECT 1")` to `conn.execute(text("SELECT 1"))` (import `text` from `sqlalchemy`).

5. **Fix rate limiting middleware registration** (BUG-005): Remove the redundant `app.add_middleware(rate_limiting_middleware.__class__, ...)` call. Instead, either: add the middleware class directly and update its Redis client after startup using an application event, or use a singleton pattern that the single middleware instance references.

6. **Add `is_active` and `updated_at` to `User` model** (BUG-006, MISSING-004): Add columns to `app/database/models.py` and create an Alembic migration.

7. **Fix route ordering for `/v1/users/stats`** (BUG-007): Move `@router.get("/stats", ...)` above `@router.get("/{user_id}", ...)` in `users.py`.

8. **Fix `constant_time_compare` logic** (BUG-008): Remove the erroneous `constant_time_compare` call after the bcrypt-hash-based DB lookup. The bcrypt lookup itself is the security check.

9. **Restrict user registration** (BUG-009): Add `Depends(require_permission(Permission.USER_CREATE))` to `POST /v1/users/register`, or implement an invitation/admin-only flow. Remove `roles` from the publicly accessible `UserCreateRequest` body.

10. **Fix `not RefreshToken.revoked` filter** (BUG-015): Replace all three occurrences with `RefreshToken.revoked == False` or `~RefreshToken.revoked` in SQLAlchemy filter expressions.

### P2 — Fix Before Production

11. **Implement `GET /v1/sessions/{id}/metrics` endpoint** (MISSING-001): Expose simulation metrics (e.g., ignition frequency, free energy, metabolic load) from `SessionManager.get_session().get_state()`.

12. **Implement `GET /v1/tasks/{task_id}/result` endpoint** (MISSING-002): Return the full `result_data` JSON from the `Task` DB record for completed tasks.

13. **Add RBAC to state routes** (BUG-016): Replace `is_authenticated(request)` checks with `dependencies=[Depends(require_permission(Permission.SESSION_READ))]` on all state endpoints.

14. **Implement Celery health check** (BUG-011): Use `celery_app.control.inspect().active()` or `ping()` to verify worker availability.

15. **Define missing settings** (BUG-013, MISSING-006): Add `csrf_protection_enabled: bool` and `request_size_limit_enabled: bool` to `Settings.__init__` with environment variable bindings.

16. **Add `GET /v1/sessions` list endpoint** (MISSING-007): Support pagination and filtering by state.

17. **Add `GET /v1/sessions/{id}/tasks` list endpoint** (MISSING-008).

18. **Populate `timestamp` in all error responses** (BUG-020): Update `validation_error_handler` and `http_exception_handler` to include `datetime.utcnow().isoformat() + "Z"`.

19. **Create `app/cli.py`** (MISSING-010): Implement `migrate` and `worker` CLI commands, or remove the dead `[project.scripts]` entries from `pyproject.toml`.

### P3 — Cleanup & Improvement

20. **Remove `delete_pycache.py`** (BUG-019): Add `__pycache__/` to `.gitignore` and remove the committed file.

21. **Unify health endpoint naming**: Decide whether the primary health endpoint is `/health` or `/v1/health`, and update documentation, Docker health checks, and Kubernetes probes consistently.

22. **Increase test coverage**: Target >80% for `app/routes/tasks.py`, `app/services/health_check.py`, `app/routes/health.py`, `app/routes/state.py`, and `app/services/data_export.py`.

23. **Install all dependencies in CI/test environment**: Ensure `bcrypt`, `celery`, `fastapi`, and all transitive deps are installed so the test suite can actually run.

24. **Fix `updated_at` ORM behavior** (BUG-017): Either set `updated_at = datetime.utcnow()` explicitly on model updates in service methods, or add a `@event.listens_for` hook.

25. **Review `LoginRequest.remember_me`**: The `remember_me` field is accepted but ignored in `auth_manager.py`. Either extend token expiry when `remember_me=True` or remove the field.


- Low Test Coverage

  Low Coverage Modules:
  app/routes/tasks.py: 14% (needs integration tests with authentication)
  app/routes/health.py: 31%
  app/routes/state.py: 32%
  app/routes/version.py: 31%
  app/services/health_check.py: 15%
  app/services/authorization.py: 53%
  app/services/data_export.py: 42%

- **Severity**: Medium
- **Location**: Core application modules
- **Status**: Add tests for task_registry.py (100% coverage), improved experimental_tasks.py coverage
- **Reproduction Steps**: Run `pytest --cov=app --cov-report=term-missing`
- **Expected Behavior**: >80% test coverage for critical paths
- **Actual Behavior**: Coverage improved for task modules, additional tests can be added as needed
- **Impact**: Better test coverage for core functionality
