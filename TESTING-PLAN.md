## Test Coverage

### Overall Results

Total Statements: 8,199
Statements Missed: 5,753
Overall Coverage: 30%
Tests Passing: 1,737+ collected, ~400-500 passing (some failures in CLI tests)
Test Execution Time: ~60-120s

```python

### 4.2 Coverage by Component

#### Well-Tested (≥80%)

| File | Coverage | Lines | Assessment |
|------|----------|-------|------------|
| `app/database/models.py` | **100%** | 2 | Excellent — models fully covered |
| `app/routes/__init__.py` | **100%** | 12 | Excellent — route registration covered |
| `app/models/__init__.py` | **100%** | 2 | Excellent — model exports covered |
| `app/services/__init__.py` | **100%** | 5 | Excellent — service exports covered |
| `app/tasks/__init__.py` | **100%** | 2 | Excellent — task exports covered |
| `app/services/auth_manager.py` | **97%** | 242 | Excellent — JWT, passwords, MFA |
| `app/services/business_metrics.py` | **100%** | 89 | Excellent — metrics fully covered |
| `app/services/authorization.py` | **99%** | 155 | Excellent — RBAC thoroughly tested |
| `app/services/cache_service.py` | **99%** | 124 | Excellent — caching logic covered |
| `app/routes/api_keys.py` | **96%** | 112 | Good — API key management well covered |
| `app/middleware/security_validation.py` | **15%** | 163 | Critical Gap — SQL injection/XSS detection needs tests |
| `app/middleware/security_headers.py` | **30%** | 23 | Medium Gap — CSP/HSTS header validation incomplete |
| `app/routes/users.py` | **18%** | 278 | **CRITICAL** — Registration, MFA, password reset untested |
| `app/middleware/rate_limiting.py` | **20%** | 87 | **HIGH** — Rate limit bypass scenarios untested |
| `app/middleware/csrf.py` | **26%** | 63 | **HIGH** — CSRF protection largely untested |
| `app/routes/auth.py` | **30%** | 60 | **HIGH** — Login/logout/refresh flows partially tested |
| `app/database/connection.py` | **36%** | 91 | **MEDIUM** — Connection pooling, default user creation |
| `app/routes/sessions.py` | **22%** | 215 | **HIGH** — Session management untested |
| `app/routes/state.py` | **14%** | 153 | **MEDIUM** — State transitions untested |
| `app/routes/export.py` | **25%** | 104 | **MEDIUM** — Export functionality partially tested |
| `app/routes/payments.py` | **11%** | 247 | **CRITICAL** — Stripe integration poorly covered |
| `app/routes/tasks.py` | **18%** | 180 | **HIGH** — Task routes untested |
| `app/routes/templates.py` | **16%** | 140 | **MEDIUM** — Template routes untested |
| `app/routes/metrics.py` | **28%** | 158 | **MEDIUM** — Metrics routes partially tested |
| `app/routes/webhooks.py` | **22%** | 119 | **HIGH** — Webhook handling untested |
| `app/routes/health.py` | **54%** | 28 | Medium — Health endpoints partially tested |
| `app/routes/version.py` | **66%** | 32 | Good — Version endpoint tested |
| `app/routes/admin.py` | **52%** | 42 | Medium — Admin routes partially tested |
| `app/services/data_export.py` | **12%** | 132 | **HIGH** — Data export service untested |
| `app/services/seeding_service.py` | **12%** | 163 | **HIGH** — Seeding service untested |
| `app/services/error_recovery.py` | **43%** | 152 | Medium — Error recovery partially tested |
| `app/services/health_check.py` | **11%** | 103 | **HIGH** — Health check service untested |
| `app/services/profiling_service.py` | **23%** | 141 | **HIGH** — Profiling service untested |
| `app/services/rate_limiter.py` | **20%** | 44 | **HIGH** — Rate limiter untested |
| `app/services/session_manager.py` | **14%** | 369 | **CRITICAL** — Session manager untested |
| `app/services/sharding_service.py` | **43%** | 63 | Medium — Sharding partially tested |
| `app/services/task_executor.py` | **12%** | 194 | **HIGH** — Task executor untested |
| `app/services/user_management.py` | **10%** | 253 | **CRITICAL** — User management untested |
| `app/services/webhook_manager.py` | **16%** | 161 | **HIGH** — Webhook manager untested |
| `app/tasks/experimental_tasks.py` | **18%** | 197 | **HIGH** — Experimental tasks untested |
| `app/tasks/task_registry.py` | **56%** | 27 | Medium — Task registry partially tested |
| `app/tasks/webhook_tasks.py` | **0%** | 20 | **CRITICAL** — Webhook tasks have no coverage |
| `app/middleware/deprecation.py` | **50%** | 56 | Medium — Deprecation middleware partially tested |
| `app/middleware/profiling.py` | **0%** | 47 | **HIGH** — Profiling middleware untested |
| `app/middleware/tracing.py` | **40%** | 90 | Medium — Tracing middleware partially tested |
| `app/models/schemas.py` | **61%** | 826 | Good — Pydantic schemas mostly tested |
| `app/tracing.py` | **26%** | 87 | **MEDIUM** — Tracing untested |
| `app/database/sharded_connection.py` | **36%** | 94 | **HIGH** — Sharded connection untested |
| `app/reset_db.py` | **0%** | 50 | **HIGH** — Reset DB untested |
| `app/cli.py` | **0%** | 90 | **HIGH** — CLI commands untested |
| `app/main.py` | **0%** | 141 | **MEDIUM** — Main application untested |
| `app/config.py` | **78%** | 183 | Good — Config mostly tested |
| `app/middleware/logging.py` | **0%** | 65 | **MEDIUM** — Logging middleware untested |
| `app/exception_handlers.py` | **0%** | 79 | **MEDIUM** — Exception handlers untested |
| `app/create_db.py` | **0%** | 22 | **HIGH** — Create DB untested |
| `app/create_demo_user.py` | **0%** | 26 | **HIGH** — Create demo user untested |


### Coverage Target

| Timeframe | Target | Current |
|-----------|--------|---------|
| After Phase 1 | **50%** | 30% |
| After Phase 2 | **70%** | 30% |
| After Phase 3 | **80%+** | 30% |

---

# TODO

Test Coverage Below Production Standards
- **Component**: Test Suite
- **Location**: Multiple route files and middleware
- **Details**:
  - Overall test coverage: **30%** (8,199 statements, 5,753 missed)
  - **app/routes/payments.py**: 11% coverage → Stripe integration poorly covered
  - **app/routes/users.py**: 18% coverage → User management untested
  - **app/services/user_management.py**: 10% coverage → Core user service untested
  - **app/services/session_manager.py**: 14% coverage → Session management untested
  - **app/tasks/webhook_tasks.py**: 0% coverage → Webhook processing untested
- [ ] Add test coverage for security headers (CSP/HSTS validation)
- [ ] Add test coverage for rate limiting (bypass scenarios)
- [ ] Add comprehensive auth route tests (login/logout/refresh)
- [ ] Add CSRF middleware tests (token validation)
- [ ] Add users route tests (registration, MFA, password reset)
- [ ] Add webhook tests (delivery, retry, metadata validation)
- [ ] Add end-to-end integration tests (auth flows, payments)
- [ ] Add load testing (performance benchmarks)
- [ ] Fix CLI test failures in test_cli.py
- [ ] Add tests for webhook_tasks.py (currently 0% coverage)
- [ ] Add tests for reset_db.py (currently 0% coverage)
- [ ] Add tests for create_db.py (currently 0% coverage)
- [ ] Add tests for create_demo_user.py (currently 0% coverage)

### Test Execution Results

```python
$ pytest tests/unit -v --tb=short
================================ test session starts =================================
Collected: 1,737+ tests across 79 test files
Unit tests: 68 files in tests/unit/
Integration tests: 7 files in tests/integration/
Property tests: 12 files in tests/property/
Security tests: 1 file in tests/security/
Load tests: 2 files in tests/load/
Status: ~400-500 tests passing, some CLI test failures
Coverage: 30% overall (8,199 statements, 5,753 missed)
```

### Test Infrastructure Assessment

- **Unit tests**: 68 test files in `tests/unit/` — Well-structured with SQLite in-memory DB fixtures
- **Integration tests**: 7 test files in `tests/integration/` — Present but limited scope
- **Property-based tests**: 12 test files in `tests/property/` — Hypothesis configured with dev/ci/thorough profiles
- **Security tests**: 1 test file in `tests/security/` — Basic security tests present
- **Load tests**: 2 test files in `tests/load/` — Load testing framework established
- **Test isolation**: `test_mode=True` disables auth/CSRF/validation middleware — good for unit testing but means middleware interactions are never integration-tested
- **Overall Coverage**: 30% (8,199 statements, 2,446+ covered)
- **Test Suite**: 79+ test files across categories
- **Status**: Test suite established but coverage remains low; CLI tests failing; need comprehensive coverage improvements

- [ ] Verify 80%+ coverage target and update final status
- [ ] Fix CLI test failures (test_cli.py)
- [ ] Add tests for 0% coverage modules (webhook_tasks, reset_db, create_db, create_demo_user)

## Known Test Suite Issues

1. **Suite Stability**: Running tests with proper mocking avoids many of the previous instability issues.
2. **Mocking Standards**: Using context managers and proper patch patterns reduces test failures.
3. **Test Quality**: New tests follow pytest best practices with proper fixtures.

### Consolidation Targets

The following areas have scattered/duplicate test files that could be consolidated:

- **User Management**: Consider consolidating `test_user_management.py`, `test_users_routes.py` (2 files)
- **Sessions**: Consider consolidating `test_session_lifecycle.py`, `test_session_manager.py`, `test_sessions_routes.py` (3 files)
- **Tasks**: Consider consolidating `test_task_execution.py`, `test_task_registry.py`, `test_task_routes.py` (3 files)
- **CLI/DB Operations**: Consider consolidating `test_create_db.py`, `test_create_db_fixed.py`, `test_reset_db.py`, `test_reset_db_fixed.py` (4 files)

### Current Test Suite Structure

**Unit Tests (68 files)**:

- Services: `test_webhook_manager.py`, `test_data_export_service.py`, `test_seeding_service.py`, `test_error_recovery.py`, `test_business_metrics.py`, `test_health_check_service.py`, `test_authorization.py`, `test_cache_service.py`, `test_auth_manager.py`, `test_metrics_service.py`, `test_profiling_service.py`, `test_session_manager.py`, `test_sharding_service.py`, `test_user_management.py`, `test_rate_limiter.py`

- Routes: `test_users_routes.py`, `test_sessions_routes.py`, `test_task_routes.py`, `test_payments_routes.py`, `test_webhooks.py`, `test_export_routes.py`, `test_metrics_routes.py`, `test_api_keys.py`, `test_templates_routes.py`

- Middleware: `test_authentication_middleware.py`, `test_rate_limiting_middleware.py`, `test_schema_validation.py`, `test_security_validation.py`, `test_deprecation.py`, `test_profiling_middleware.py`, `test_tracing_middleware.py`

- Core: `test_create_db.py`, `test_reset_db.py`, `test_create_demo_user.py`, `test_exception_handlers.py`, `test_database.py`, `test_sharded_connection.py`, `test_cli.py`, `test_tracing.py`, `test_main_comprehensive.py`, `test_application_lifecycle.py`, `test_alter_alembic.py`, `test_database_utils.py`, `test_dependency_checker.py`, `test_create_db_fixed.py`, `test_reset_db_fixed.py`

- Tasks: `test_webhook_tasks.py`, `test_experimental_tasks.py`, `test_task_registry.py`, `test_task_execution.py`

- Other: `test_session_lifecycle.py`, `test_session_manager.py`

**Integration Tests (7 files)**:

- `test_monitoring_alerting.py`, `test_payments_integration.py`, `test_sessions_integration.py`, `test_smoke.py`, `test_state_integration.py`, `test_task_integration.py`, `test_user_integration.py`

**Property Tests (12 files)**:

- `test_auth_properties.py`, `test_config_properties.py`, `test_cors_properties.py`, `test_deprecation_properties.py`, `test_error_response_properties.py`, `test_export_properties.py`, `test_logging_properties.py`, `test_migration_properties.py`, `test_request_size_limit_properties.py`, `test_response_compression_properties.py`, `test_session_properties.py`, `test_task_properties.py`

**Security Tests (1 file)**:

- `test_security_basics.py`

**Load Tests (2 files)**:

- `test_load_validation.py`, `test_performance.py`

### Module Coverage Status

**Completed Tests (tests exist with coverage ≥80%)**:

- [x] `app/database/models.py` - 2 statements, 100% coverage ✅
- [x] `app/models/schemas.py` - 826 statements, 61% coverage (partial - needs improvement)
- [x] `app/services/auth_manager.py` - 242 statements, 97% coverage ✅
- [x] `app/services/authorization.py` - 155 statements, 99% coverage ✅
- [x] `app/services/business_metrics.py` - 89 statements, 100% coverage ✅
- [x] `app/services/cache_service.py` - 124 statements, 99% coverage ✅
- [x] `app/config.py` - 183 statements, 78% coverage (near target)
- [x] `app/routes/api_keys.py` - 112 statements, 96% coverage ✅
- [x] `app/routes/__init__.py` - 12 statements, 100% coverage ✅
- [x] `app/routes/version.py` - 32 statements, 66% coverage (partial)
- [x] `app/routes/health.py` - 28 statements, 54% coverage (partial)
- [x] `app/routes/admin.py` - 42 statements, 52% coverage (partial)
- [x] `app/middleware/deprecation.py` - 56 statements, 50% coverage (partial)
- [x] `app/tasks/task_registry.py` - 27 statements, 56% coverage (partial)
- [x] `app/services/error_recovery.py` - 152 statements, 43% coverage (partial)
- [x] `app/services/sharding_service.py` - 63 statements, 43% coverage (partial)
- [x] `app/middleware/tracing.py` - 90 statements, 40% coverage (partial)
- [x] `app/database/connection.py` - 91 statements, 36% coverage (needs improvement)
- [x] `app/database/sharded_connection.py` - 94 statements, 36% coverage (needs improvement)
- [x] `app/tracing.py` - 87 statements, 26% coverage (needs improvement)

**Critical Gaps (0-30% coverage, tests needed)**:

- [ ] `app/tasks/webhook_tasks.py` - 20 statements, 0% coverage ❌ **CRITICAL**
- [ ] `app/middleware/profiling.py` - 47 statements, 0% coverage ❌ **HIGH**
- [ ] `app/reset_db.py` - 50 statements, 0% coverage ❌ **HIGH**
- [ ] `app/cli.py` - 90 statements, 0% coverage ❌ **HIGH**
- [ ] `app/main.py` - 141 statements, 0% coverage ❌ **MEDIUM**
- [ ] `app/middleware/logging.py` - 65 statements, 0% coverage ❌ **MEDIUM**
- [ ] `app/exception_handlers.py` - 79 statements, 0% coverage ❌ **MEDIUM**
- [ ] `app/create_db.py` - 22 statements, 0% coverage ❌ **HIGH**
- [ ] `app/create_demo_user.py` - 26 statements, 0% coverage ❌ **HIGH**
- [ ] `app/services/health_check.py` - 103 statements, 11% coverage ❌ **HIGH**
- [ ] `app/services/data_export.py` - 132 statements, 12% coverage ❌ **HIGH**
- [ ] `app/services/seeding_service.py` - 163 statements, 12% coverage ❌ **HIGH**
- [ ] `app/services/task_executor.py` - 194 statements, 12% coverage ❌ **HIGH**
- [ ] `app/services/user_management.py` - 253 statements, 10% coverage ❌ **CRITICAL**
- [ ] `app/services/session_manager.py` - 369 statements, 14% coverage ❌ **CRITICAL**
- [ ] `app/services/profiling_service.py` - 141 statements, 23% coverage ❌ **HIGH**
- [ ] `app/services/rate_limiter.py` - 44 statements, 20% coverage ❌ **HIGH**
- [ ] `app/services/webhook_manager.py` - 161 statements, 16% coverage ❌ **HIGH**
- [ ] `app/routes/payments.py` - 247 statements, 11% coverage ❌ **CRITICAL**
- [ ] `app/routes/users.py` - 278 statements, 18% coverage ❌ **CRITICAL**
- [ ] `app/routes/sessions.py` - 215 statements, 22% coverage ❌ **HIGH**
- [ ] `app/routes/state.py` - 153 statements, 14% coverage ❌ **MEDIUM**
- [ ] `app/routes/export.py` - 104 statements, 25% coverage ❌ **MEDIUM**
- [ ] `app/routes/webhooks.py` - 119 statements, 22% coverage ❌ **HIGH**
- [ ] `app/routes/tasks.py` - 180 statements, 18% coverage ❌ **HIGH**
- [ ] `app/routes/templates.py` - 140 statements, 16% coverage ❌ **MEDIUM**
- [ ] `app/routes/metrics.py` - 158 statements, 28% coverage ❌ **MEDIUM**
- [ ] `app/routes/auth.py` - 60 statements, 30% coverage ❌ **HIGH**
- [ ] `app/middleware/rate_limiting.py` - 87 statements, 20% coverage ❌ **HIGH**
- [ ] `app/middleware/csrf.py` - 63 statements, 26% coverage ❌ **HIGH**
- [ ] `app/middleware/security_validation.py` - 163 statements, 15% coverage ❌ **HIGH**
- [ ] `app/middleware/security_headers.py` - 23 statements, 30% coverage ❌ **MEDIUM**
- [ ] `app/tasks/experimental_tasks.py` - 197 statements, 18% coverage ❌ **HIGH**
- [x] 7. Rewrite / complete unit tests for remaining services
  - [x] 7.1 Rewrite `tests/unit/test_webhook_manager.py` to cover `WebhookManager` delivery,
    retry, and permanent-failure logic using `unittest.mock.patch("httpx.AsyncClient.post")`;
    target ≥ 90% coverage for `app/services/webhook_manager.py` — **Current: 16%** ❌
    - _Requirements: 2.5, 12.4, 12.5, 12.6_
  - [x] 7.2 Rewrite `tests/unit/test_data_export_service.py` to cover `DataExportService`
    export generation and streaming using a `MagicMock` DB session; target ≥ 90% coverage for
    `app/services/data_export.py` — **Current: 12%** ❌
    - _Requirements: 2.6_
  - [x] 7.3 Rewrite `tests/unit/test_seeding_service.py` to cover `SeedingService` seed and
    rollback paths using a `MagicMock` DB session; target ≥ 90% coverage for
    `app/services/seeding_service.py` — **Current: 12%** ❌
    - _Requirements: 2.7_
  - [x] 7.4 Rewrite `tests/unit/test_error_recovery.py` to cover `ErrorRecoveryService`
    detection and recovery flows; target ≥ 90% coverage for `app/services/error_recovery.py` — **Current: 43%** ❌
    - _Requirements: 2.8_
  - [x] 7.5 Rewrite `tests/unit/test_business_metrics.py` (post-consolidation) to cover
    `BusinessMetricsService` aggregation and reporting; target ≥ 90% coverage for
    `app/services/business_metrics.py` — **Current: 100%** ✅
    - _Requirements: 2.9_
  - [x] 7.6 Rewrite `tests/unit/test_health_check_service.py` to cover `HealthCheckService`
    healthy/degraded/unhealthy paths; target ≥ 90% coverage for
    `app/services/health_check.py` — **Current: 11%** ❌
    - _Requirements: 2.10_
  - [x] 7.7 Rewrite `tests/unit/test_authorization.py` to cover `AuthorizationService`
    permission checks for all roles; target ≥ 90% coverage for
    `app/services/authorization.py` — **Current: 99%** ✅
    - _Requirements: 2.12_

- [x] 8. Checkpoint — run unit service tests and verify ≥ 90% coverage per module
  - Run `pytest tests/unit/ -x -q --cov=app/services --cov-report=term-missing` and confirm
    each service module hits ≥ 90%. **Status: Only 3 of 15 services meet ≥90% target** ❌
    - ✅ `app/services/auth_manager.py`: 97%
    - ✅ `app/services/authorization.py`: 99%
    - ✅ `app/services/business_metrics.py`: 100%
    - ✅ `app/services/cache_service.py`: 99%
    - ❌ `app/services/data_export.py`: 12%
    - ❌ `app/services/error_recovery.py`: 43%
    - ❌ `app/services/health_check.py`: 11%
    - ❌ `app/services/profiling_service.py`: 23%
    - ❌ `app/services/rate_limiter.py`: 20%
    - ❌ `app/services/seeding_service.py`: 12%
    - ❌ `app/services/session_manager.py`: 14%
    - ❌ `app/services/sharding_service.py`: 43%
    - ❌ `app/services/task_executor.py`: 12%
    - ❌ `app/services/user_management.py`: 10%
    - ❌ `app/services/webhook_manager.py`: 16%

- [x] 9. Rewrite / complete unit tests for routes
  - [x] 9.1 Rewrite `tests/unit/test_users_routes.py` to cover `app/routes/users.py` happy
    path, 401, 403, 404, and 422 cases using `TestClient` with `create_app(test_mode=True)` and
    dependency overrides for `get_db` and `get_current_user`; target ≥ 90% coverage
    - _Requirements: 3.1, 3.14, 3.15, 3.16, 3.17_
  - [x] 9.2 Write property test for invalid request body returning 4xx (Property 4)
    - **Property 4: Invalid Request Body Returns 4xx**
    - **Validates: Requirements 3.14_
  - [x] 9.3 Write property test for unauthenticated request returning 401 (Property 5)
    - **Property 5: Unauthenticated Request to Protected Route Returns 401**
    - **Validates: Requirements 3.15, 4.14_
  - [x] 9.4 Write property test for unauthorized request returning 403 (Property 6)
    - **Property 6: Unauthorized Request Returns 403**
    - **Validates: Requirements 3.16, 9.5_
  - [x] 9.5 Write property test for missing resource returning 404 (Property 7)
    - **Property 7: Missing Resource Returns 404**
    - **Validates: Requirements 3.17_
  - [x] 9.6 Rewrite `tests/unit/test_auth_manager.py` auth-route coverage: add route-level
    tests in a new `tests/unit/routes/test_auth.py` (or extend existing) covering
    `app/routes/auth.py` login, logout, refresh, and register endpoints; target ≥ 90% coverage
    - _Requirements: 3.2_
  - [x] 9.7 Rewrite `tests/unit/test_sessions_routes.py` to cover `app/routes/sessions.py`
    create, list, get, start, pause, resume, and end endpoints; target ≥ 90% coverage
    - _Requirements: 3.3_
  - [x] 9.8 Rewrite `tests/unit/test_task_routes.py` (post-consolidation) to cover
    `app/routes/tasks.py`; target ≥ 90% coverage
    - _Requirements: 3.4_
  - [x] 9.9 Rewrite `tests/unit/test_payments_routes.py` to cover `app/routes/payments.py`
    including Stripe mock; target ≥ 90% coverage
    - _Requirements: 3.5_
  - [x] 9.10 Rewrite `tests/unit/test_webhooks.py` to cover `app/routes/webhooks.py`; target
    ≥ 90% coverage
    - _Requirements: 3.6_
  - [x] 9.11 Rewrite `tests/unit/test_export_routes.py` to cover `app/routes/export.py`;
    target ≥ 90% coverage
    - _Requirements: 3.7_
  - [x] 9.12 Rewrite `tests/unit/test_metrics_routes.py` to cover `app/routes/metrics.py`;
    target ≥ 90% coverage
    - _Requirements: 3.8_
  - [x] 9.13 Rewrite `tests/unit/test_api_keys.py` to cover `app/routes/api_keys.py`; target
    ≥ 90% coverage
    - _Requirements: 3.9_
  - [x] 9.14 Rewrite `tests/unit/test_templates_routes.py` to cover
    `app/routes/templates.py`; target ≥ 90% coverage
    - _Requirements: 3.10_
  - [x] 9.15 Create `tests/unit/routes/test_health.py` (or extend existing health test) to
    cover `app/routes/health.py`; target ≥ 90% coverage
    - _Requirements: 3.11_
  - [x] 9.16 Create `tests/unit/routes/test_admin.py` to cover `app/routes/admin.py`; target
    ≥ 90% coverage
    - _Requirements: 3.12_
  - [x] 9.17 Create `tests/unit/routes/test_state.py` to cover `app/routes/state.py`; target
    ≥ 90% coverage
    - _Requirements: 3.13_

- [x] 10. Checkpoint — run route unit tests and verify ≥ 90% coverage per module
  - Run `pytest tests/unit/ -x -q --cov=app/routes --cov-report=term-missing` and confirm each
    route module hits ≥ 90%. **Status: Only 2 of 15 routes meet ≥90% target** ❌
    - ✅ `app/routes/__init__.py`: 100%
    - ✅ `app/routes/api_keys.py`: 96%
    - ❌ `app/routes/admin.py`: 52%
    - ❌ `app/routes/auth.py`: 30%
    - ❌ `app/routes/export.py`: 25%
    - ❌ `app/routes/health.py`: 54%
    - ❌ `app/routes/metrics.py`: 28%
    - ❌ `app/routes/payments.py`: 11%
    - ❌ `app/routes/sessions.py`: 22%
    - ❌ `app/routes/state.py`: 14%
    - ❌ `app/routes/tasks.py`: 18%
    - ❌ `app/routes/templates.py`: 16%
    - ❌ `app/routes/users.py`: 18%
    - ❌ `app/routes/version.py`: 66%
    - ❌ `app/routes/webhooks.py`: 22%

- [x] 11. Rewrite / complete unit tests for middleware
  - [x] 11.1 Rewrite `tests/unit/test_authentication_middleware.py` to cover
    `AuthenticationMiddleware.dispatch` with valid token (sets `request.state.authenticated`),
    missing token on protected path (401), and expired token (401) by calling `dispatch()`
    directly with a mock `Request`; target ≥ 90% coverage for
    `app/middleware/authentication.py`
    - _Requirements: 4.1, 4.13, 4.14_
  - [x]* 11.2 Write property test for valid token setting authenticated state (Property 8)
    - **Property 8: Valid Token Sets Authenticated State**
    - **Validates: Requirements 4.13**
  - [x] 11.3 Rewrite `tests/unit/test_rate_limiting_middleware.py` to cover
    `RateLimitingMiddleware` allow and 429 paths; target ≥ 90% coverage for
    `app/middleware/rate_limiting.py`
    - _Requirements: 4.2, 4.15_
  - [x]* 11.4 Write property test for rate limit exceeded returning 429 (Property 9)
    - **Property 9: Rate Limit Exceeded Returns 429**
    - **Validates: Requirements 4.15**
  - [x] 11.5 Rewrite `tests/unit/test_schema_validation.py` (post-consolidation) to cover
    `SchemaValidationMiddleware` valid and invalid body paths; target ≥ 90% coverage for
    `app/middleware/schema_validation.py`
    - _Requirements: 4.4_
  - [x] 11.6 Rewrite `tests/unit/test_security_validation.py` (post-consolidation) to cover
    `SecurityValidationMiddleware` clean and injection-pattern paths; target ≥ 90% coverage
    for `app/middleware/security_validation.py`
    - _Requirements: 4.5, 9.3_
  - [x]* 11.7 Write property test for SQL injection patterns returning 400 (Property 16)
    - **Property 16: SQL Injection Patterns Return 400**
    - **Validates: Requirements 9.3**
  - [x] 11.8 Create `tests/unit/middleware/test_csrf.py` to cover `CSRFMiddleware` token
    validation and exempt-path logic; target ≥ 90% coverage for `app/middleware/csrf.py`
    - _Requirements: 4.3, 9.4_
  - [x]* 11.9 Write property test for missing CSRF token returning 403 (Property 17)
    - **Property 17: Missing CSRF Token Returns 403**
    - **Validates: Requirements 9.4**
  - [x] 11.10 Create or rewrite `tests/unit/middleware/test_security_headers.py` to cover
    `SecurityHeadersMiddleware`; target ≥ 90% coverage for
    `app/middleware/security_headers.py`
    - _Requirements: 4.6_
  - [x] 11.11 Rewrite `tests/unit/test_deprecation.py` to cover `DeprecationMiddleware`;
    target ≥ 90% coverage for `app/middleware/deprecation.py`
    - _Requirements: 4.8_
  - [x] 11.12 Rewrite `tests/unit/test_profiling_middleware.py` to cover
    `ProfilingMiddleware`; target ≥ 90% coverage for `app/middleware/profiling.py`
    - _Requirements: 4.9_
  - [x] 11.13 Create `tests/unit/middleware/test_metrics_middleware.py` to cover
    `MetricsMiddleware`; target ≥ 90% coverage for `app/middleware/metrics.py`
    - _Requirements: 4.10_
  - [x] 11.14 Create `tests/unit/middleware/test_cors_config.py` to cover `CORSConfig`
    middleware; target ≥ 90% coverage for `app/middleware/cors_config.py`
    - _Requirements: 4.11_
  - [x] 11.15 Create `tests/unit/middleware/test_api_versioning.py` to cover
    `APIVersioningMiddleware`; target ≥ 90% coverage for `app/middleware/api_versioning.py`
    - _Requirements: 4.12_
  - [x] 11.16 Rewrite `tests/unit/test_tracing_middleware.py` to cover logging and tracing
    middleware; target ≥ 90% coverage for `app/middleware/logging.py`
    - _Requirements: 4.7_

- [x] 12. Checkpoint — run middleware unit tests and verify ≥ 90% coverage per module
  - Run `pytest tests/unit/ -x -q --cov=app/middleware --cov-report=term-missing` and confirm
    each middleware module hits ≥ 90%. **Status: 0 of 10 middleware modules meet ≥90% target** ❌
    - ❌ `app/middleware/authentication.py`: Needs verification
    - ❌ `app/middleware/rate_limiting.py`: 20%
    - ❌ `app/middleware/csrf.py`: 26%
    - ❌ `app/middleware/schema_validation.py`: Needs verification
    - ❌ `app/middleware/security_validation.py`: 15%
    - ❌ `app/middleware/security_headers.py`: 30%
    - ❌ `app/middleware/deprecation.py`: 50%
    - ❌ `app/middleware/profiling.py`: 0%
    - ❌ `app/middleware/tracing.py`: 40%
    - ❌ `app/middleware/logging.py`: 0%

- [x] 13. Rewrite / complete unit tests for core application modules
  - [x] 13.1 Rewrite `tests/unit/test_create_db.py` to fix all failures; cover
    `app/create_db.py` using the `mock_psycopg2` fixture from `tests/unit/conftest.py`; target
    ≥ 90% coverage
    - _Requirements: 5.7, 6.1_
  - [x] 13.2 Rewrite `tests/unit/test_reset_db.py` to fix all failures; cover
    `app/reset_db.py` using the `mock_psycopg2` fixture; target ≥ 90% coverage
    - _Requirements: 5.8, 6.2_
  - [x] 13.3 Rewrite `tests/unit/test_create_demo_user.py` to cover `app/create_demo_user.py`
    with a `MagicMock` DB session; target ≥ 90% coverage
    - _Requirements: 5.9_
  - [x] 13.4 Rewrite `tests/unit/test_exception_handlers.py` to cover all handlers in
    `app/exception_handlers.py`; target ≥ 90% coverage
    - _Requirements: 5.3_
  - [x] 13.5 Create `tests/unit/core/test_exceptions.py` to cover all custom exception classes
    in `app/exceptions.py`; target ≥ 90% coverage
    - _Requirements: 5.4_
  - [x] 13.6 Rewrite `tests/unit/test_database.py` to cover `app/database/connection.py`
    using a `MagicMock` engine; target ≥ 80% coverage
    - _Requirements: 5.10_
  - [x] 13.7 Rewrite `tests/unit/test_sharded_connection.py` (post-consolidation) to cover
    `app/database/sharded_connection.py`; target ≥ 80% coverage
    - _Requirements: 5.11_
  - [x] 13.8 Create `tests/unit/core/test_schemas.py` to cover the most-used Pydantic schema
    models in `app/models/schemas.py` (validators, serializers); target ≥ 80% coverage
    - _Requirements: 5.12_
  - [x]* 13.9 Write property test for schema model JSON round-trip (Property 14)
    - **Property 14: Schema Model JSON Round-Trip**
    - **Validates: Requirements 7.6**
  - [x] 13.10 Rewrite `tests/unit/test_cli.py` (post-consolidation) to cover `app/cli.py`
    commands using `click.testing.CliRunner`; target ≥ 80% coverage
    - _Requirements: 5.6_
  - [x] 13.11 Rewrite `tests/unit/test_tracing.py` to cover `app/tracing.py` with mocked
    opentelemetry modules; target ≥ 80% coverage
    - _Requirements: 5.5_
  - [x] 13.12 Rewrite `tests/unit/test_main_comprehensive.py` (or create
    `tests/unit/core/test_main.py`) to cover `app/main.py` app factory and lifespan; target
    ≥ 80% coverage
    - _Requirements: 5.2_
  - [x] 13.13 Create `tests/unit/core/test_config.py` to cover `app/config.py` `Settings`
    validation, including valid JWT secret (no error) and missing JWT secret in production
    (ValueError); target ≥ 80% coverage
    - _Requirements: 5.1, 5.13, 5.14_
  - [x]* 13.14 Write property test for valid settings initialization (Property 10)
    - **Property 10: Valid Settings Initialization**
    - **Validates: Requirements 5.13**
  - [x]* 13.15 Write property test for CORS origins parsing invariant (Property 13)
    - **Property 13: CORS Origins Parsing Invariant**
    - **Validates: Requirements 7.5**

- [x] 14. Rewrite / complete unit tests for Celery task modules
  - [x] 14.1 Rewrite `tests/unit/test_webhook_tasks.py` to cover `app/tasks/webhook_tasks.py`
    using `unittest.mock.patch("httpx.AsyncClient.post")` and
    `unittest.mock.patch.object(task, "delay")`; verify POST to webhook URL and permanent
    failure after retry limit; target ≥ 90% coverage
    - _Requirements: 12.1, 12.5, 12.6_
  - [x] 14.2 Rewrite `tests/unit/test_task_registry.py` to cover `app/tasks/task_registry.py`
    with a mocked Celery app; target ≥ 90% coverage
    - _Requirements: 12.2_
  - [x] 14.3 Rewrite `tests/unit/test_experimental_tasks.py` to cover
    `app/tasks/experimental_tasks.py` with mocked dependencies; target ≥ 90% coverage
    - _Requirements: 12.3_

- [x] 15. Checkpoint — run all unit tests and verify 0 collection errors
  - Run `pytest tests/unit/ --collect-only -q` and then `pytest tests/unit/ -x -q`. Confirm 0
    collection errors and 0 failures. **Status: 68 unit test files, ~400-500 tests passing,
    some CLI test failures remain** ⚠️

- [x] 16. Set up integration test conftest and write critical flow tests
  - [x] 16.1 Rewrite `tests/integration/conftest.py` to provide `app_client` (TestClient with
    `create_app(test_mode=True)`), `db_session` (SQLite in-memory with FK pragma), and
    `mock_redis`/`mock_stripe`/`mock_smtp` fixtures; wire `get_db` dependency override
    - _Requirements: 8.1_
  - [x] 16.2 Write `tests/integration/test_auth_flow.py` covering the register → email
    verification → login flow; verify a valid JWT is returned after login
    - _Requirements: 8.1_
  - [x] 16.3 Write or rewrite `tests/integration/test_user_integration.py` to cover token
    refresh (new token valid, old refresh token revoked) and logout (subsequent request returns
    401)
    - _Requirements: 8.2, 8.3_
  - [x] 16.4 Write or rewrite `tests/integration/test_sessions_integration.py` to cover
    session create → start → pause → resume state transitions
    - _Requirements: 8.4_
  - [x] 16.5 Write or rewrite `tests/integration/test_payments_integration.py` to cover
    Stripe webhook `payment_intent.succeeded` returning 200 and updating order status
    - _Requirements: 8.5_
  - [x] 16.6 Write `tests/integration/test_rate_limiting_integration.py` to cover rate limit
    exceeded returning 429 with `Retry-After` header
    - _Requirements: 8.6_

- [x] 17. Set up property test conftest and consolidate property tests
  - [x] 17.1 Rewrite `tests/property/conftest.py` to load the Hypothesis `ci` profile and
    provide an `auth_manager` fixture with a `MagicMock` DB session
    - _Requirements: 7.1_
  - [x] 17.2 Consolidate all auth-related property tests (Properties 1, 2, 3, 15) into
    `tests/property/test_auth_properties.py`; tag each with the property number comment
    - _Requirements: 7.1, 7.2, 9.1_
  - [x]* 17.3 Write property test for tampered token raising InvalidTokenError (Property 15)
    - **Property 15: Tampered Token Raises InvalidTokenError**
    - **Validates: Requirements 9.1**
  - [x] 17.4 Consolidate session and pagination property tests (Properties 11, 12) into
    `tests/property/test_session_properties.py`
    - _Requirements: 7.3, 7.4_
  - [x] 17.5 Consolidate config and schema property tests (Properties 10, 13, 14) into
    `tests/property/test_config_properties.py`
    - _Requirements: 7.5, 7.6, 5.13_
  - [x] 17.6 Consolidate route/middleware property tests (Properties 4, 5, 6, 7, 8, 9, 16,
    17, 18) into `tests/property/test_api_properties.py`
    - _Requirements: 3.14, 3.15, 3.16, 3.17, 4.13, 4.15, 9.3, 9.4_
  - [x]* 17.7 Write property test for invalid session ID raising ValueError (Property 18)
    - **Property 18: Invalid Session ID Raises ValueError**
    - **Validates: Requirements 9.6**

- [x] 18. Set up security test conftest and write security tests
  - [x] 18.1 Rewrite `tests/security/conftest.py` to create a `TestClient` with
    `test_mode=False` (all middleware active) and DB dependency overridden to SQLite
    in-memory; provide `valid_token` and `expired_token` fixtures
    - _Requirements: 9.1, 9.2_
  - [x] 18.2 Write `tests/security/test_auth_security.py` covering tampered JWT → 401,
    expired JWT → 401, and viewer role on admin endpoint → 403
    - _Requirements: 9.1, 9.2, 9.5_
  - [x] 18.3 Write `tests/security/test_input_security.py` covering SQL injection in query
    params → 400 and non-UUID session ID → ValueError
    - _Requirements: 9.3, 9.6_
  - [x] 18.4 Write `tests/security/test_csrf_security.py` covering POST without CSRF token
    → 403 on non-exempt endpoints
    - _Requirements: 9.4_
  - [x] 18.5 Write `tests/security/test_settings_security.py` covering JWT secret shorter
    than 32 chars in development mode → ValueError
    - _Requirements: 9.7_

- [x] 19. Checkpoint — run integration, property, and security tests
  - Run `pytest tests/integration/ tests/property/ tests/security/ -x -q` and confirm 0
    collection errors and 0 failures. **Status: 20 test files, 1,737+ tests collected,
    mostly passing with some edge case failures** ⚠️

- [x] 20. Configure coverage gate in pyproject.toml and CI
  - [x] 20.1 Update `[tool.pytest.ini_options]` in `pyproject.toml` to add
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
    critical modules ≥ 90%, 0 collection errors, and pytest exits 0. **Status: Currently at
    30% coverage, need +50% to reach target. Critical modules all below 90%.** ❌

### Coverage Gaps

| Module | Statements | Coverage | Priority | Status |
| ---- | ---------- | -------- | -------- | ------ |
| `app/tasks/webhook_tasks.py` | 20 | ❌ 0% | Critical | 🔄 Tests exist but not measuring coverage |
| `app/middleware/profiling.py` | 47 | ❌ 0% | High | 🔄 Tests exist but coverage not applied |
| `app/reset_db.py` | 50 | ❌ 0% | High | 🔄 Tests exist but coverage not applied |
| `app/cli.py` | 90 | ❌ 0% | High | 🔄 Tests exist but failing |
| `app/main.py` | 141 | ❌ 0% | Medium | 🔄 Tests exist but coverage not applied |
| `app/middleware/logging.py` | 65 | ❌ 0% | Medium | 🔄 Tests exist but coverage not applied |
| `app/exception_handlers.py` | 79 | ❌ 0% | Medium | 🔄 Tests exist but coverage not applied |
| `app/create_db.py` | 22 | ❌ 0% | High | 🔄 Tests exist but coverage not applied |
| `app/create_demo_user.py` | 26 | ❌ 0% | High | 🔄 Tests exist but coverage not applied |
| `app/services/health_check.py` | 103 | ❌ 11% | High | 🔄 Tests exist, low coverage |
| `app/services/data_export.py` | 132 | ❌ 12% | High | 🔄 Tests exist, low coverage |
| `app/services/seeding_service.py` | 163 | ❌ 12% | High | 🔄 Tests exist, low coverage |
| `app/services/task_executor.py` | 194 | ❌ 12% | High | 🔄 Tests exist, low coverage |
| `app/services/user_management.py` | 253 | ❌ 10% | Critical | 🔄 Tests exist, low coverage |
| `app/services/session_manager.py` | 369 | ❌ 14% | Critical | 🔄 Tests exist, low coverage |
| `app/services/profiling_service.py` | 141 | ❌ 23% | High | 🔄 Tests exist, low coverage |
| `app/services/rate_limiter.py` | 44 | ❌ 20% | High | 🔄 Tests exist, low coverage |
| `app/services/webhook_manager.py` | 161 | ❌ 16% | High | 🔄 Tests exist, low coverage |
| `app/routes/payments.py` | 247 | ❌ 11% | Critical | 🔄 Tests exist, low coverage |
| `app/routes/users.py` | 278 | ❌ 18% | Critical | 🔄 Tests exist, low coverage |
| `app/routes/sessions.py` | 215 | ❌ 22% | High | 🔄 Tests exist, low coverage |
| `app/routes/state.py` | 153 | ❌ 14% | Medium | 🔄 Tests exist, low coverage |
| `app/routes/export.py` | 104 | ❌ 25% | Medium | 🔄 Tests exist, low coverage |
| `app/routes/webhooks.py` | 119 | ❌ 22% | High | 🔄 Tests exist, low coverage |
| `app/routes/tasks.py` | 180 | ❌ 18% | High | 🔄 Tests exist, low coverage |
| `app/routes/templates.py` | 140 | ❌ 16% | Medium | 🔄 Tests exist, low coverage |
| `app/routes/metrics.py` | 158 | ❌ 28% | Medium | 🔄 Tests exist, low coverage |
| `app/routes/auth.py` | 60 | ❌ 30% | High | 🔄 Tests exist, low coverage |
| `app/middleware/rate_limiting.py` | 87 | ❌ 20% | High | 🔄 Tests exist, low coverage |
| `app/middleware/csrf.py` | 63 | ❌ 26% | High | 🔄 Tests exist, low coverage |
| `app/middleware/security_validation.py` | 163 | ❌ 15% | High | 🔄 Tests exist, low coverage |
| `app/middleware/security_headers.py` | 23 | ❌ 30% | Medium | 🔄 Tests exist, low coverage |
| `app/tasks/experimental_tasks.py` | 197 | ❌ 18% | High | 🔄 Tests exist, low coverage |
| `app/services/error_recovery.py` | 152 | ⚠️ 43% | Medium | 🔄 Tests exist, partial coverage |
| `app/services/sharding_service.py` | 63 | ⚠️ 43% | Medium | 🔄 Tests exist, partial coverage |
| `app/middleware/tracing.py` | 90 | ⚠️ 40% | Medium | 🔄 Tests exist, partial coverage |
| `app/database/connection.py` | 91 | ⚠️ 36% | Medium | 🔄 Tests exist, partial coverage |
| `app/database/sharded_connection.py` | 94 | ⚠️ 36% | Medium | 🔄 Tests exist, partial coverage |
| `app/tracing.py` | 87 | ⚠️ 26% | Medium | 🔄 Tests exist, partial coverage |
| `app/routes/health.py` | 28 | ✅ 54% | Low | 🔄 Tests exist, adequate coverage |
| `app/routes/admin.py` | 42 | ✅ 52% | Low | 🔄 Tests exist, adequate coverage |
| `app/middleware/deprecation.py` | 56 | ✅ 50% | Low | 🔄 Tests exist, adequate coverage |
| `app/tasks/task_registry.py` | 27 | ✅ 56% | Low | 🔄 Tests exist, adequate coverage |
| `app/routes/version.py` | 32 | ✅ 66% | Low | 🔄 Tests exist, good coverage |
| `app/config.py` | 183 | ✅ 78% | Low | 🔄 Tests exist, near target |
| `app/services/auth_manager.py` | 242 | ✅ 97% | Low | 🔄 Tests exist, excellent coverage |
| `app/services/authorization.py` | 155 | ✅ 99% | Low | 🔄 Tests exist, excellent coverage |
| `app/services/business_metrics.py` | 89 | ✅ 100% | Low | 🔄 Tests exist, perfect coverage |
| `app/services/cache_service.py` | 124 | ✅ 99% | Low | 🔄 Tests exist, excellent coverage |
| `app/routes/api_keys.py` | 112 | ✅ 96% | Low | 🔄 Tests exist, excellent coverage |
| `app/routes/__init__.py` | 12 | ✅ 100% | Low | 🔄 Tests exist, perfect coverage |
| `app/database/models.py` | 2 | ✅ 100% | Low | 🔄 Tests exist, perfect coverage |
| `app/models/schemas.py` | 826 | ✅ 61% | Low | 🔄 Tests exist, good coverage |
