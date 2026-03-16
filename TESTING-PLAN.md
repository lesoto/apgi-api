# Test Coverage Improvement Plan

## Coverage Status Summary

> **Overall Coverage**: ~28.5% (8,063 statements total)  
> **Test Suite**: 67 test files, ~1,100+ tests in `tests/unit/`

---

## ✅ Completed

- [x] **Metrics Routes** (`app/routes/metrics.py`) → **100%** ✅
  - Fixed `test_html_escaping` which had an incorrect assertion logic (expecting raw tags when they were correctly escaped).
  - Verified all dashboard endpoints (overview, sessions, tasks, users, templates, profiling) are fully covered.

- [x] **Authorization Service** (`app/services/authorization.py`) → **94%** (was 34%)
  - Resolved 4 major test failures caused by `Mock(spec=[])` in Python 3.14 which were breaking `hasattr` checks.
  - Missed lines: 238, 269, 422-426, 538-539, 590-591, 604.

- [x] **Rate Limiting Middleware** (`app/middleware/rate_limiting.py`) → **90%** (was 19%)
  - **Rebuilt the test suite**: Replaced fictional API tests (which called non-existent methods) with real ASGI interface tests.
  - Missed lines: 111-115, 119-120, 122, 240-244 (X-Forwarded-For trusted proxy logic).

- [x] **Core Tracing** (`app/tracing.py`) → **83%** (was 35%)
  - Verified existing comprehensive tests against actual source.
  - Missed lines: 39-59 (Error handling for missing OTel dependencies).

---

## Coverage Gaps

| Module | Statements | Status |
|--------|------------|--------|
| `app/cli.py` | 90 | ❌ High Priority |
| `app/main.py` | 141 | ❌ High Priority (App Factory) |
| `app/middleware/security_validation.py` | 156 | ❌ High Priority (User Request) |
| `app/exception_handlers.py` | 79 | ❌ |
| `app/routes/payments.py` | 207 | ❌ |
| `app/routes/templates.py` | 140 | ❌ |
| `app/services/error_recovery.py` | 152 | ❌ |
| `app/services/seeding_service.py` | 163 | ❌ |
| `app/database/sharded_connection.py` | 94 | ❌ |
| `app/reset_db.py` | 50 | ❌ |
| `app/middleware/schema_validation.py` | 11% | 100% | Most validation logic |
| `app/services/user_management.py` | 10% | 100% | Core user logic |
| `app/services/data_export.py` | 12% | 100% | Export logic |
| `app/services/task_executor.py` | 12% | 100% | Async execution |
| `app/middleware/authentication.py` | 23% | 100% | Token validation middleware |
| `app/services/profiling_service.py` | 23% | 100% | Performance profiling |
| `app/services/session_manager.py` | 14% | 100% | Session lifecycle |
| `app/routes/sessions.py` | 22% | 100% | Session endpoints |
| `app/routes/users.py` | 18% | 100% | User endpoints |

---

## Known Test Suite Issues

1. **Suite Stability**: Running the full batch of 1,000+ tests frequently hangs or segment faults due to `psycopg2` and `opentelemetry` mock interactions/state leakage.
2. **Mocking Standards**: Avoid `Mock(spec=[])` as it is fragile on Python 3.14. Prefer anonymous classes or `MagicMock` with explicit attributes.
3. **Draft Tests**: Several files in `tests/unit/` were found to be testing "fictional" APIs (legacy code or AI-generated placeholders) that don't match the actual implementation.

### Consolidation Targets

The following areas have too many scattered/duplicate test files:
- **User Management**: Merge `test_user_management*` (7 files) into one suite.
- **Sessions**: Merge `test_sessions*` (5 files).
- **Tasks**: Merge `test_tasks*` (5 files).

---

## Remaining Tasks

- [ ] Fix `test_user_management.py` (Complexity check regex/logic mismatch)
- [ ] Add tests for `app/middleware/security_validation.py` (0%)
- [ ] Add tests for `app/database/sharded_connection.py` (0%)
- [ ] Add tests for `app/cli.py` (0%)
- [ ] Consolidate duplicate test suites for Users and Sessions.
- [ ] Implement trusted proxy test cases for rate limiting (Lines 111-122).
- [ ] Mock dependency failure for tracing.py (Lines 39-59).
- [ ] Final coverage verification across all modules.
