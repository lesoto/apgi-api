 interactions are never integration-tested.

## Glossary

- **Test_Suite**: The collection of all pytest test files under `tests/`.
- **Coverage_Tool**: `pytest-cov` / `coverage.py` as configured in `pyproject.toml`.
- **Coverage_Gate**: The `--cov-fail-under` threshold enforced in CI.
- **Unit_Test**: A test that exercises a single module in isolation using mocks/stubs.
- **Integration_Test**: A test that exercises multiple real components together (e.g. route + service + DB).
- **Property_Test**: A Hypothesis-based test that verifies a correctness property over generated inputs.
- **TestClient**: `starlette.testclient.TestClient` wrapping `create_app(test_mode=True)`.
- **Middleware_Integration_Test**: A test that exercises the full middleware stack with `test_mode=False`.
- **Module**: A single `.py` file under `app/`.
- **Statement**: A single executable line as counted by `coverage.py`.
- **Branch**: A conditional execution path (True/False arm of an `if`, `try`/`except` arm, etc.).
- **Fixture**: A pytest fixture providing shared setup/teardown.
- **Mock**: A `unittest.mock.MagicMock` or `AsyncMock` substituting a real dependency.
- **CLI_Runner**: `click.testing.CliRunner` used to invoke CLI commands in tests.
- **EARS**: Easy Approach to Requirements Syntax — the pattern used for all acceptance criteria below.

---

## Requirements

### Requirement 1: Zero-Coverage Module Tests

**User Story:** As a developer, I want every currently-uncovered module to have a dedicated test file, so that no application code is invisible to the coverage report.

#### Acceptance Criteria

1. THE Test_Suite SHALL contain a test file that imports and exercises `app/main.py`, covering the `create_app` factory, the `lifespan` context manager startup and shutdown paths, and the root `/` endpoint.
2. THE Test_Suite SHALL contain a test file that imports and exercises `app/cli.py`, covering every Click command (`migrate`, `worker`, `seed`, `clear_seed_data`) using CLI_Runner.
3. THE Test_Suite SHALL contain a test file that imports and exercises `app/middleware/logging.py`, covering `RequestLoggingMiddleware.dispatch`, `StructuredLogger` log-level methods, and `configure_structured_logging`.
4. THE Test_Suite SHALL contain a test file that imports and exercises `app/exception_handlers.py`, covering every registered exception handler with a matching exception type.
5. THE Test_Suite SHALL contain a test file that imports and exercises `app/create_db.py`, covering the success path and the `DuplicateDatabase` error path.
6. THE Test_Suite SHALL contain a test file that imports and exercises `app/create_demo_user.py`, covering the success path and the duplicate-user error path.
7. THE Test_Suite SHALL contain a test file that imports and exercises `app/middleware/profiling.py`, covering `ProfilingMiddleware.dispatch` with profiling enabled and disabled.
8. THE Test_Suite SHALL contain a test file that imports and exercises `app/tasks/webhook_tasks.py`, covering the Celery task success path and the delivery-failure path.
9. THE Test_Suite SHALL contain a test file that imports and exercises `app/reset_db.py`, covering the success path and the error path when the database does not exist.

---

### Requirement 2: Critical-Gap Service Tests (≥90% per module)

**User Story:** As a developer, I want every service module with less than 30% coverage to reach ≥90% coverage, so that core business logic is reliably verified.

#### Acceptance Criteria

1. WHEN `tests/unit/test_session_manager.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/services/session_manager.py` (currently 14%, 369 statements).
2. WHEN `tests/unit/test_user_management.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/services/user_management.py` (currently 10%, 253 statements).
3. WHEN `tests/unit/test_task_execution.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/services/task_executor.py` (currently 12%, 194 statements).
4. WHEN `tests/unit/test_seeding_service.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/services/seeding_service.py` (currently 12%, 163 statements).
5. WHEN `tests/unit/test_webhook_manager.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/services/webhook_manager.py` (currently 16%, 161 statements).
6. WHEN `tests/unit/test_data_export_service.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/services/data_export.py` (currently 12%, 132 statements).
7. WHEN `tests/unit/test_health_check_service.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/services/health_check.py` (currently 11%, 103 statements).
8. WHEN `tests/unit/test_profiling_service.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/services/profiling_service.py` (currently 23%, 141 statements).
9. WHEN `tests/unit/test_rate_limiter.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/services/rate_limiter.py` (currently 20%, 44 statements).
10. WHEN `tests/unit/test_error_recovery.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/services/error_recovery.py` (currently 43%, 152 statements).
11. WHEN `tests/unit/test_sharding_service.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/services/sharding_service.py` (currently 43%, 63 statements).

---

### Requirement 3: Critical-Gap Route Tests (≥90% per module)

**User Story:** As a developer, I want every route module with less than 30% coverage to reach ≥90% coverage, so that all HTTP endpoints are verified for happy-path, error, and edge-case behaviour.

#### Acceptance Criteria

1. WHEN `tests/unit/test_payments_routes.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/routes/payments.py` (currently 11%, 247 statements), including Stripe mock responses for success, card-declined, and webhook-signature-failure paths.
2. WHEN `tests/unit/test_users_routes.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/routes/users.py` (currently 18%, 278 statements), including registration, MFA enable/disable, and password-reset flows.
3. WHEN `tests/unit/test_sessions_routes.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/routes/sessions.py` (currently 22%, 215 statements), including create, list, start, pause, resume, and end endpoints.
4. WHEN `tests/unit/test_task_routes.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/routes/tasks.py` (currently 18%, 180 statements).
5. WHEN `tests/unit/test_webhooks.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/routes/webhooks.py` (currently 22%, 119 statements).
6. WHEN `tests/unit/test_metrics_routes.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/routes/metrics.py` (currently 28%, 158 statements).
7. WHEN `tests/unit/test_export_routes.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/routes/export.py` (currently 25%, 104 statements).
8. WHEN `tests/unit/test_templates_routes.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/routes/templates.py` (currently 16%, 140 statements).
9. WHEN a route test for `app/routes/state.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/routes/state.py` (currently 14%, 153 statements).
10. WHEN a route test for `app/routes/auth.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/routes/auth.py` (currently 30%, 60 statements).
11. WHEN `tests/unit/test_api_keys.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/routes/api_keys.py` (currently 96%, 112 statements).
12. WHEN a route test for `app/routes/health.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/routes/health.py` (currently 54%, 28 statements).
13. WHEN a route test for `app/routes/admin.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/routes/admin.py` (currently 52%, 42 statements).
14. WHEN a route test for `app/routes/version.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/routes/version.py` (currently 66%, 32 statements).
15. IF a route handler returns an HTTP 4xx or 5xx status code, THEN THE Test_Suite SHALL include at least one test case asserting that specific status code for each handler.

---

### Requirement 4: Middleware Tests (≥90% per module)

**User Story:** As a developer, I want every middleware module to reach ≥90% coverage, so that request-processing logic including security, rate limiting, and CSRF protection is verified.

#### Acceptance Criteria

1. WHEN `tests/unit/test_rate_limiting_middleware.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/middleware/rate_limiting.py` (currently 20%, 87 statements), covering the allow path, the 429 path, and Redis-unavailable fallback.
2. WHEN `tests/unit/test_authentication_middleware.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/middleware/authentication.py`, covering valid token, missing token on protected path, and expired token paths.
3. WHEN a middleware test for `app/middleware/csrf.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/middleware/csrf.py` (currently 26%, 63 statements), covering token generation, valid token, missing token, and exempt-path logic.
4. WHEN `tests/unit/test_security_validation.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/middleware/security_validation.py` (currently 15%, 163 statements), covering clean input, SQL-injection pattern, and XSS pattern paths.
5. WHEN a middleware test for `app/middleware/security_headers.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/middleware/security_headers.py` (currently 30%, 23 statements).
6. WHEN `tests/unit/test_deprecation.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/middleware/deprecation.py` (currently 50%, 56 statements).
7. WHEN `tests/unit/test_profiling_middleware.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/middleware/profiling.py` (currently 0%, 47 statements).
8. WHEN `tests/unit/test_tracing_middleware.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/middleware/tracing.py` (currently 40%, 90 statements).
9. WHEN a middleware test for `app/middleware/logging.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/middleware/logging.py` (currently 0%, 65 statements).
10. WHEN a middleware test for `app/middleware/metrics.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/middleware/metrics.py`.
11. WHEN a middleware test for `app/middleware/api_versioning.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/middleware/api_versioning.py`.
12. WHEN a middleware test for `app/middleware/cors_config.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/middleware/cors_config.py`.
13. WHEN `tests/unit/test_schema_validation.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/middleware/schema_validation.py`.

---

### Requirement 5: Core Module Tests (≥80% per module)

**User Story:** As a developer, I want core application modules (config, main, CLI, tracing, DB utilities) to reach ≥80% coverage, so that application startup, configuration validation, and database management are verified.

#### Acceptance Criteria

1. WHEN a test for `app/config.py` is executed, THE Coverage_Tool SHALL report ≥80% statement coverage for `app/config.py` (currently 78%, 183 statements), covering valid settings, invalid JWT secret, missing production keys, and insecure-default detection.
2. WHEN a test for `app/main.py` is executed, THE Coverage_Tool SHALL report ≥80% statement coverage for `app/main.py` (currently 0%, 141 statements), covering `create_app(test_mode=False)`, `create_app(test_mode=True)`, and the `lifespan` startup/shutdown sequence.
3. WHEN a test for `app/exception_handlers.py` is executed, THE Coverage_Tool SHALL report ≥80% statement coverage for `app/exception_handlers.py` (currently 0%, 79 statements).
4. WHEN a test for `app/exceptions.py` is executed, THE Coverage_Tool SHALL report ≥80% statement coverage for `app/exceptions.py`.
5. WHEN a test for `app/tracing.py` is executed, THE Coverage_Tool SHALL report ≥80% statement coverage for `app/tracing.py` (currently 26%, 87 statements), using mocked OpenTelemetry modules.
6. WHEN `tests/unit/test_cli.py` is executed, THE Coverage_Tool SHALL report ≥80% statement coverage for `app/cli.py` (currently 0%, 90 statements), using CLI_Runner to invoke each command.
7. WHEN a test for `app/create_db.py` is executed, THE Coverage_Tool SHALL report ≥80% statement coverage for `app/create_db.py` (currently 0%, 22 statements).
8. WHEN a test for `app/reset_db.py` is executed, THE Coverage_Tool SHALL report ≥80% statement coverage for `app/reset_db.py` (currently 0%, 50 statements).
9. WHEN a test for `app/create_demo_user.py` is executed, THE Coverage_Tool SHALL report ≥80% statement coverage for `app/create_demo_user.py` (currently 0%, 26 statements).
10. WHEN a test for `app/database/connection.py` is executed, THE Coverage_Tool SHALL report ≥80% statement coverage for `app/database/connection.py` (currently 36%, 91 statements).
11. WHEN a test for `app/database/sharded_connection.py` is executed, THE Coverage_Tool SHALL report ≥80% statement coverage for `app/database/sharded_connection.py` (currently 36%, 94 statements).
12. WHEN a test for `app/models/schemas.py` is executed, THE Coverage_Tool SHALL report ≥80% statement coverage for `app/models/schemas.py` (currently 61%, 826 statements), covering Pydantic validators and serializers.
13. IF `app/config.py` is instantiated with a JWT_SECRET_KEY shorter than 32 characters in a non-production environment, THEN THE Settings SHALL raise a ValueError.
14. IF `app/config.py` is instantiated with a known insecure default JWT_SECRET_KEY value, THEN THE Settings SHALL raise a ValueError.

---

### Requirement 6: Schema Round-Trip and Serialization Properties

**User Story:** As a developer, I want property-based tests to verify that all Pydantic schema models correctly round-trip through JSON serialization, so that data integrity is guaranteed across API boundaries.

#### Acceptance Criteria

1. FOR ALL valid instances of each Pydantic model in `app/models/schemas.py`, THE Test_Suite SHALL verify that `Model.model_validate(instance.model_dump())` produces an equivalent object (round-trip property).
2. FOR ALL valid instances of each Pydantic model in `app/models/schemas.py`, THE Test_Suite SHALL verify that `Model.model_validate_json(instance.model_dump_json())` produces an equivalent object (JSON round-trip property).
3. WHEN a Pydantic model field receives an invalid type, THE Model SHALL raise a `ValidationError` with a descriptive message identifying the invalid field.
4. THE Test_Suite SHALL include at least one Hypothesis-based property test covering the round-trip property for each schema group (user schemas, session schemas, task schemas, webhook schemas).

---

### Requirement 7: Middleware Integration Tests (test_mode=False)

**User Story:** As a developer, I want integration tests that run the full middleware stack with `test_mode=False`, so that authentication, CSRF, and security-validation middleware interactions are verified end-to-end.

#### Acceptance Criteria

1. THE Test_Suite SHALL contain at least one integration test that sends a request to a protected endpoint with `test_mode=False` and a valid JWT token, and verifies a 200 response.
2. THE Test_Suite SHALL contain at least one integration test that sends a request to a protected endpoint with `test_mode=False` and no JWT token, and verifies a 401 response.
3. THE Test_Suite SHALL contain at least one integration test that sends a state-mutating request (POST/PUT/DELETE) with `test_mode=False` and a missing CSRF token, and verifies a 403 response.
4. THE Test_Suite SHALL contain at least one integration test that sends a request containing a SQL-injection pattern with `test_mode=False`, and verifies a 400 response from `SecurityValidationMiddleware`.
5. WHEN a request exceeds the configured rate limit with `test_mode=False`, THE Test_Suite SHALL verify a 429 response is returned.
6. WHEN a request is sent to a deprecated endpoint with `test_mode=False`, THE Test_Suite SHALL verify the response includes a `Deprecation` header.

---

### Requirement 8: Task and Celery Coverage

**User Story:** As a developer, I want Celery task modules to reach ≥90% coverage, so that background job logic is verified without requiring a live broker.

#### Acceptance Criteria

1. WHEN `tests/unit/test_webhook_tasks.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/tasks/webhook_tasks.py` (currently 0%, 20 statements), using a mocked Celery task context.
2. WHEN `tests/unit/test_experimental_tasks.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/tasks/experimental_tasks.py` (currently 18%, 197 statements).
3. WHEN `tests/unit/test_task_registry.py` is executed, THE Coverage_Tool SHALL report ≥90% statement coverage for `app/tasks/task_registry.py` (currently 56%, 27 statements).
4. IF a Celery task raises an unhandled exception, THEN THE Test_Suite SHALL verify the task transitions to a FAILURE state and the exception is logged.

---

### Requirement 9: Security-Focused Tests

**User Story:** As a developer, I want dedicated security tests for authentication, CSRF, injection prevention, and rate limiting, so that security regressions are caught automatically.

#### Acceptance Criteria

1. THE Test_Suite SHALL verify that a JWT token signed with a different secret key is rejected with a 401 response.
2. THE Test_Suite SHALL verify that an expired JWT token is rejected with a 401 response.
3. THE Test_Suite SHALL verify that a request body containing a SQL-injection pattern (e.g. `'; DROP TABLE users; --`) is rejected with a 400 response by `SecurityValidationMiddleware`.
4. THE Test_Suite SHALL verify that a POST request to a CSRF-protected endpoint without the `X-CSRF-Token` header is rejected with a 403 response.
5. THE Test_Suite SHALL verify that a client exceeding the configured rate limit receives a 429 response with a `Retry-After` header.
6. THE Test_Suite SHALL verify that responses from all endpoints include the `X-Content-Type-Options`, `X-Frame-Options`, and `Strict-Transport-Security` security headers.
7. THE Test_Suite SHALL verify that a request body containing an XSS pattern (e.g. `<script>alert(1)</script>`) is rejected with a 400 response by `SecurityValidationMiddleware`.
8. IF a user submits more than the configured maximum login attempts within the rate-limit window, THEN THE Test_Suite SHALL verify the account is temporarily locked or a 429 is returned.

---

### Requirement 10: Coverage Gate Enforcement

**User Story:** As a developer, I want the CI pipeline to fail if overall coverage drops below 100%, so that coverage regressions are caught before merging.

#### Acceptance Criteria

1. THE `pyproject.toml` `[tool.pytest.ini_options]` `addopts` field SHALL include `--cov-fail-under=100` so that the Test_Suite fails if overall statement coverage falls below 100%.
2. THE `pyproject.toml` `[tool.coverage.report]` section SHALL include `fail_under = 100` as a secondary enforcement mechanism.
3. WHEN the Test_Suite is executed and overall coverage is below 100%, THE Coverage_Tool SHALL exit with a non-zero return code.
4. WHEN the Test_Suite is executed and overall coverage is exactly 100%, THE Coverage_Tool SHALL exit with return code 0.
5. THE `pyproject.toml` `[tool.coverage.run]` `branch` setting SHALL be set to `true` so that branch coverage is measured in addition to statement coverage.

---

### Requirement 11: Test Suite Stability and Passing Rate

**User Story:** As a developer, I want all collected tests to pass without failures or errors, so that the test suite is a reliable signal of application correctness.

#### Acceptance Criteria

1. WHEN the full Test_Suite is executed with `pytest tests/`, THE Test_Suite SHALL report zero test failures and zero errors.
2. THE Test_Suite SHALL fix all currently-failing tests in `tests/unit/test_cli.py` so that CLI command tests pass.
3. WHEN `tests/unit/test_create_db.py` and `tests/unit/test_reset_db.py` are executed, THE Test_Suite SHALL report zero failures (currently failing due to psycopg2 import issues).
4. THE Test_Suite SHALL not contain duplicate test files covering the same module (e.g. `test_create_db.py` and `test_create_db_fixed.py` should be consolidated into one file).
5. WHILE the Test_Suite is executing, THE Test_Suite SHALL complete within 300 seconds for the full unit and property test run (excluding load tests).
6. THE Test_Suite SHALL use the `mock_psycopg2` fixture from `tests/unit/conftest.py` for all tests that import `app/create_db.py` or `app/reset_db.py`.

---

### Requirement 12: Property-Based Tests for Core Correctness Properties

**User Story:** As a developer, I want property-based tests covering key invariants and round-trip properties, so that correctness is verified over a wide range of generated inputs rather than only hand-crafted examples.

#### Acceptance Criteria

1. THE Test_Suite SHALL include a property test verifying that for any valid user registration payload, `model_validate(payload.model_dump()) == payload` (schema round-trip invariant).
2. THE Test_Suite SHALL include a property test verifying that for any valid session object, serializing then deserializing produces an equivalent object (session round-trip invariant).
3. THE Test_Suite SHALL include a property test verifying that for any string input, `SecurityValidationMiddleware` either passes the request or returns a 400 — it never raises an unhandled exception (total-function property).
4. THE Test_Suite SHALL include a property test verifying that for any valid JWT payload, `encode` followed by `decode` returns the original payload (JWT round-trip property).
5. THE Test_Suite SHALL include a property test verifying that applying the rate-limiter `check` function twice with the same key and count does not produce a lower remaining count than applying it once (idempotence-adjacent monotonicity property).
6. THE Test_Suite SHALL include a property test verifying that for any list of tasks, the task registry `register` then `get` returns the same task (registry round-trip property).
7. WHERE Hypothesis profiles are configured in `tests/conftest.py`, THE Test_Suite SHALL use the `ci` profile when the `CI` environment variable is set, and the `dev` profile otherwise.
