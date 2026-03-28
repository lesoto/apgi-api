# Implementation Plan: test-coverage-100

## Overview

Achieve 100% statement and branch coverage across all `app/` modules.
Work proceeds in layers: fix infrastructure first, then fill coverage gaps module-by-module, then enforce the gate.

## Tasks

- [x] 1. Fix test infrastructure and consolidate duplicate test files
  - [x] 1.1 Consolidate `tests/unit/test_create_db.py` and `tests/unit/test_create_db_fixed.py` into a single `tests/unit/test_create_db.py` using the `mock_psycopg2` fixture; delete `test_create_db_fixed.py`
    - Merge all passing tests from both files; ensure `mock_psycopg2` fixture is used for all psycopg2-dependent paths
    - _Requirements: 11.3, 11.4, 11.6_
  - [x] 1.2 Consolidate `tests/unit/test_reset_db.py` and `tests/unit/test_reset_db_fixed.py` into a single `tests/unit/test_reset_db.py` using the `mock_psycopg2` fixture; delete `test_reset_db_fixed.py`
    - Merge all passing tests from both files; ensure `mock_psycopg2` fixture is used for all psycopg2-dependent paths
    - _Requirements: 11.3, 11.4, 11.6_
  - [x] 1.3 Fix all currently-failing tests in `tests/unit/test_cli.py` so every CLI command test passes with `CliRunner`
    - Patch `alembic.config.Config`, `alembic.command.upgrade`, `app.celery_app.celery_app`, `app.services.seeding_service.DatabaseSeedingService`, and `app.database.connection.init_db` as needed
    - _Requirements: 11.1, 11.2_
  - [x] 1.4 Verify `tests/unit/conftest.py` has `mock_psycopg2` (function-scoped, non-autouse), `mock_opentelemetry` (autouse), and `mock_celery_app` (autouse) fixtures; add any that are missing
    - _Requirements: 11.1, 11.6_
  - [x] 1.5 Verify `tests/conftest.py` sets `JWT_SECRET_KEY`, `CURSOR_SIGNING_KEY`, and `WEBHOOK_SECRET_KEY` env vars via `os.environ.setdefault`; add Hypothesis `ci`/`dev` profiles if missing
    - _Requirements: 12.7_


- [x] 2. Checkpoint — infrastructure
  - Run `pytest tests/unit/test_create_db.py tests/unit/test_reset_db.py tests/unit/test_cli.py -x` and confirm zero failures before proceeding.

- [x] 3. Fill zero-coverage modules
  - [x] 3.1 Write `tests/unit/test_main_comprehensive.py` covering `create_app(test_mode=True)`, `create_app(test_mode=False)`, and the `lifespan` startup/shutdown paths; mock `init_db`, `redis.asyncio.from_url`, `init_cache_service`, and all route `init_*` functions
    - _Requirements: 1.1, 5.2_
  - [x] 3.2 Write `tests/unit/test_exception_handlers.py` covering every registered exception handler by triggering each exception type through a `TestClient(create_app(test_mode=True))` route
    - _Requirements: 1.4, 5.3_
  - [x] 3.3 Write `tests/unit/test_logging_middleware.py` covering `RequestLoggingMiddleware.dispatch`, all `StructuredLogger` log-level methods, and `configure_structured_logging`
    - _Requirements: 1.3, 4.9_
  - [x] 3.4 Write `tests/unit/test_create_demo_user.py` covering the success path and the duplicate-user error path; mock `SessionLocal` and `AuthManager`
    - _Requirements: 1.6, 5.9_
  - [x] 3.5 Write `tests/unit/test_profiling_middleware.py` covering `ProfilingMiddleware.dispatch` with profiling enabled and disabled; mock `call_next` and `cProfile`
    - _Requirements: 1.7, 4.7_
  - [x] 3.6 Write `tests/unit/test_webhook_tasks.py` covering the Celery task success path and the delivery-failure path; use `task.apply()` with mocked `SessionLocal` and `WebhookManager`
    - _Requirements: 1.8, 8.1_
  - [x] 3.7 Ensure `tests/unit/test_create_db.py` covers the success path and the `DuplicateDatabase` error path using `mock_psycopg2`
    - _Requirements: 1.5, 5.7_
  - [x] 3.8 Ensure `tests/unit/test_reset_db.py` covers the success path and the error path when the database does not exist using `mock_psycopg2`
    - _Requirements: 1.9, 5.8_

- [x] 4. Checkpoint — zero-coverage modules
  - Run `pytest tests/unit/test_main_comprehensive.py tests/unit/test_exception_handlers.py tests/unit/test_logging_middleware.py tests/unit/test_create_demo_user.py tests/unit/test_profiling_middleware.py tests/unit/test_webhook_tasks.py tests/unit/test_create_db.py tests/unit/test_reset_db.py -x` and confirm zero failures.


- [x] 5. Fill critical-gap service tests (≥90% per module)
  - [x] 5.1 Extend `tests/unit/test_session_manager.py` to reach ≥90% statement coverage for `app/services/session_manager.py` (currently 14%, 369 statements); cover all public methods, error paths, and async flows using `MagicMock`/`AsyncMock` for the DB session
    - _Requirements: 2.1_
  - [x] 5.2 Extend `tests/unit/test_user_management.py` to reach ≥90% statement coverage for `app/services/user_management.py` (currently 10%, 253 statements); cover registration, MFA, password-reset, and error paths
    - _Requirements: 2.2_
  - [x] 5.3 Extend `tests/unit/test_task_execution.py` to reach ≥90% statement coverage for `app/services/task_executor.py` (currently 12%, 194 statements); cover task dispatch, cancellation, and failure paths
    - _Requirements: 2.3_
  - [x] 5.4 Extend `tests/unit/test_seeding_service.py` to reach ≥90% statement coverage for `app/services/seeding_service.py` (currently 12%, 163 statements); cover `seed_all`, `clear_all_data`, and error paths
    - _Requirements: 2.4_
  - [x] 5.5 Extend `tests/unit/test_webhook_manager.py` to reach ≥90% statement coverage for `app/services/webhook_manager.py` (currently 16%, 161 statements); cover delivery success, retry, and failure paths
    - _Requirements: 2.5_
  - [x] 5.6 Extend `tests/unit/test_data_export_service.py` to reach ≥90% statement coverage for `app/services/data_export.py` (currently 12%, 132 statements); cover all export formats and error paths
    - _Requirements: 2.6_
  - [x] 5.7 Extend `tests/unit/test_health_check_service.py` to reach ≥90% statement coverage for `app/services/health_check.py` (currently 11%, 103 statements); cover healthy, degraded, and unhealthy states
    - _Requirements: 2.7_
  - [x] 5.8 Extend `tests/unit/test_profiling_service.py` to reach ≥90% statement coverage for `app/services/profiling_service.py` (currently 23%, 141 statements)
    - _Requirements: 2.8_
  - [x] 5.9 Extend `tests/unit/test_rate_limiter.py` to reach ≥90% statement coverage for `app/services/rate_limiter.py` (currently 20%, 44 statements); cover allow, deny, and Redis-unavailable paths
    - _Requirements: 2.9_
  - [x] 5.10 Extend `tests/unit/test_error_recovery.py` to reach ≥90% statement coverage for `app/services/error_recovery.py` (currently 43%, 152 statements)
    - _Requirements: 2.10_
  - [x] 5.11 Extend `tests/unit/test_sharding_service.py` to reach ≥90% statement coverage for `app/services/sharding_service.py` (currently 43%, 63 statements)
    - _Requirements: 2.11_

- [x] 6. Checkpoint — critical-gap services
  - Run `pytest tests/unit/test_session_manager.py tests/unit/test_user_management.py tests/unit/test_task_execution.py tests/unit/test_seeding_service.py tests/unit/test_webhook_manager.py tests/unit/test_data_export_service.py tests/unit/test_health_check_service.py tests/unit/test_profiling_service.py tests/unit/test_rate_limiter.py tests/unit/test_error_recovery.py tests/unit/test_sharding_service.py --cov=app/services --cov-report=term-missing -x` and confirm ≥90% per module.


- [x] 7. Fill critical-gap route tests (≥90% per module)
  - [x] 7.1 Extend `tests/unit/test_payments_routes.py` to reach ≥90% coverage for `app/routes/payments.py` (currently 11%, 247 statements); include Stripe mock responses for success, card-declined, and webhook-signature-failure paths
    - _Requirements: 3.1, 3.15_
  - [x] 7.2 Extend `tests/unit/test_users_routes.py` to reach ≥90% coverage for `app/routes/users.py` (currently 18%, 278 statements); cover registration, MFA enable/disable, password-reset, and 4xx/5xx paths
    - _Requirements: 3.2, 3.15_
  - [x] 7.3 Extend `tests/unit/test_sessions_routes.py` to reach ≥90% coverage for `app/routes/sessions.py` (currently 22%, 215 statements); cover create, list, start, pause, resume, end, and error paths
    - _Requirements: 3.3, 3.15_
  - [x] 7.4 Extend `tests/unit/test_task_routes.py` to reach ≥90% coverage for `app/routes/tasks.py` (currently 18%, 180 statements); cover all task CRUD and status endpoints
    - _Requirements: 3.4, 3.15_
  - [x] 7.5 Extend `tests/unit/test_webhooks.py` to reach ≥90% coverage for `app/routes/webhooks.py` (currently 22%, 119 statements)
    - _Requirements: 3.5, 3.15_
  - [x] 7.6 Extend `tests/unit/test_metrics_routes.py` to reach ≥90% coverage for `app/routes/metrics.py` (currently 28%, 158 statements)
    - _Requirements: 3.6, 3.15_
  - [x] 7.7 Extend `tests/unit/test_export_routes.py` to reach ≥90% coverage for `app/routes/export.py` (currently 25%, 104 statements)
    - _Requirements: 3.7, 3.15_
  - [x] 7.8 Extend `tests/unit/test_templates_routes.py` to reach ≥90% coverage for `app/routes/templates.py` (currently 16%, 140 statements)
    - _Requirements: 3.8, 3.15_
  - [x] 7.9 Write `tests/unit/test_state_routes.py` to reach ≥90% coverage for `app/routes/state.py` (currently 14%, 153 statements)
    - _Requirements: 3.9, 3.15_
  - [x] 7.10 Write `tests/unit/test_auth_routes.py` to reach ≥90% coverage for `app/routes/auth.py` (currently 30%, 60 statements); cover login, logout, token-refresh, and error paths
    - _Requirements: 3.10, 3.15_
  - [x] 7.11 Extend `tests/unit/test_api_keys.py` to reach ≥90% coverage for `app/routes/api_keys.py` (currently 96%, 112 statements)
    - _Requirements: 3.11_
  - [x] 7.12 Write `tests/unit/test_health_routes.py` to reach ≥90% coverage for `app/routes/health.py` (currently 54%, 28 statements)
    - _Requirements: 3.12_
  - [x] 7.13 Write `tests/unit/test_admin_routes.py` to reach ≥90% coverage for `app/routes/admin.py` (currently 52%, 42 statements)
    - _Requirements: 3.13_
  - [x] 7.14 Write `tests/unit/test_version_routes.py` to reach ≥90% coverage for `app/routes/version.py` (currently 66%, 32 statements)
    - _Requirements: 3.14_

- [x] 8. Checkpoint — critical-gap routes
  - Run `pytest tests/unit/test_payments_routes.py tests/unit/test_users_routes.py tests/unit/test_sessions_routes.py tests/unit/test_task_routes.py tests/unit/test_webhooks.py tests/unit/test_metrics_routes.py tests/unit/test_export_routes.py tests/unit/test_templates_routes.py tests/unit/test_state_routes.py tests/unit/test_auth_routes.py tests/unit/test_api_keys.py tests/unit/test_health_routes.py tests/unit/test_admin_routes.py tests/unit/test_version_routes.py --cov=app/routes --cov-report=term-missing -x` and confirm ≥90% per module.


- [x] 9. Fill middleware tests (≥90% per module)
  - [x] 9.1 Extend `tests/unit/test_rate_limiting_middleware.py` to reach ≥90% coverage for `app/middleware/rate_limiting.py` (currently 20%, 87 statements); cover allow path, 429 path, and Redis-unavailable fallback
    - _Requirements: 4.1_
  - [x] 9.2 Extend `tests/unit/test_authentication_middleware.py` to reach ≥90% coverage for `app/middleware/authentication.py`; cover valid token, missing token on protected path, and expired token paths
    - _Requirements: 4.2_
  - [x] 9.3 Write `tests/unit/test_csrf_middleware.py` to reach ≥90% coverage for `app/middleware/csrf.py` (currently 26%, 63 statements); cover token generation, valid token, missing token, and exempt-path logic
    - _Requirements: 4.3_
  - [x] 9.4 Extend `tests/unit/test_security_validation.py` to reach ≥90% coverage for `app/middleware/security_validation.py` (currently 15%, 163 statements); cover clean input, SQL-injection pattern, and XSS pattern paths
    - _Requirements: 4.4_
  - [x] 9.5 Write `tests/unit/test_security_headers_middleware.py` to reach ≥90% coverage for `app/middleware/security_headers.py` (currently 30%, 23 statements)
    - _Requirements: 4.5_
  - [x] 9.6 Extend `tests/unit/test_deprecation.py` to reach ≥90% coverage for `app/middleware/deprecation.py` (currently 50%, 56 statements)
    - _Requirements: 4.6_
  - [x] 9.7 Extend `tests/unit/test_tracing_middleware.py` to reach ≥90% coverage for `app/middleware/tracing.py` (currently 40%, 90 statements)
    - _Requirements: 4.8_
  - [x] 9.8 Write `tests/unit/test_metrics_middleware.py` to reach ≥90% coverage for `app/middleware/metrics.py`
    - _Requirements: 4.10_
  - [x] 9.9 Write `tests/unit/test_api_versioning_middleware.py` to reach ≥90% coverage for `app/middleware/api_versioning.py`
    - _Requirements: 4.11_
  - [x] 9.10 Write `tests/unit/test_cors_config.py` to reach ≥90% coverage for `app/middleware/cors_config.py`
    - _Requirements: 4.12_
  - [x] 9.11 Extend `tests/unit/test_schema_validation.py` to reach ≥90% coverage for `app/middleware/schema_validation.py`
    - _Requirements: 4.13_

- [x] 10. Checkpoint — middleware
  - Run `pytest tests/unit/test_rate_limiting_middleware.py tests/unit/test_authentication_middleware.py tests/unit/test_csrf_middleware.py tests/unit/test_security_validation.py tests/unit/test_security_headers_middleware.py tests/unit/test_deprecation.py tests/unit/test_profiling_middleware.py tests/unit/test_tracing_middleware.py tests/unit/test_logging_middleware.py tests/unit/test_metrics_middleware.py tests/unit/test_api_versioning_middleware.py tests/unit/test_cors_config.py tests/unit/test_schema_validation.py --cov=app/middleware --cov-report=term-missing -x` and confirm ≥90% per module.


- [~] 11. Fill core module tests (≥80% per module)
  - [x] 11.1 Extend the config test (or write `tests/unit/test_config.py`) to reach ≥80% coverage for `app/config.py` (currently 78%, 183 statements); cover valid settings, JWT secret too short, missing production keys, and insecure-default detection
    - _Requirements: 5.1, 5.13, 5.14_
  - [x] 11.2 Extend `tests/unit/test_tracing.py` to reach ≥80% coverage for `app/tracing.py` (currently 26%, 87 statements); mock all OpenTelemetry modules
    - _Requirements: 5.5_
  - [x] 11.3 Extend `tests/unit/test_database.py` (or write `tests/unit/test_db_connection.py`) to reach ≥80% coverage for `app/database/connection.py` (currently 36%, 91 statements)
    - _Requirements: 5.10_
  - [x] 11.4 Extend `tests/unit/test_sharded_connection.py` to reach ≥80% coverage for `app/database/sharded_connection.py` (currently 36%, 94 statements)
    - _Requirements: 5.11_
  - [x] 11.5 Extend the schemas test (or write `tests/unit/test_schemas.py`) to reach ≥80% coverage for `app/models/schemas.py` (currently 61%, 826 statements); cover Pydantic validators, serializers, and invalid-type rejection
    - _Requirements: 5.12, 6.3_
  - [x] 11.6 Write `tests/unit/test_exceptions.py` to reach ≥80% coverage for `app/exceptions.py`
    - _Requirements: 5.4_

- [x] 12. Checkpoint — core modules
  - Run `pytest tests/unit/test_config.py tests/unit/test_tracing.py tests/unit/test_sharded_connection.py tests/unit/test_schemas.py tests/unit/test_exceptions.py --cov=app/config.py --cov=app/tracing.py --cov=app/database --cov=app/models/schemas.py --cov=app/exceptions.py --cov-report=term-missing -x` and confirm ≥80% per module.

- [x] 13. Fill Celery task tests (≥90% per module)
  - [x] 13.1 Extend `tests/unit/test_experimental_tasks.py` to reach ≥90% coverage for `app/tasks/experimental_tasks.py` (currently 18%, 197 statements); call task functions directly or via `task.apply()` with mocked dependencies
    - _Requirements: 8.2_
  - [x] 13.2 Extend `tests/unit/test_task_registry.py` to reach ≥90% coverage for `app/tasks/task_registry.py` (currently 56%, 27 statements); cover `register`, `get`, and missing-task error paths
    - _Requirements: 8.3_
  - [x] 13.3 Add a test to `tests/unit/test_webhook_tasks.py` (or `test_experimental_tasks.py`) that verifies a Celery task transitions to FAILURE state and logs the exception when it raises an unhandled exception
    - _Requirements: 8.4_

- [x] 14. Checkpoint — Celery tasks
  - Run `pytest tests/unit/test_webhook_tasks.py tests/unit/test_experimental_tasks.py tests/unit/test_task_registry.py --cov=app/tasks --cov-report=term-missing -x` and confirm ≥90% per module.


- [-] 15. Write property-based tests
  - [x] 15.1 Write a property test in `tests/property/test_schema_properties.py` verifying `Model.model_validate(instance.model_dump()) == instance` for user, session, task, and webhook schema groups
    - Property 1: Schema dict round-trip — annotate with `# Feature: test-coverage-100, Property 1`
    - _Requirements: 6.1, 6.4, 12.1_
  - [ ]* 15.2 Extend `tests/property/test_schema_properties.py` with a JSON round-trip property test: `Model.model_validate_json(instance.model_dump_json()) == instance` for each schema group
    - Property 2: Schema JSON round-trip — annotate with `# Feature: test-coverage-100, Property 2`
    - _Requirements: 6.2_
  - [ ]* 15.3 Write a property test in `tests/property/test_session_properties.py` (or extend existing) verifying session serialization round-trip for any valid session object
    - Property 3: Session serialization round-trip — annotate with `# Feature: test-coverage-100, Property 3`
    - _Requirements: 12.2_
  - [ ]* 15.4 Write a property test in `tests/property/test_security_properties.py` verifying that `SecurityValidationMiddleware._validate_request` never raises an unhandled exception for any string input
    - Property 4: SecurityValidationMiddleware total function — annotate with `# Feature: test-coverage-100, Property 4`
    - _Requirements: 12.3_
  - [ ]* 15.5 Write a property test in `tests/property/test_auth_properties.py` (or extend existing) verifying JWT encode-decode round-trip for any valid payload
    - Property 5: JWT encode-decode round-trip — annotate with `# Feature: test-coverage-100, Property 5`
    - _Requirements: 12.4_
  - [ ]* 15.6 Write a property test in `tests/property/test_rate_limiter_properties.py` verifying that calling `check_rate_limit(key, limit)` twice returns a non-increasing `remaining` count
    - Property 6: Rate limiter monotonicity — annotate with `# Feature: test-coverage-100, Property 6`
    - _Requirements: 12.5_
  - [ ]* 15.7 Write a property test in `tests/property/test_task_properties.py` (or extend existing) verifying `get_task_function(task_type)` returns the same callable stored in `TASK_FUNCTIONS[task_type]`
    - Property 7: Task registry get-function round-trip — annotate with `# Feature: test-coverage-100, Property 7`
    - _Requirements: 12.6_
  - [ ]* 15.8 Write a property test in `tests/property/test_security_headers_properties.py` verifying that every response from `create_app()` includes `X-Content-Type-Options`, `X-Frame-Options`, and `Strict-Transport-Security` headers
    - Property 8: Security headers present on all responses — annotate with `# Feature: test-coverage-100, Property 8`
    - _Requirements: 9.6_

- [x] 16. Checkpoint — property tests
  - Run `pytest tests/property/ -m property --tb=short -x` and confirm zero failures.

- [x] 17. Write middleware integration tests (test_mode=False)
  - [x] 17.1 Write `tests/integration/test_middleware_stack.py` with a `full_stack_client` fixture using `create_app(test_mode=False)` and mocked Redis, DB init, and cache service; include a test for a valid JWT token returning 200 on a protected endpoint
    - _Requirements: 7.1_
  - [x] 17.2 Add a test to `tests/integration/test_middleware_stack.py` that sends a request with no JWT token to a protected endpoint and asserts a 401 response
    - _Requirements: 7.2_
  - [x] 17.3 Add a test to `tests/integration/test_middleware_stack.py` that sends a POST/PUT/DELETE with a missing CSRF token and asserts a 403 response
    - _Requirements: 7.3_
  - [x] 17.4 Add a test to `tests/integration/test_middleware_stack.py` that sends a request body containing a SQL-injection pattern and asserts a 400 response from `SecurityValidationMiddleware`
    - _Requirements: 7.4_
  - [x] 17.5 Add a test to `tests/integration/test_middleware_stack.py` that exceeds the configured rate limit and asserts a 429 response
    - _Requirements: 7.5_
  - [x] 17.6 Add a test to `tests/integration/test_middleware_stack.py` that sends a request to a deprecated endpoint and asserts the response includes a `Deprecation` header
    - _Requirements: 7.6_

- [x] 18. Write security tests
  - [x] 18.1 Extend `tests/security/test_security_basics.py` to verify a JWT signed with a wrong secret is rejected with 401
    - _Requirements: 9.1_
  - [x] 18.2 Add a test verifying an expired JWT token is rejected with 401
    - _Requirements: 9.2_
  - [x] 18.3 Add a test verifying a request body with a SQL-injection pattern (e.g. `'; DROP TABLE users; --`) is rejected with 400 by `SecurityValidationMiddleware`
    - _Requirements: 9.3_
  - [x] 18.4 Add a test verifying a POST to a CSRF-protected endpoint without `X-CSRF-Token` is rejected with 403
    - _Requirements: 9.4_
  - [x] 18.5 Add a test verifying a client exceeding the rate limit receives 429 with a `Retry-After` header
    - _Requirements: 9.5_
  - [x] 18.6 Add a test verifying responses from all endpoints include `X-Content-Type-Options`, `X-Frame-Options`, and `Strict-Transport-Security` headers
    - _Requirements: 9.6_
  - [x] 18.7 Add a test verifying a request body with an XSS pattern (e.g. `<script>alert(1)</script>`) is rejected with 400 by `SecurityValidationMiddleware`
    - _Requirements: 9.7_
  - [x] 18.8 Add a test verifying that exceeding the configured maximum login attempts returns 429 or triggers account lock
    - _Requirements: 9.8_

- [x] 19. Checkpoint — integration and security tests
  - Run `pytest tests/integration/test_middleware_stack.py tests/security/ -x` and confirm zero failures.

- [x] 20. Update coverage gate in pyproject.toml
  - [x] 20.1 Add `--cov-fail-under=100` to the `addopts` field in `[tool.pytest.ini_options]` in `pyproject.toml`
    - _Requirements: 10.1_
  - [x] 20.2 Add `fail_under = 100` to `[tool.coverage.report]` in `pyproject.toml`
    - _Requirements: 10.2_
  - [x] 20.3 Add `branch = true` to `[tool.coverage.run]` in `pyproject.toml`
    - _Requirements: 10.5_

- [x] 21. Final verification checkpoint
  - Run `pytest tests/ --ignore=tests/load --ignore=tests/test_load.py -x` and confirm zero failures, zero errors, and 100% statement and branch coverage reported by `coverage.py`.
  - _Requirements: 10.3, 10.4, 11.1, 11.5_

