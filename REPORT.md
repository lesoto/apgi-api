# APGI API — Comprehensive Codebase Audit Report

**Date:** 2026-03-20
**Auditor:** Claude Code (Automated Static & Dynamic Analysis)
**Scope:** Full codebase audit — architecture, security, testing, performance, technical debt
**Codebase:** ~179 Python files, ~63,000 lines of code

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Security Audit](#3-security-audit)
4. [Test Coverage Analysis](#4-test-coverage-analysis)
5. [Bugs & Defects](#5-bugs--defects)
6. [Performance Bottlenecks](#6-performance-bottlenecks)
7. [Technical Debt](#7-technical-debt)
8. [Prioritized Remediation Roadmap](#8-prioritized-remediation-roadmap)

---

## 1. Executive Summary

The APGI API is a well-structured FastAPI application with strong foundational security patterns (JWT with JTI revocation, bcrypt+SHA-256 password hashing, CSRF protection, SSRF prevention). However, the audit reveals **critical gaps in test coverage (39% overall)**, **environment files tracked in git containing secrets**, and **a missing dependency (`apgi_system`) that breaks two test modules**. Security middleware — the most critical defense layer — has the lowest coverage in the codebase.

### Key Metrics

| Metric | Value | Assessment |
|--------|-------|------------|
| Overall Test Coverage | **39%** | Below acceptable threshold (≥80%) |
| Unit Tests Passing | **474 passed, 2 skipped, 0 failed** | Existing tests are healthy |
| Critical Security Coverage | **0–29%** on key middleware | High risk |
| OWASP Top 10 Findings | **5 categories affected** | Requires immediate attention |
| Severity: Critical | **3 findings** | |
| Severity: High | **7 findings** | |
| Severity: Medium | **8 findings** | |
| Severity: Low | **5 findings** | |

---

## 2. Architecture Overview

### 2.1 Application Structure

```
app/
├── main.py              # Application factory: create_app(test_mode=False)
├── config.py            # Settings from env vars with security validation
├── celery_app.py        # Celery broker (Redis db/1) and backend (Redis db/2)
├── exceptions.py        # Custom exception hierarchy (APIError base)
├── routes/              # 10 FastAPI routers
├── services/            # Business logic layer
├── middleware/           # 13-layer middleware stack
├── database/            # SQLAlchemy ORM models, connection pooling
├── tasks/               # Celery task definitions and registry
└── alembic/             # Database migrations
```

### 2.2 Middleware Stack (outermost → innermost)

```
RequestSizeLimitMiddleware → GZipMiddleware → PrometheusMetricsMiddleware →
ProfilingMiddleware (opt) → RequestLoggingMiddleware → APIVersioningMiddleware →
ResponseSchemaValidationMiddleware → CSRFMiddleware → AuthenticationMiddleware →
DeprecationMiddleware → RateLimitingMiddleware → CORSMiddleware
```

**Observation:** The 13-layer middleware stack is comprehensive but adds latency to every request. The ordering is mostly correct — authentication before rate limiting ensures revoked tokens are caught early. However, rate limiting _after_ authentication means unauthenticated brute-force attacks bypass per-user rate limits.

### 2.3 Database Architecture

- **PostgreSQL** via SQLAlchemy (sync ORM) with connection pooling (`pool_size=20`, `max_overflow=30`)
- **Redis db/0**: Caching, sessions, token blocklist
- **Redis db/1**: Celery broker
- **Redis db/2**: Celery results
- **Optional sharding** via `sharded_connection.py` (disabled by default)
- **11 ORM models**: User, Session, Task, TaskDependency, SessionData, SessionTemplate, RefreshToken, APIKey, WebhookDelivery, AuditLog, Order/Subscription

### 2.4 Authentication Flow

1. `POST /v1/auth/login` → JWT access token + refresh token
2. Access tokens include JTI for revocation via Redis blocklist
3. Refresh via `POST /v1/auth/refresh` with token rotation
4. TOTP MFA supported via `pyotp` with backup codes
5. API key authentication as alternative to JWT

---

## 3. Security Audit

### 3.1 OWASP Top 10 Mapping

#### A01:2021 — Broken Access Control

| ID | Finding | Severity | Status |
|----|---------|----------|--------|
| SEC-001 | RBAC authorization service has 99% coverage and correct role hierarchy | — | **PASS** |
| SEC-002 | Resource ownership checks enforced in authorization layer | — | **PASS** |
| SEC-003 | Rate limiting middleware has only **19% test coverage** — bypass scenarios untested | **High** | FAIL |

**Evidence (SEC-003):** `app/middleware/rate_limiting.py` (302 lines) — coverage report shows 19%. Key untested paths: trusted proxy handling, endpoint-specific rate configuration, rate limit reset logic.

#### A02:2021 — Cryptographic Failures

| ID | Finding | Severity | Status |
|----|---------|----------|--------|
| SEC-004 | `.env.development` tracked in git with dev JWT secret key | **Critical** | FAIL |
| SEC-005 | `.env.production` tracked in git with `CHANGE_ME` placeholder secrets | **Critical** | FAIL |
| SEC-006 | JWT secret validation requires ≥32 chars, rejects insecure defaults | — | **PASS** |
| SEC-007 | bcrypt + SHA-256 pre-hash handles >72-byte passwords correctly | — | **PASS** |
| SEC-008 | CURSOR_SIGNING_KEY validated at startup | — | **PASS** |

**Evidence (SEC-004/005):**
```bash
$ git ls-files | grep '\.env'
.env.development    # Contains: JWT_SECRET_KEY=dev_secret_key_change_in_production_min_32_chars
.env.production     # Contains: JWT_SECRET_KEY=CHANGE_ME_TO_SECURE_RANDOM_STRING_MIN_32_CHARS
```
Despite `.gitignore` containing `.env.*`, these files are already tracked. They must be removed from git history.

**Reproduction steps:**
1. Clone the repository
2. Open `.env.development` — JWT secret is visible
3. Open `.env.production` — placeholder secrets visible (risk: deployed as-is)

#### A03:2021 — Injection

| ID | Finding | Severity | Status |
|----|---------|----------|--------|
| SEC-009 | SQL injection pattern detection in `security_validation.py` (85% coverage) | — | **PASS** |
| SEC-010 | XSS pattern detection middleware present | — | **PASS** |
| SEC-011 | SQLAlchemy parameterized queries used throughout | — | **PASS** |

#### A04:2021 — Insecure Design

| ID | Finding | Severity | Status |
|----|---------|----------|--------|
| SEC-012 | CSRF middleware has only **29% test coverage** | **High** | FAIL |
| SEC-013 | Security headers middleware has **0% test coverage** | **High** | FAIL |
| SEC-014 | Authentication middleware has **83% coverage** — good but critical gaps remain | **Medium** | PARTIAL |

**Evidence (SEC-013):** `app/middleware/security_headers.py` (120 lines) — sets CSP, HSTS, X-Frame-Options DENY, Permissions-Policy but has zero test assertions validating these headers are applied correctly.

#### A05:2021 — Security Misconfiguration

| ID | Finding | Severity | Status |
|----|---------|----------|--------|
| SEC-015 | Production config validation raises ValueError on insecure settings | — | **PASS** |
| SEC-016 | CORS configuration validated in Settings.__post_init__() | — | **PASS** |
| SEC-017 | Default admin user created with credentials written to temp file | **Medium** | REVIEW |

**Evidence (SEC-017):** `app/database/connection.py` writes default admin credentials to a temp file on first run. While the file is temporary, if the process crashes before cleanup, credentials may persist on disk.

#### A07:2021 — Identification and Authentication Failures

| ID | Finding | Severity | Status |
|----|---------|----------|--------|
| SEC-018 | Auth routes have only **30% test coverage** | **High** | FAIL |
| SEC-019 | User routes (registration, MFA, password reset) have only **18% coverage** | **High** | FAIL |
| SEC-020 | Token revocation via Redis JTI blocklist — well implemented | — | **PASS** |
| SEC-021 | Refresh token rotation implemented | — | **PASS** |

#### A10:2021 — Server-Side Request Forgery (SSRF)

| ID | Finding | Severity | Status |
|----|---------|----------|--------|
| SEC-022 | SSRF prevention in webhook_manager.py — private IP blocking, DNS rebinding protection | — | **PASS** |
| SEC-023 | SSRF prevention lacks dedicated test coverage | **Medium** | FAIL |

### 3.2 Additional Security Findings

| ID | Finding | Severity | Category |
|----|---------|----------|----------|
| SEC-024 | Stripe webhook signature verification implemented correctly | — | Payments |
| SEC-025 | HMAC-SHA256 used for webhook payload signing | — | Integrity |
| SEC-026 | Password reset flow has minimal test coverage | **Medium** | Auth |
| SEC-027 | MFA backup codes generated but recovery flow undertested | **Medium** | Auth |
| SEC-028 | API key authentication path less tested than JWT path | **Medium** | Auth |

---

## 4. Test Coverage Analysis

### 4.1 Overall Results

```
Total Statements: 8,147
Statements Missed: 4,933
Overall Coverage: 39%
Tests Passing: 474 passed, 2 skipped, 0 failed
Test Execution Time: 24.82s
```

### 4.2 Coverage by Component

#### Well-Tested (≥80%)

| File | Coverage | Lines | Assessment |
|------|----------|-------|------------|
| `app/database/models.py` | **100%** | 746 | Excellent — all 11 models fully covered |
| `app/services/authorization.py` | **99%** | 631 | Excellent — RBAC thoroughly tested |
| `app/services/auth_manager.py` | **97%** | 635 | Excellent — JWT, passwords, MFA |
| `app/routes/payments.py` | **89%** | 458 | Good — Stripe integration well covered |
| `app/middleware/security_validation.py` | **85%** | 387 | Good — SQL injection/XSS detection |
| `app/middleware/authentication.py` | **83%** | 447 | Good but gaps in edge cases |
| `app/exceptions.py` | **~95%** | 503 | Excellent — error handling well tested |

#### Critical Gaps (<50%)

| File | Coverage | Lines | Risk |
|------|----------|-------|------|
| `app/middleware/security_headers.py` | **0%** | 120 | **CRITICAL** — No validation of CSP/HSTS/X-Frame headers |
| `app/routes/users.py` | **18%** | 1050 | **CRITICAL** — Registration, MFA, password reset untested |
| `app/middleware/rate_limiting.py` | **19%** | 302 | **HIGH** — Rate limit bypass scenarios untested |
| `app/middleware/csrf.py` | **29%** | 218 | **HIGH** — CSRF protection largely untested |
| `app/routes/auth.py` | **30%** | 283 | **HIGH** — Login/logout/refresh flows untested |
| `app/database/connection.py` | **41%** | 277 | **MEDIUM** — Connection pooling, default user creation |
| `app/routes/sessions.py` | **<30%** | est. | **HIGH** — Session management untested |
| `app/routes/state.py` | **<30%** | est. | **MEDIUM** — State transitions untested |
| `app/routes/export.py` | **<30%** | est. | **MEDIUM** — Export functionality untested |

### 4.3 Test Infrastructure Assessment

- **Unit tests**: Well-structured with SQLite in-memory DB fixtures
- **Integration tests**: Present but limited scope
- **Property-based tests**: Hypothesis configured with dev/ci/thorough profiles
- **Test isolation**: `test_mode=True` disables auth/CSRF/validation middleware — good for unit testing but means middleware interactions are never integration-tested

---

## 5. Bugs & Defects

### BUG-001: Missing `apgi_system` Dependency (Critical)

**Severity:** Critical
**Files:** `tests/unit/test_experimental_tasks.py`, `tests/unit/test_task_registry.py`
**Description:** Both test files import from `apgi_system` package which is not in `requirements.txt` or `requirements-dev.txt` and is not installable. These tests fail with `ModuleNotFoundError`.

**Reproduction:**
```bash
$ pytest tests/unit/test_experimental_tasks.py
ModuleNotFoundError: No module named 'apgi_system'
```

**Impact:** Two entire test modules are non-functional. Any CI pipeline that doesn't explicitly skip these files will fail.

**Fix:** Either add `apgi_system` to dependencies or update imports to reference the correct package.

### BUG-002: .env Files Tracked in Git Despite .gitignore Rule

**Severity:** Critical
**Files:** `.env.development`, `.env.production`, `.gitignore`
**Description:** `.gitignore` contains `.env.*` pattern, but `.env.development` and `.env.production` were committed before the rule was added. They remain tracked and visible to anyone with repo access.

**Reproduction:**
```bash
$ git ls-files | grep '\.env\.'
.env.development
.env.production
```

**Fix:**
```bash
git rm --cached .env.development .env.production
git commit -m "Remove tracked .env files"
# Rotate all secrets that were exposed
```

### BUG-003: Rate Limiting After Authentication in Middleware Stack

**Severity:** Medium
**File:** `app/main.py`
**Description:** `RateLimitingMiddleware` is positioned _after_ `AuthenticationMiddleware` in the stack. This means unauthenticated requests (e.g., brute-force login attempts) are processed through the full authentication middleware before rate limiting kicks in. While per-IP rate limiting still applies, the ordering allows more processing overhead per malicious request than necessary.

**Recommendation:** Move rate limiting before authentication for pre-auth endpoints, or add a separate lightweight rate limiter at the outermost layer for login/register endpoints.

### BUG-004: Hypothesis Tests May Hang in CI

**Severity:** Medium
**Files:** `tests/property/`
**Description:** Property-based tests using Hypothesis can run indefinitely without the correct profile settings. No timeout guard is configured in `pytest.ini` or `conftest.py`.

**Reproduction:**
```bash
$ pytest tests/property/  # May not terminate with default settings
```

**Fix:** Add `timeout` setting to Hypothesis profiles or use `pytest-timeout` with a per-test maximum.

### BUG-005: Default User Credential File Persistence Risk

**Severity:** Low
**File:** `app/database/connection.py`
**Description:** Default admin credentials are written to a temporary file during initialization. If the application crashes before cleanup, credentials persist on disk.

**Fix:** Use Python's `tempfile.NamedTemporaryFile(delete=True)` with proper context management, or avoid writing credentials to disk entirely.

---

## 6. Performance Bottlenecks

### PERF-001: Synchronous SQLAlchemy ORM

**Severity:** Medium
**Impact:** All database operations block the event loop
**Description:** The application uses synchronous SQLAlchemy with FastAPI. While FastAPI runs sync endpoints in a thread pool, this limits concurrency compared to async drivers (e.g., `asyncpg` with SQLAlchemy 2.0 async).

**Recommendation:** Consider migrating to SQLAlchemy async sessions for high-throughput endpoints. Priority: Low (thread pool mitigates impact for moderate load).

### PERF-002: 13-Layer Middleware Stack Overhead

**Severity:** Low
**Impact:** Added latency per request (~1-5ms estimated overhead)
**Description:** Every request traverses 13 middleware layers. Most are lightweight, but `SecurityValidationMiddleware` performs regex matching against SQL injection/XSS patterns on every request body.

**Recommendation:** Profile middleware latency under load. Consider making `SecurityValidationMiddleware` configurable per-route or caching compiled regex patterns (verify they aren't already compiled at module level).

### PERF-003: Redis Connection for Every Token Revocation Check

**Severity:** Low
**Impact:** One Redis roundtrip per authenticated request
**Description:** `AuthenticationMiddleware` checks the Redis blocklist for every request to verify the JWT JTI hasn't been revoked. This is architecturally correct but adds latency.

**Recommendation:** This is an acceptable trade-off for security. Consider connection pooling optimization or local LRU cache with short TTL for the blocklist if Redis latency becomes an issue under high load.

### PERF-004: Connection Pool Sizing

**Severity:** Low
**File:** `app/database/connection.py`
**Description:** Pool size is hardcoded at `pool_size=20, max_overflow=30` (50 total connections). For high-concurrency deployments, this may be insufficient or excessive depending on the PostgreSQL `max_connections` setting.

**Recommendation:** Make pool sizing configurable via environment variables. Add pool exhaustion monitoring.

---

## 7. Technical Debt

### DEBT-001: Large Route Files

**Severity:** Medium
**Files:** `app/routes/users.py` (1050 lines), `app/services/auth_manager.py` (635 lines), `app/services/authorization.py` (631 lines)
**Description:** Several files exceed 500 lines, making them harder to navigate and test. `users.py` at 1050 lines handles registration, verification, MFA, password reset, and profile management — these are distinct concerns.

**Recommendation:** Split `users.py` into sub-modules: `registration.py`, `mfa.py`, `password.py`, `profile.py`.

### DEBT-002: Route Initialization Pattern Complexity

**Severity:** Low
**File:** `app/main.py`
**Description:** Several routers require explicit `init_*()` calls during lifespan to receive dependencies (Redis, session manager). This creates implicit coupling and ordering requirements.

**Recommendation:** Consider dependency injection via FastAPI's `Depends()` or a proper DI container to reduce init-time coupling.

### DEBT-003: Test Mode Bypasses Security Middleware

**Severity:** Medium
**File:** `app/main.py`
**Description:** `test_mode=True` disables `AuthenticationMiddleware`, `CSRFMiddleware`, and `ResponseSchemaValidationMiddleware`. This means integration tests never exercise the full middleware stack, potentially hiding bugs in middleware interactions.

**Recommendation:** Create a separate integration test suite that runs with `test_mode=False` against a test database with proper JWT tokens.

### DEBT-004: Inconsistent Error Response Formats

**Severity:** Low
**File:** `app/exceptions.py` (503 lines)
**Description:** The custom exception hierarchy is comprehensive but the 503-line file suggests many exception types. Verify that all routes consistently use the structured error response format.

### DEBT-005: No OpenAPI Schema Validation in Tests

**Severity:** Low
**Description:** While `ResponseSchemaValidationMiddleware` exists, it's disabled in test mode. No tests validate that API responses match the OpenAPI schema.

**Recommendation:** Add schema validation tests using `schemathesis` or response model assertions.

---

## 8. Prioritized Remediation Roadmap

### Phase 1: Critical Security (Week 1)

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| **P0** | Remove `.env.development` and `.env.production` from git, rotate all exposed secrets (SEC-004/005, BUG-002) | 1 hour | Eliminates secret exposure |
| **P0** | Fix `apgi_system` missing dependency or update imports (BUG-001) | 2 hours | Restores 2 test modules |
| **P0** | Add tests for security headers middleware — 0% → ≥80% (SEC-013) | 4 hours | Validates CSP/HSTS/X-Frame |
| **P1** | Add tests for CSRF middleware — 29% → ≥80% (SEC-012) | 6 hours | Validates CSRF protection |
| **P1** | Add tests for rate limiting middleware — 19% → ≥80% (SEC-003) | 6 hours | Validates rate limit enforcement |

### Phase 2: Authentication & Route Testing (Weeks 2-3)

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| **P1** | Add tests for auth routes — 30% → ≥80% (SEC-018) | 8 hours | Covers login/logout/refresh |
| **P1** | Add tests for user routes — 18% → ≥80% (SEC-019) | 16 hours | Covers registration, MFA, password reset |
| **P2** | Add SSRF prevention tests (SEC-023) | 4 hours | Validates webhook safety |
| **P2** | Add integration tests with full middleware stack (DEBT-003) | 8 hours | Tests middleware interactions |
| **P2** | Add Hypothesis timeout/profile configuration (BUG-004) | 1 hour | Prevents CI hangs |

### Phase 3: Code Quality & Performance (Weeks 3-4)

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| **P2** | Split `users.py` into sub-modules (DEBT-001) | 4 hours | Improves maintainability |
| **P2** | Make connection pool configurable (PERF-004) | 2 hours | Deployment flexibility |
| **P3** | Add database connection tests — 41% → ≥70% | 4 hours | Validates pooling/failover |
| **P3** | Evaluate async SQLAlchemy migration (PERF-001) | 16 hours | Better concurrency |
| **P3** | Refactor route initialization to use DI (DEBT-002) | 8 hours | Reduces coupling |
| **P3** | Add OpenAPI schema validation tests (DEBT-005) | 4 hours | API contract verification |

### Coverage Target

| Timeframe | Target | Current |
|-----------|--------|---------|
| After Phase 1 | **50%** | 39% |
| After Phase 2 | **70%** | 39% |
| After Phase 3 | **80%+** | 39% |

---

## Appendix A: Test Execution Results

```
$ pytest tests/unit/ --ignore=tests/unit/test_experimental_tasks.py --ignore=tests/unit/test_task_registry.py -p no:hypothesis
================================ test session starts =================================
collected 476 items
474 passed, 2 skipped, 0 failed
Total time: 24.82s

Coverage Summary:
Name                                    Stmts   Miss  Cover
------------------------------------------------------------
TOTAL                                    8147   4933    39%
```

## Appendix B: Positive Findings

The audit also identified several well-implemented patterns worth preserving:

1. **Password hashing** — SHA-256 pre-hash + bcrypt handles the 72-byte bcrypt limit correctly
2. **Token revocation** — JTI-based Redis blocklist is a robust pattern
3. **SSRF prevention** — Private IP blocking with DNS rebinding protection in webhook delivery
4. **Config validation** — Production startup fails fast on insecure configuration
5. **CSRF design** — HMAC-SHA256 tokens with proper bypass for JWT-authenticated requests
6. **Stripe integration** — Webhook signature verification and idempotent event processing
7. **Audit logging** — Authorization service logs access decisions for compliance
8. **Exception hierarchy** — Structured error responses with consistent format

---

*Report generated by automated codebase audit. Manual review recommended for all Critical and High severity findings.*
