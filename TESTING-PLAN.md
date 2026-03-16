# Test Coverage Improvement Plan

## Coverage Status Summary

> **Overall Coverage**: 1% (8,100 statements, 80 covered)
> **Test Suite**: 67 test files, ~1,943 tests in `tests/`
> **Status**: Critical - coverage much lower than expected (1% vs 40% in plan)
> **Issue**: Import errors and failing tests preventing proper coverage measurement

- [ ] Fix failing tests in test_create_db.py (7 failures - SQL composition and assertion issues)
- [ ] Fix failing tests in test_reset_db.py (5 failures - TypeError and assertion issues)
- [ ] Create tests for modules with 0% coverage:
  - app/middleware/schema_validation.py (11%)
  - app/services/seeding_service.py (12%)
  - app/services/data_export.py (12%)
  - app/routes/templates.py (16%)
  - app/middleware/deprecation.py (18%)
  - app/routes/api_keys.py (23%)
  - app/routes/webhooks.py (22%)
  - app/routes/export.py (25%)
  - app/routes/payments.py (26%)
  - app/tracing.py (26%)
  - app/database/sharded_connection.py (28%)
  - app/routes/metrics.py (28%)
  - app/middleware/csrf.py (29%)
  - app/middleware/profiling.py (28%)
  - app/routes/tasks.py (33%)
  - app/routes/users.py (29%)
  - app/services/cache_service.py (29%)
  - app/services/auth_manager.py (33%)
  - app/services/business_metrics.py (35%)
  - app/services/error_recovery.py (43%)
- [ ] Fix failing tests and improve coverage for partial modules
- [ ] Verify 100% coverage and update final status

## Known Test Suite Issues

1. **Suite Stability**: Running the full batch of 1,000+ tests frequently hangs or segment faults due to `psycopg2` and `opentelemetry` mock interactions/state leakage.
2. **Mocking Standards**: Avoid `Mock(spec=[])` as it is fragile on Python 3.14. Prefer anonymous classes or `MagicMock` with explicit attributes.
3. **Draft Tests**: Several files in `tests/unit/` were found to be testing "fictional" APIs (legacy code or AI-generated placeholders) that don't match the actual implementation.

### Consolidation Targets

The following areas have too many scattered/duplicate test files:

- **User Management**: Merge `test_user_management*` (7 files) into one suite.
- **Sessions**: Merge `test_sessions*` (5 files).
- **Tasks**: Merge `test_tasks*` (5 files).

- [x] `app/create_db.py` - 22 statements, 0% coverage
- [x] `app/create_demo_user.py` - 26 statements, 0% coverage (tests passing but not measuring)
- [x] `app/reset_db.py` - 50 statements, 0% coverage
- [x] `app/tasks/webhook_tasks.py` - 27 statements, 0% coverage (no tests)
- [ ] `app/services/seeding_service.py` - 163 statements, 0% coverage
- [ ] `app/services/data_export.py` - 132 statements, 0% coverage
- [ ] `app/middleware/schema_validation.py` - 167 statements, 0% coverage
- [ ] `app/routes/templates.py` - 140 statements, 0% coverage
- [ ] `app/middleware/deprecation.py` - 56 statements, 0% coverage
- [ ] `app/routes/api_keys.py` - 112 statements, 0% coverage
- [ ] `app/routes/webhooks.py` - 119 statements, 0% coverage
- [ ] `app/routes/export.py` - 104 statements, 0% coverage
- [ ] `app/routes/payments.py` - 207 statements, 0% coverage
- [ ] `app/tracing.py` - 87 statements, 0% coverage
- [ ] `app/database/sharded_connection.py` - 94 statements, 0% coverage
- [ ] `app/routes/metrics.py` - 158 statements, 0% coverage
- [ ] `app/middleware/csrf.py` - 63 statements, 0% coverage
- [ ] `app/middleware/profiling.py` - 47 statements, 0% coverage
- [ ] `app/routes/tasks.py` - 180 statements, 0% coverage
- [ ] `app/routes/users.py` - 278 statements, 0% coverage
- [ ] `app/services/cache_service.py` - 124 statements, 0% coverage
- [ ] `app/services/auth_manager.py` - 242 statements, 0% coverage
- [ ] `app/services/business_metrics.py` - 89 statements, 0% coverage
- [ ] `app/services/error_recovery.py` - 152 statements, 0% coverage
- [ ] Fix failing tests and test suite stability issues
- [ ] Final coverage verification and achieve 100%

### Coverage Gaps

| Module | Statements | Coverage | Priority | Status |
| ---- | ---------- | -------- | -------- | ------ |
| `app/create_db.py` | 22 | ❌ 0% | Critical | 🔄 Tests failing, needs fixing |
| `app/create_demo_user.py` | 26 | ❌ 0% | Critical | 🔄 Tests not running properly |
| `app/reset_db.py` | 50 | ❌ 0% | Critical | 🔄 Tests failing, needs fixing |
| `app/tasks/webhook_tasks.py` | 27 | ❌ 0% | Critical | 🔄 No tests |
| `app/middleware/schema_validation.py` | 167 | ❌ 0% | High | 🔄 Needs tests |
| `app/services/seeding_service.py` | 163 | ❌ 0% | High | 🔄 Needs tests |
| `app/services/data_export.py` | 132 | ❌ 0% | High | 🔄 Needs tests |
| `app/routes/templates.py` | 140 | ❌ 0% | High | 🔄 Needs tests |
| `app/middleware/deprecation.py` | 56 | ❌ 0% | High | 🔄 Needs tests |
| `app/routes/api_keys.py` | 112 | ❌ 0% | High | 🔄 Needs tests |
| `app/routes/webhooks.py` | 119 | ❌ 0% | High | 🔄 Needs tests |
| `app/routes/export.py` | 104 | ❌ 0% | High | 🔄 Needs tests |
| `app/routes/payments.py` | 207 | ❌ 0% | High | 🔄 Needs tests |
| `app/tracing.py` | 87 | ❌ 0% | High | 🔄 Needs tests |
| `app/database/sharded_connection.py` | 94 | ❌ 0% | High | 🔄 Needs tests |
| `app/routes/metrics.py` | 158 | ❌ 0% | High | 🔄 Needs tests |
| `app/middleware/csrf.py` | 63 | ❌ 0% | High | 🔄 Needs tests |
| `app/middleware/profiling.py` | 47 | ❌ 0% | High | 🔄 Needs tests |
| `app/routes/tasks.py` | 180 | ❌ 0% | High | 🔄 Needs tests |
| `app/routes/users.py` | 278 | ❌ 0% | High | 🔄 Needs tests |
| `app/services/cache_service.py` | 124 | ❌ 0% | High | 🔄 Needs tests |
| `app/services/auth_manager.py` | 242 | ❌ 0% | High | 🔄 Needs tests |
| `app/services/business_metrics.py` | 89 | ❌ 0% | High | 🔄 Needs tests |
| `app/services/error_recovery.py` | 152 | ❌ 0% | High | 🔄 Needs tests |
| `app/cli.py` | 90 | ❌ 0% | Medium | 🔄 Needs tests |
| `app/main.py` | 141 | ❌ 0% | Medium | 🔄 Needs tests |
| `app/middleware/security_validation.py` | 163 | ❌ 0% | High | 🔄 Needs tests |
| `app/exception_handlers.py` | 79 | ❌ 0% | Medium | 🔄 Needs tests |
| `app/config.py` | 183 | ❌ 0% | Medium | 🔄 Needs tests |
| `app/models/schemas.py` | 826 | ❌ 0% | Medium | 🔄 Needs tests |
| `app/middleware/logging.py` | 65 | ❌ 0% | Medium | 🔄 Needs tests |
| `app/routes/health.py` | 28 | ❌ 0% | Medium | 🔄 Needs tests |
| `app/middleware/security_headers.py` | 23 | ❌ 0% | Medium | 🔄 Needs tests |
