# Implementation Plan: Comprehensive Test Coverage

## Overview

Fix suite stability first (conftest hierarchy + sys.modules patches), then consolidate duplicate
files, then write/rewrite unit tests for services/routes/middleware/core, then property-based and
security tests, and finally enforce the coverage gate in pyproject.toml and CI.

## Tasks

- [x] 1. Stabilize the root conftest and environment setup
  - [x] 1.1 Rewrite `tests/conftest.py` to set all required env vars (`JWT_SECRET_KEY`,
    `CURSOR_SIGNING_KEY`, `WEBHOOK_SECRET_KEY`, `ENVIRONMENT=development`,
    `DATABASE_URL=sqlite:///:memory:`, `REDIS_URL`) via `os.environ.setdefault` before any app
    import, register Hypothesis profiles (`ci`/`dev`/`thorough`), and load the correct profile
    based on the `CI` env var
    - _Requirements: 1.1, 1.2, 5.13_
  - [ ]* 1.2 Write a smoke test that imports `app.config` and verifies `Settings()` constructs
    without raising `ValueError` when the env vars from 1.1 are present
    - _Requirements: 5.13, 6.3_

- [x] 2. Stabilize the unit test conftest (psycopg2 / opentelemetry / Celery patches)
  - [x] 2.1 Rewrite `tests/unit/conftest.py` to add `autouse=True` function-scoped fixtures that
    replace `psycopg2`, `psycopg2.extensions`, `psycopg2.errors`, all `opentelemetry.*`
    sub-modules, and `app.celery_app` in `sys.modules` with explicit-attribute `MagicMock`
    instances, and clean them up in the fixture teardown
    - _Requirements: 1.4, 1.5_
  - [ ]* 2.2 Write a property test verifying that after the fixture teardown the patched keys are
    absent from `sys.modules` (no state leakage between tests)
    - **Property 12: Session State Transition Invariant (used as structural analogy for fixture
      isolation)**
    - **Validates: Requirements 1.5**

- [x] 3. Consolidate duplicate and fictional test files
  - [x] 3.1 Merge `tests/unit/test_cache_service_simple.py` into `tests/unit/test_cache_service.py`
    (preserve unique cases, delete the simple file)
    - _Requirements: 10.1, 10.2_
  - [x] 3.2 Merge `tests/unit/test_business_metrics_simple.py` into
    `tests/unit/test_business_metrics.py`, then delete the simple file
    - _Requirements: 10.1, 10.2_
  - [x] 3.3 Merge `tests/unit/test_cli_simple.py` and `tests/unit/test_cli_comprehensive.py` into
    `tests/unit/test_cli.py`, then delete both source files
    - _Requirements: 10.1, 10.2_
  - [x] 3.4 Merge `tests/unit/test_profiling_service_simple.py` into
    `tests/unit/test_profiling_service.py`, then delete the simple file
    - _Requirements: 10.1, 10.2_
  - [x] 3.5 Merge `tests/unit/test_security_validation_real.py` and
    `tests/unit/test_security_validation_comprehensive.py` into
    `tests/unit/test_security_validation.py`, then delete both source files
    - _Requirements: 10.1, 10.2_
  - [x] 3.6 Merge `tests/unit/test_sharded_connection_comprehensive.py` into
    `tests/unit/test_sharded_connection.py`, then delete the comprehensive file
    - _Requirements: 10.1, 10.2_
  - [x] 3.7 Merge `tests/unit/test_schema_validation_middleware.py` into
    `tests/unit/test_schema_validation.py`, then delete the middleware file
    - _Requirements: 10.1, 10.2_
  - [x] 3.8 Merge `tests/unit/test_tasks_routes.py` into `tests/unit/test_task_routes.py`, then
    delete `test_tasks_routes.py`
    - _Requirements: 10.1, 10.2_

- [x] 4. Checkpoint — verify collection is clean after consolidation
  - Run `pytest tests/unit/ --collect-only -q` and confirm 0 collection errors. Ask the user if
    any errors remain before proceeding.


- [x] 5. Rewrite / complete unit tests for auth and user services
  - [x] 5.1 Rewrite `tests/unit/test_auth_manager.py` to cover `AuthManager.hash_password`,
    `verify_password`, `create_access_token`, `verify_token`, `refresh_token`, and
    `revoke_token` using a `MagicMock` DB session; target ≥ 90% line coverage for
    `app/services/auth_manager.py`
    - _Requirements: 2.1, 2.13, 2.14, 2.15_
  - [ ]* 5.2 Write property test for password hash round-trip (Property 1)
    - **Property 1: Password Hash Round-Trip**
    - **Validates: Requirements 2.13, 7.1**
  - [ ]* 5.3 Write property test for different passwords not cross-verifying (Property 2)
    - **Property 2: Different Passwords Do Not Cross-Verify**
    - **Validates: Requirements 2.14**
  - [ ]* 5.4 Write property test for token creation round-trip (Property 3)
    - **Property 3: Token Creation Round-Trip**
    - **Validates: Requirements 2.15, 7.2**
  - [x] 5.5 Rewrite `tests/unit/test_user_management.py` to cover `UserManagementService`
    CRUD methods and `list_users` pagination using a `MagicMock` DB session; target ≥ 90%
    coverage for `app/services/user_management.py`
    - _Requirements: 2.2_
  - [ ]* 5.6 Write property test for pagination length invariant (Property 11)
    - **Property 11: Pagination Length Invariant**
    - **Validates: Requirements 7.3**

- [x] 6. Rewrite / complete unit tests for session, cache, and rate-limiter services
  - [x] 6.1 Rewrite `tests/unit/test_session_manager.py` to cover `SessionManager` create,
    start, pause, resume, and end flows using a `MagicMock` DB session; target ≥ 90% coverage
    for `app/services/session_manager.py`
    - _Requirements: 2.3_
  - [x] 6.2 Rewrite `tests/unit/test_session_lifecycle.py` to cover all
    `SessionLifecycleState` transitions, verifying allowed transitions succeed and disallowed
    ones raise `ValueError`
    - _Requirements: 2.3, 7.4_
  - [ ]* 6.3 Write property test for session state transition invariant (Property 12)
    - **Property 12: Session State Transition Invariant**
    - **Validates: Requirements 7.4**
  - [x] 6.4 Rewrite `tests/unit/test_cache_service.py` (post-consolidation) to cover
    `CacheService` get/set/delete/invalidate using an `AsyncMock` redis client; target ≥ 90%
    coverage for `app/services/cache_service.py`
    - _Requirements: 2.4_
  - [x] 6.5 Rewrite `tests/unit/test_rate_limiter.py` to cover `RateLimiter` allow/deny logic
    using an `AsyncMock` redis client; target ≥ 90% coverage for
    `app/services/rate_limiter.py`
    - _Requirements: 2.11_

- [~] 7. Rewrite / complete unit tests for remaining services
  - [x] 7.1 Rewrite `tests/unit/test_webhook_manager.py` to cover `WebhookManager` delivery,
    retry, and permanent-failure logic using `unittest.mock.patch("httpx.AsyncClient.post")`;
    target ≥ 90% coverage for `app/services/webhook_manager.py`
    - _Requirements: 2.5, 12.4, 12.5, 12.6_
  - [x] 7.2 Rewrite `tests/unit/test_data_export_service.py` to cover `DataExportService`
    export generation and streaming using a `MagicMock` DB session; target ≥ 90% coverage for
    `app/services/data_export.py`
    - _Requirements: 2.6_
  - [~] 7.3 Rewrite `tests/unit/test_seeding_service.py` to cover `SeedingService` seed and
    rollback paths using a `MagicMock` DB session; target ≥ 90% coverage for
    `app/services/seeding_service.py`
    - _Requirements: 2.7_
  - [~] 7.4 Rewrite `tests/unit/test_error_recovery.py` to cover `ErrorRecoveryService`
    detection and recovery flows; target ≥ 90% coverage for `app/services/error_recovery.py`
    - _Requirements: 2.8_
  - [~] 7.5 Rewrite `tests/unit/test_business_metrics.py` (post-consolidation) to cover
    `BusinessMetricsService` aggregation and reporting; target ≥ 90% coverage for
    `app/services/business_metrics.py`
    - _Requirements: 2.9_
  - [~] 7.6 Rewrite `tests/unit/test_health_check_service.py` to cover `HealthCheckService`
    healthy/degraded/unhealthy paths; target ≥ 90% coverage for
    `app/services/health_check.py`
    - _Requirements: 2.10_
  - [~] 7.7 Rewrite `tests/unit/test_authorization.py` to cover `AuthorizationService`
    permission checks for all roles; target ≥ 90% coverage for
    `app/services/authorization.py`
    - _Requirements: 2.12_

- [~] 8. Checkpoint — run unit service tests and verify ≥ 90% coverage per module
  - Run `pytest tests/unit/ -x -q --cov=app/services --cov-report=term-missing` and confirm
    each service module hits ≥ 90%. Ask the user if any module falls short.


- [~] 9. Rewrite / complete unit tests for routes
  - [~] 9.1 Rewrite `tests/unit/test_users_routes.py` to cover `app/routes/users.py` happy
    path, 401, 403, 404, and 422 cases using `TestClient` with `create_app(test_mode=True)` and
    dependency overrides for `get_db` and `get_current_user`; target ≥ 90% coverage
    - _Requirements: 3.1, 3.14, 3.15, 3.16, 3.17_
  - [ ]* 9.2 Write property test for invalid request body returning 4xx (Property 4)
    - **Property 4: Invalid Request Body Returns 4xx**
    - **Validates: Requirements 3.14**
  - [ ]* 9.3 Write property test for unauthenticated request returning 401 (Property 5)
    - **Property 5: Unauthenticated Request to Protected Route Returns 401**
    - **Validates: Requirements 3.15, 4.14**
  - [ ]* 9.4 Write property test for unauthorized request returning 403 (Property 6)
    - **Property 6: Unauthorized Request Returns 403**
    - **Validates: Requirements 3.16, 9.5**
  - [ ]* 9.5 Write property test for missing resource returning 404 (Property 7)
    - **Property 7: Missing Resource Returns 404**
    - **Validates: Requirements 3.17**
  - [~] 9.6 Rewrite `tests/unit/test_auth_manager.py` auth-route coverage: add route-level
    tests in a new `tests/unit/routes/test_auth.py` (or extend existing) covering
    `app/routes/auth.py` login, logout, refresh, and register endpoints; target ≥ 90% coverage
    - _Requirements: 3.2_
  - [~] 9.7 Rewrite `tests/unit/test_sessions_routes.py` to cover `app/routes/sessions.py`
    create, list, get, start, pause, resume, and end endpoints; target ≥ 90% coverage
    - _Requirements: 3.3_
  - [~] 9.8 Rewrite `tests/unit/test_task_routes.py` (post-consolidation) to cover
    `app/routes/tasks.py`; target ≥ 90% coverage
    - _Requirements: 3.4_
  - [~] 9.9 Rewrite `tests/unit/test_payments_routes.py` to cover `app/routes/payments.py`
    including Stripe mock; target ≥ 90% coverage
    - _Requirements: 3.5_
  - [~] 9.10 Rewrite `tests/unit/test_webhooks.py` to cover `app/routes/webhooks.py`; target
    ≥ 90% coverage
    - _Requirements: 3.6_
  - [~] 9.11 Rewrite `tests/unit/test_export_routes.py` to cover `app/routes/export.py`;
    target ≥ 90% coverage
    - _Requirements: 3.7_
  - [~] 9.12 Rewrite `tests/unit/test_metrics_routes.py` to cover `app/routes/metrics.py`;
    target ≥ 90% coverage
    - _Requirements: 3.8_
  - [~] 9.13 Rewrite `tests/unit/test_api_keys.py` to cover `app/routes/api_keys.py`; target
    ≥ 90% coverage
    - _Requirements: 3.9_
  - [~] 9.14 Rewrite `tests/unit/test_templates_routes.py` to cover
    `app/routes/templates.py`; target ≥ 90% coverage
    - _Requirements: 3.10_
  - [~] 9.15 Create `tests/unit/routes/test_health.py` (or extend existing health test) to
    cover `app/routes/health.py`; target ≥ 90% coverage
    - _Requirements: 3.11_
  - [~] 9.16 Create `tests/unit/routes/test_admin.py` to cover `app/routes/admin.py`; target
    ≥ 90% coverage
    - _Requirements: 3.12_
  - [~] 9.17 Create `tests/unit/routes/test_state.py` to cover `app/routes/state.py`; target
    ≥ 90% coverage
    - _Requirements: 3.13_

- [~] 10. Checkpoint — run route unit tests and verify ≥ 90% coverage per module
  - Run `pytest tests/unit/ -x -q --cov=app/routes --cov-report=term-missing` and confirm each
    route module hits ≥ 90%. Ask the user if any module falls short.


- [~] 11. Rewrite / complete unit tests for middleware
  - [~] 11.1 Rewrite `tests/unit/test_authentication_middleware.py` to cover
    `AuthenticationMiddleware.dispatch` with valid token (sets `request.state.authenticated`),
    missing token on protected path (401), and expired token (401) by calling `dispatch()`
    directly with a mock `Request`; target ≥ 90% coverage for
    `app/middleware/authentication.py`
    - _Requirements: 4.1, 4.13, 4.14_
  - [ ]* 11.2 Write property test for valid token setting authenticated state (Property 8)
    - **Property 8: Valid Token Sets Authenticated State**
    - **Validates: Requirements 4.13**
  - [~] 11.3 Rewrite `tests/unit/test_rate_limiting_middleware.py` to cover
    `RateLimitingMiddleware` allow and 429 paths; target ≥ 90% coverage for
    `app/middleware/rate_limiting.py`
    - _Requirements: 4.2, 4.15_
  - [ ]* 11.4 Write property test for rate limit exceeded returning 429 (Property 9)
    - **Property 9: Rate Limit Exceeded Returns 429**
    - **Validates: Requirements 4.15**
  - [~] 11.5 Rewrite `tests/unit/test_schema_validation.py` (post-consolidation) to cover
    `SchemaValidationMiddleware` valid and invalid body paths; target ≥ 90% coverage for
    `app/middleware/schema_validation.py`
    - _Requirements: 4.4_
  - [~] 11.6 Rewrite `tests/unit/test_security_validation.py` (post-consolidation) to cover
    `SecurityValidationMiddleware` clean and injection-pattern paths; target ≥ 90% coverage
    for `app/middleware/security_validation.py`
    - _Requirements: 4.5, 9.3_
  - [ ]* 11.7 Write property test for SQL injection patterns returning 400 (Property 16)
    - **Property 16: SQL Injection Patterns Return 400**
    - **Validates: Requirements 9.3**
  - [~] 11.8 Create `tests/unit/middleware/test_csrf.py` to cover `CSRFMiddleware` token
    validation and exempt-path logic; target ≥ 90% coverage for `app/middleware/csrf.py`
    - _Requirements: 4.3, 9.4_
  - [ ]* 11.9 Write property test for missing CSRF token returning 403 (Property 17)
    - **Property 17: Missing CSRF Token Returns 403**
    - **Validates: Requirements 9.4**
  - [~] 11.10 Create or rewrite `tests/unit/middleware/test_security_headers.py` to cover
    `SecurityHeadersMiddleware`; target ≥ 90% coverage for
    `app/middleware/security_headers.py`
    - _Requirements: 4.6_
  - [~] 11.11 Rewrite `tests/unit/test_deprecation.py` to cover `DeprecationMiddleware`;
    target ≥ 90% coverage for `app/middleware/deprecation.py`
    - _Requirements: 4.8_
  - [~] 11.12 Rewrite `tests/unit/test_profiling_middleware.py` to cover
    `ProfilingMiddleware`; target ≥ 90% coverage for `app/middleware/profiling.py`
    - _Requirements: 4.9_
  - [~] 11.13 Create `tests/unit/middleware/test_metrics_middleware.py` to cover
    `MetricsMiddleware`; target ≥ 90% coverage for `app/middleware/metrics.py`
    - _Requirements: 4.10_
  - [~] 11.14 Create `tests/unit/middleware/test_cors_config.py` to cover `CORSConfig`
    middleware; target ≥ 90% coverage for `app/middleware/cors_config.py`
    - _Requirements: 4.11_
  - [~] 11.15 Create `tests/unit/middleware/test_api_versioning.py` to cover
    `APIVersioningMiddleware`; target ≥ 90% coverage for `app/middleware/api_versioning.py`
    - _Requirements: 4.12_
  - [~] 11.16 Rewrite `tests/unit/test_tracing_middleware.py` to cover logging and tracing
    middleware; target ≥ 90% coverage for `app/middleware/logging.py`
    - _Requirements: 4.7_

- [~] 12. Checkpoint — run middleware unit tests and verify ≥ 90% coverage per module
  - Run `pytest tests/unit/ -x -q --cov=app/middleware --cov-report=term-missing` and confirm
    each middleware module hits ≥ 90%. Ask the user if any module falls short.


- [~] 13. Rewrite / complete unit tests for core application modules
  - [~] 13.1 Rewrite `tests/unit/test_create_db.py` to fix all failures; cover
    `app/create_db.py` using the `mock_psycopg2` fixture from `tests/unit/conftest.py`; target
    ≥ 90% coverage
    - _Requirements: 5.7, 6.1_
  - [~] 13.2 Rewrite `tests/unit/test_reset_db.py` to fix all failures; cover
    `app/reset_db.py` using the `mock_psycopg2` fixture; target ≥ 90% coverage
    - _Requirements: 5.8, 6.2_
  - [~] 13.3 Rewrite `tests/unit/test_create_demo_user.py` to cover `app/create_demo_user.py`
    with a `MagicMock` DB session; target ≥ 90% coverage
    - _Requirements: 5.9_
  - [~] 13.4 Rewrite `tests/unit/test_exception_handlers.py` to cover all handlers in
    `app/exception_handlers.py`; target ≥ 90% coverage
    - _Requirements: 5.3_
  - [~] 13.5 Create `tests/unit/core/test_exceptions.py` to cover all custom exception classes
    in `app/exceptions.py`; target ≥ 90% coverage
    - _Requirements: 5.4_
  - [~] 13.6 Rewrite `tests/unit/test_database.py` to cover `app/database/connection.py`
    using a `MagicMock` engine; target ≥ 80% coverage
    - _Requirements: 5.10_
  - [~] 13.7 Rewrite `tests/unit/test_sharded_connection.py` (post-consolidation) to cover
    `app/database/sharded_connection.py`; target ≥ 80% coverage
    - _Requirements: 5.11_
  - [~] 13.8 Create `tests/unit/core/test_schemas.py` to cover the most-used Pydantic schema
    models in `app/models/schemas.py` (validators, serializers); target ≥ 80% coverage
    - _Requirements: 5.12_
  - [ ]* 13.9 Write property test for schema model JSON round-trip (Property 14)
    - **Property 14: Schema Model JSON Round-Trip**
    - **Validates: Requirements 7.6**
  - [~] 13.10 Rewrite `tests/unit/test_cli.py` (post-consolidation) to cover `app/cli.py`
    commands using `click.testing.CliRunner`; target ≥ 80% coverage
    - _Requirements: 5.6_
  - [~] 13.11 Rewrite `tests/unit/test_tracing.py` to cover `app/tracing.py` with mocked
    opentelemetry modules; target ≥ 80% coverage
    - _Requirements: 5.5_
  - [~] 13.12 Rewrite `tests/unit/test_main_comprehensive.py` (or create
    `tests/unit/core/test_main.py`) to cover `app/main.py` app factory and lifespan; target
    ≥ 80% coverage
    - _Requirements: 5.2_
  - [~] 13.13 Create `tests/unit/core/test_config.py` to cover `app/config.py` `Settings`
    validation, including valid JWT secret (no error) and missing JWT secret in production
    (ValueError); target ≥ 80% coverage
    - _Requirements: 5.1, 5.13, 5.14_
  - [ ]* 13.14 Write property test for valid settings initialization (Property 10)
    - **Property 10: Valid Settings Initialization**
    - **Validates: Requirements 5.13**
  - [ ]* 13.15 Write property test for CORS origins parsing invariant (Property 13)
    - **Property 13: CORS Origins Parsing Invariant**
    - **Validates: Requirements 7.5**

- [~] 14. Rewrite / complete unit tests for Celery task modules
  - [~] 14.1 Rewrite `tests/unit/test_webhook_tasks.py` to cover `app/tasks/webhook_tasks.py`
    using `unittest.mock.patch("httpx.AsyncClient.post")` and
    `unittest.mock.patch.object(task, "delay")`; verify POST to webhook URL and permanent
    failure after retry limit; target ≥ 90% coverage
    - _Requirements: 12.1, 12.5, 12.6_
  - [~] 14.2 Rewrite `tests/unit/test_task_registry.py` to cover `app/tasks/task_registry.py`
    with a mocked Celery app; target ≥ 90% coverage
    - _Requirements: 12.2_
  - [~] 14.3 Rewrite `tests/unit/test_experimental_tasks.py` to cover
    `app/tasks/experimental_tasks.py` with mocked dependencies; target ≥ 90% coverage
    - _Requirements: 12.3_

- [~] 15. Checkpoint — run all unit tests and verify 0 collection errors
  - Run `pytest tests/unit/ --collect-only -q` and then `pytest tests/unit/ -x -q`. Confirm 0
    collection errors and 0 failures. Ask the user if any issues remain.


- [~] 16. Set up integration test conftest and write critical flow tests
  - [~] 16.1 Rewrite `tests/integration/conftest.py` to provide `app_client` (TestClient with
    `create_app(test_mode=True)`), `db_session` (SQLite in-memory with FK pragma), and
    `mock_redis`/`mock_stripe`/`mock_smtp` fixtures; wire `get_db` dependency override
    - _Requirements: 8.1_
  - [~] 16.2 Write `tests/integration/test_auth_flow.py` covering the register → email
    verification → login flow; verify a valid JWT is returned after login
    - _Requirements: 8.1_
  - [~] 16.3 Write or rewrite `tests/integration/test_user_integration.py` to cover token
    refresh (new token valid, old refresh token revoked) and logout (subsequent request returns
    401)
    - _Requirements: 8.2, 8.3_
  - [~] 16.4 Write or rewrite `tests/integration/test_sessions_integration.py` to cover
    session create → start → pause → resume state transitions
    - _Requirements: 8.4_
  - [~] 16.5 Write or rewrite `tests/integration/test_payments_integration.py` to cover
    Stripe webhook `payment_intent.succeeded` returning 200 and updating order status
    - _Requirements: 8.5_
  - [~] 16.6 Write `tests/integration/test_rate_limiting_integration.py` to cover rate limit
    exceeded returning 429 with `Retry-After` header
    - _Requirements: 8.6_

- [ ] 17. Set up property test conftest and consolidate property tests
  - [ ] 17.1 Rewrite `tests/property/conftest.py` to load the Hypothesis `ci` profile and
    provide an `auth_manager` fixture with a `MagicMock` DB session
    - _Requirements: 7.1_
  - [ ] 17.2 Consolidate all auth-related property tests (Properties 1, 2, 3, 15) into
    `tests/property/test_auth_properties.py`; tag each with the property number comment
    - _Requirements: 7.1, 7.2, 9.1_
  - [ ]* 17.3 Write property test for tampered token raising InvalidTokenError (Property 15)
    - **Property 15: Tampered Token Raises InvalidTokenError**
    - **Validates: Requirements 9.1**
  - [ ] 17.4 Consolidate session and pagination property tests (Properties 11, 12) into
    `tests/property/test_session_properties.py`
    - _Requirements: 7.3, 7.4_
  - [ ] 17.5 Consolidate config and schema property tests (Properties 10, 13, 14) into
    `tests/property/test_config_properties.py`
    - _Requirements: 7.5, 7.6, 5.13_
  - [ ] 17.6 Consolidate route/middleware property tests (Properties 4, 5, 6, 7, 8, 9, 16,
    17, 18) into `tests/property/test_api_properties.py`
    - _Requirements: 3.14, 3.15, 3.16, 3.17, 4.13, 4.15, 9.3, 9.4_
  - [ ]* 17.7 Write property test for invalid session ID raising ValueError (Property 18)
    - **Property 18: Invalid Session ID Raises ValueError**
    - **Validates: Requirements 9.6**

- [ ] 18. Set up security test conftest and write security tests
  - [ ] 18.1 Rewrite `tests/security/conftest.py` to create a `TestClient` with
    `test_mode=False` (all middleware active) and DB dependency overridden to SQLite
    in-memory; provide `valid_token` and `expired_token` fixtures
    - _Requirements: 9.1, 9.2_
  - [ ] 18.2 Write `tests/security/test_auth_security.py` covering tampered JWT → 401,
    expired JWT → 401, and viewer role on admin endpoint → 403
    - _Requirements: 9.1, 9.2, 9.5_
  - [ ] 18.3 Write `tests/security/test_input_security.py` covering SQL injection in query
    params → 400 and non-UUID session ID → ValueError
    - _Requirements: 9.3, 9.6_
  - [ ] 18.4 Write `tests/security/test_csrf_security.py` covering POST without CSRF token
    → 403 on non-exempt endpoints
    - _Requirements: 9.4_
  - [ ] 18.5 Write `tests/security/test_settings_security.py` covering JWT secret shorter
    than 32 chars in development mode → ValueError
    - _Requirements: 9.7_

- [ ] 19. Checkpoint — run integration, property, and security tests
  - Run `pytest tests/integration/ tests/property/ tests/security/ -x -q` and confirm 0
    collection errors and 0 failures. Ask the user if any issues remain.


- [ ] 20. Configure coverage gate in pyproject.toml and CI
  - [ ] 20.1 Update `[tool.pytest.ini_options]` in `pyproject.toml` to add
    `--cov=app --cov-report=term-missing --cov-report=html --cov-fail-under=80
    --ignore=tests/load --ignore=tests/test_load.py` to the `addopts` field
    - _Requirements: 11.1, 11.2, 11.3_
  - [ ] 20.2 Update `[tool.coverage.run]` in `pyproject.toml` to set `branch = true`,
    `source = ["app"]`, and `omit = ["*/tests/*", "*/alembic/*", "*/__pycache__/*",
    "app/tests/*"]`
    - _Requirements: 11.4_
  - [ ] 20.3 Update `[tool.coverage.report]` in `pyproject.toml` to set `fail_under = 80`
    and `show_missing = true`
    - _Requirements: 11.2_
  - [ ] 20.4 Update `.github/workflows/ci-cd.yml` test step to pass `CI=true`,
    `JWT_SECRET_KEY`, `CURSOR_SIGNING_KEY`, `WEBHOOK_SECRET_KEY`, `ENVIRONMENT=development`,
    and `DATABASE_URL=sqlite:///:memory:` as env vars, and run
    `pytest tests/ --ignore=tests/load -x -q`
    - _Requirements: 11.5_

- [ ] 21. Final checkpoint — full suite with coverage gate
  - Run `pytest tests/ --ignore=tests/load -x -q` and confirm overall coverage ≥ 80%, all
    critical modules ≥ 90%, 0 collection errors, and pytest exits 0. Ask the user if any
    module falls short before closing out.
