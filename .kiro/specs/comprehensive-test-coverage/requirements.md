# Requirements Document

## Introduction

This feature delivers comprehensive test coverage across the entire APGI FastAPI backend application. The codebase currently sits at approximately 1% measured coverage (8,100 statements, ~80 covered) despite having 67 test files and ~1,943 tests. The root causes are: import errors preventing test collection, tests targeting fictional/legacy APIs, test suite instability (hangs, segfaults from psycopg2/opentelemetry mock interactions), and large swaths of application code with zero tests.

The goal is to reach ≥ 80% overall coverage with all critical modules (routes, services, middleware) at ≥ 90% coverage, a stable and fast-running test suite, and a CI coverage gate that prevents regressions.

## Glossary

- **Test_Suite**: The collection of all pytest test files under `tests/` and `app/tests/`.
- **Coverage_Tool**: `pytest-cov` with `coverage.py` measuring line and branch coverage of the `app/` package.
- **Unit_Test**: A test that exercises a single module in isolation using mocks for all external dependencies (database, Redis, Stripe, SMTP).
- **Integration_Test**: A test that exercises multiple modules together using an in-memory SQLite database and mocked external services.
- **Property_Test**: A Hypothesis-based test that verifies invariants hold across many generated inputs.
- **Coverage_Gate**: A `--cov-fail-under` threshold enforced in CI that causes the build to fail if coverage drops below the configured value.
- **Fictional_Test**: A test that imports or calls APIs that do not exist in the current codebase, causing `AttributeError` or `ImportError` at collection time.
- **Module**: A single `.py` file within the `app/` package.
- **Conftest**: A `conftest.py` file providing shared pytest fixtures.
- **Mock**: A `unittest.mock.MagicMock` or `patch` replacing an external dependency during testing.
- **Hypothesis**: The property-based testing library used for generating test inputs.
- **EARS**: Easy Approach to Requirements Syntax — the pattern language used for all acceptance criteria below.

---

## Requirements

### Requirement 1: Test Suite Stability

**User Story:** As a developer, I want the test suite to run to completion without hanging or crashing, so that I can get reliable feedback on every commit.

#### Acceptance Criteria

1. WHEN the command `pytest tests/ --ignore=tests/load -x -q` is executed, THE Test_Suite SHALL complete within 300 seconds without a segmentation fault or process hang.
2. WHEN any test file is imported by pytest, THE Test_Suite SHALL collect that file without raising `ImportError` or `AttributeError`.
3. IF a test file contains references to non-existent module attributes, THEN THE Test_Suite SHALL fail that file at collection time with a clear error message rather than silently skipping it.
4. THE Test_Suite SHALL use `MagicMock` with explicit attributes or anonymous classes instead of `Mock(spec=[])` to avoid fragile spec-based mocking on Python 3.12+.
5. WHEN psycopg2 or opentelemetry modules are used in tests, THE Test_Suite SHALL patch those imports at the module level in conftest fixtures to prevent state leakage between tests.

---

### Requirement 2: Unit Test Coverage for Services

**User Story:** As a developer, I want every service module to have thorough unit tests, so that business logic bugs are caught before they reach integration or production.

#### Acceptance Criteria

1. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/services/auth_manager.py` (242 statements).
2. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/services/user_management.py`.
3. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/services/session_manager.py`.
4. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/services/cache_service.py` (124 statements).
5. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/services/webhook_manager.py`.
6. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/services/data_export.py` (132 statements).
7. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/services/seeding_service.py` (163 statements).
8. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/services/error_recovery.py` (152 statements).
9. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/services/business_metrics.py` (89 statements).
10. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/services/health_check.py`.
11. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/services/rate_limiter.py`.
12. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/services/authorization.py`.
13. WHEN `AuthManager.hash_password` is called with a valid password, THE Unit_Test SHALL verify that `AuthManager.verify_password` returns `True` for the same password (round-trip property).
14. WHEN `AuthManager.hash_password` is called with a valid password, THE Unit_Test SHALL verify that `AuthManager.verify_password` returns `False` for a different password.
15. WHEN `AuthManager.create_access_token` is called and the resulting token is decoded, THE Unit_Test SHALL verify the decoded payload contains the original `user_id`, `username`, and `roles`.

---

### Requirement 3: Unit Test Coverage for Routes

**User Story:** As a developer, I want every route module to have unit tests covering happy paths and error paths, so that API contract regressions are caught immediately.

#### Acceptance Criteria

1. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/routes/users.py` (278 statements).
2. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/routes/auth.py`.
3. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/routes/sessions.py`.
4. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/routes/tasks.py` (180 statements).
5. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/routes/payments.py` (207 statements).
6. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/routes/webhooks.py` (119 statements).
7. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/routes/export.py` (104 statements).
8. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/routes/metrics.py` (158 statements).
9. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/routes/api_keys.py` (112 statements).
10. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/routes/templates.py` (140 statements).
11. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/routes/health.py` (28 statements).
12. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/routes/admin.py`.
13. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/routes/state.py`.
14. WHEN a route handler receives an invalid request body, THE Unit_Test SHALL verify the handler returns HTTP 400 or HTTP 422.
15. WHEN a route handler requires authentication and no token is provided, THE Unit_Test SHALL verify the handler returns HTTP 401.
16. WHEN a route handler requires a specific permission and the user lacks it, THE Unit_Test SHALL verify the handler returns HTTP 403.
17. WHEN a route handler references a resource that does not exist, THE Unit_Test SHALL verify the handler returns HTTP 404.

---

### Requirement 4: Unit Test Coverage for Middleware

**User Story:** As a developer, I want every middleware module to have unit tests, so that cross-cutting concerns like authentication, rate limiting, and security headers are verified.

#### Acceptance Criteria

1. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/middleware/authentication.py`.
2. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/middleware/rate_limiting.py`.
3. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/middleware/csrf.py` (63 statements).
4. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/middleware/schema_validation.py` (167 statements).
5. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/middleware/security_validation.py` (163 statements).
6. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/middleware/security_headers.py` (23 statements).
7. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/middleware/logging.py` (65 statements).
8. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/middleware/deprecation.py` (56 statements).
9. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/middleware/profiling.py` (47 statements).
10. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/middleware/metrics.py`.
11. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/middleware/cors_config.py`.
12. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/middleware/api_versioning.py`.
13. WHEN `AuthenticationMiddleware` receives a request with a valid JWT Bearer token, THE Unit_Test SHALL verify the middleware sets `request.state.authenticated = True`.
14. WHEN `AuthenticationMiddleware` receives a request with no credentials to a non-public path, THE Unit_Test SHALL verify the middleware returns HTTP 401.
15. WHEN `RateLimitingMiddleware` receives more requests than the configured limit within the time window, THE Unit_Test SHALL verify the middleware returns HTTP 429.

---

### Requirement 5: Unit Test Coverage for Core Application Modules

**User Story:** As a developer, I want the core application modules (config, main, exceptions, database, tracing, CLI) to have unit tests, so that application startup and configuration errors are caught early.

#### Acceptance Criteria

1. THE Coverage_Tool SHALL report ≥ 80% line coverage for `app/config.py` (183 statements).
2. THE Coverage_Tool SHALL report ≥ 80% line coverage for `app/main.py` (141 statements).
3. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/exception_handlers.py` (79 statements).
4. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/exceptions.py`.
5. THE Coverage_Tool SHALL report ≥ 80% line coverage for `app/tracing.py` (87 statements).
6. THE Coverage_Tool SHALL report ≥ 80% line coverage for `app/cli.py` (90 statements).
7. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/create_db.py` (22 statements).
8. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/reset_db.py` (50 statements).
9. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/create_demo_user.py` (26 statements).
10. THE Coverage_Tool SHALL report ≥ 80% line coverage for `app/database/connection.py`.
11. THE Coverage_Tool SHALL report ≥ 80% line coverage for `app/database/sharded_connection.py` (94 statements).
12. THE Coverage_Tool SHALL report ≥ 80% line coverage for `app/models/schemas.py` (826 statements).
13. WHEN `Settings.__init__` is called with a valid `JWT_SECRET_KEY` environment variable of at least 32 characters, THE Unit_Test SHALL verify the `Settings` object is created without raising `ValueError`.
14. IF `Settings.__init__` is called with `ENVIRONMENT=production` and no `JWT_SECRET_KEY`, THEN THE Unit_Test SHALL verify `ValueError` is raised.

---

### Requirement 6: Failing Tests Fixed

**User Story:** As a developer, I want all previously failing tests to pass, so that the test suite provides a reliable green baseline.

#### Acceptance Criteria

1. WHEN `pytest tests/unit/test_create_db.py` is executed, THE Test_Suite SHALL report 0 failures and 0 errors.
2. WHEN `pytest tests/unit/test_reset_db.py` is executed, THE Test_Suite SHALL report 0 failures and 0 errors.
3. WHEN `pytest tests/unit/` is executed, THE Test_Suite SHALL report 0 collection errors due to `ImportError` or `AttributeError`.
4. WHEN `pytest tests/integration/` is executed, THE Test_Suite SHALL report 0 collection errors.
5. WHEN `pytest tests/property/` is executed, THE Test_Suite SHALL report 0 collection errors.

---

### Requirement 7: Property-Based Tests for Core Invariants

**User Story:** As a developer, I want property-based tests for critical invariants, so that edge cases and unexpected inputs are automatically explored.

#### Acceptance Criteria

1. THE Property_Test for `AuthManager.hash_password` and `AuthManager.verify_password` SHALL verify that for all non-empty string passwords generated by Hypothesis, `verify_password(password, hash_password(password))` returns `True` (round-trip property).
2. THE Property_Test for `AuthManager.create_access_token` and `AuthManager.verify_token` SHALL verify that for all valid `user_id`, `username`, and `roles` inputs, the decoded token payload matches the original inputs (round-trip property).
3. THE Property_Test for pagination in `UserManagementService.list_users` SHALL verify that for all valid `skip` and `limit` values, the returned list length is ≤ `limit` (metamorphic property).
4. THE Property_Test for `SessionLifecycleState` transitions SHALL verify that for all states, only transitions defined in `ALLOWED_TRANSITIONS` succeed without raising `ValueError` (invariant property).
5. THE Property_Test for `Settings._parse_cors_origins` SHALL verify that for all comma-separated origin strings, the parsed list contains no empty strings and each entry is stripped of whitespace (invariant property).
6. THE Property_Test for JSON serialization of schema models SHALL verify that for all valid model instances, `model.model_dump_json()` followed by `Model.model_validate_json()` produces an equivalent object (round-trip property).

---

### Requirement 8: Integration Tests for Critical Flows

**User Story:** As a developer, I want integration tests covering the most important end-to-end user flows, so that cross-module interactions are verified.

#### Acceptance Criteria

1. WHEN the user registration → email verification → login flow is executed against a test FastAPI client with an in-memory database, THE Integration_Test SHALL verify the user receives a valid JWT access token after login.
2. WHEN a valid access token is used to call a protected endpoint and then the token is refreshed, THE Integration_Test SHALL verify the new access token is valid and the old refresh token is revoked.
3. WHEN a user logs out, THE Integration_Test SHALL verify that subsequent requests using the revoked access token return HTTP 401.
4. WHEN a session is created, started, paused, and then resumed, THE Integration_Test SHALL verify the session state transitions follow the `ALLOWED_TRANSITIONS` table.
5. WHEN a Stripe webhook event `payment_intent.succeeded` is sent to `/v1/payments/webhook` with a valid signature, THE Integration_Test SHALL verify the endpoint returns HTTP 200 and the order status is updated.
6. WHEN a request exceeds the rate limit, THE Integration_Test SHALL verify subsequent requests within the window return HTTP 429 with a `Retry-After` header.

---

### Requirement 9: Security Test Coverage

**User Story:** As a developer, I want security-focused tests for authentication, authorization, and input validation, so that common attack vectors are verified to be blocked.

#### Acceptance Criteria

1. WHEN a JWT token is tampered with (signature modified), THE Unit_Test SHALL verify `AuthManager.verify_token` raises `InvalidTokenError`.
2. WHEN an expired JWT token is presented to `AuthenticationMiddleware`, THE Unit_Test SHALL verify the middleware returns HTTP 401.
3. WHEN a request contains SQL injection patterns in path parameters or query strings, THE Unit_Test SHALL verify `SecurityValidationMiddleware` returns HTTP 400.
4. WHEN a request to a state-mutating endpoint is made without a CSRF token (in non-test mode), THE Unit_Test SHALL verify `CSRFMiddleware` returns HTTP 403.
5. WHEN a user with `viewer` role attempts to access an endpoint requiring `USER_ADMIN` permission, THE Unit_Test SHALL verify the authorization check returns HTTP 403.
6. WHEN `validate_session_id` is called with a non-UUID string, THE Unit_Test SHALL verify it raises `ValueError`.
7. WHEN `Settings.__post_init__` is called with a JWT secret shorter than 32 characters in development mode, THE Unit_Test SHALL verify a `ValueError` is raised.

---

### Requirement 10: Test Consolidation and Organization

**User Story:** As a developer, I want the test suite to be organized without duplicate or redundant test files, so that maintenance burden is minimized and coverage is not double-counted.

#### Acceptance Criteria

1. THE Test_Suite SHALL contain no more than one primary test file per application module (e.g., one `test_auth_manager.py` for `app/services/auth_manager.py`).
2. WHERE multiple test files exist for the same module (e.g., `test_cache_service.py` and `test_cache_service_simple.py`), THE Test_Suite SHALL consolidate them into a single file with all non-duplicate test cases preserved.
3. THE Test_Suite SHALL organize tests into the existing directory structure: `tests/unit/` for unit tests, `tests/integration/` for integration tests, `tests/property/` for property-based tests, and `tests/security/` for security tests.
4. WHEN a test file is added or modified, THE Test_Suite SHALL follow the naming convention `test_{module_name}.py` matching the application module under test.

---

### Requirement 11: Coverage Gate in CI

**User Story:** As a developer, I want the CI pipeline to enforce a minimum coverage threshold, so that coverage regressions are automatically detected and blocked.

#### Acceptance Criteria

1. THE Coverage_Gate SHALL be configured in `pyproject.toml` with `--cov-fail-under=80` in the `addopts` field of `[tool.pytest.ini_options]`.
2. WHEN `pytest` is run and overall coverage is below 80%, THE Coverage_Gate SHALL cause pytest to exit with a non-zero exit code.
3. THE Coverage_Tool SHALL be configured to generate both `term-missing` and `html` reports on every test run.
4. THE Coverage_Tool SHALL exclude `app/alembic/`, `app/tests/`, and `*/__pycache__/` from coverage measurement, as already configured in `[tool.coverage.run]`.
5. WHEN the CI workflow in `.github/workflows/ci-cd.yml` runs, THE Coverage_Gate SHALL be enforced as part of the test step.

---

### Requirement 12: Task and Webhook Module Coverage

**User Story:** As a developer, I want the Celery task modules and webhook manager to have unit tests, so that background job logic is verified.

#### Acceptance Criteria

1. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/tasks/webhook_tasks.py` (27 statements).
2. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/tasks/task_registry.py`.
3. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/tasks/experimental_tasks.py`.
4. THE Coverage_Tool SHALL report ≥ 90% line coverage for `app/services/webhook_manager.py`.
5. WHEN a webhook task is executed with a mocked HTTP client, THE Unit_Test SHALL verify the task sends a POST request to the configured webhook URL with the correct payload.
6. IF a webhook delivery fails after the configured retry limit, THEN THE Unit_Test SHALL verify the task marks the webhook as permanently failed.
