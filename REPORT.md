# APGI System API — End-to-End Production Audit Report

**Version:** 3.0 — Full Sweep
**Date:** 2026-03-15
**Auditor:** Claude Code (Sonnet 4.6)
**Branch audited:** `claude/app-audit-production-mSL7y`
**Scope:** Full codebase — routes, services, middleware, schemas, migrations, tests, configuration

---

## Executive Summary

The APGI System API is a FastAPI-based REST backend for consciousness-modelling research.
The codebase has a **well-structured architecture**, strong middleware layering, and many
security-aware decisions (bcrypt + SHA-256 pre-hashing, JWT revocation via Redis, per-endpoint
rate limits, RBAC, audit logging). However, the audit uncovered **two CRITICAL showstopper
bugs** that break core user flows, **one HIGH-severity migration defect** that prevents
database upgrades, and a collection of medium/low issues that collectively pull the
production-readiness score well below the target of 100.

**All issues are fixable without architectural redesign.**

---

## KPI Scores

| Dimension | Score | Status |
|---|:---:|:---:|
| Functional Completeness | 58 / 100 | 🔴 Critical |
| API Contract Quality | 72 / 100 | 🟡 Needs Work |
| Security Posture | 74 / 100 | 🟡 Needs Work |
| Error Handling & Resilience | 80 / 100 | 🟡 Needs Work |
| Code Quality & Maintainability | 76 / 100 | 🟡 Needs Work |
| **Overall** | **72 / 100** | 🟡 **Not Production-Ready** |

> 🔴 < 65 · 🟡 65–84 · 🟢 ≥ 85

---

## Bug Inventory

### CRITICAL Severity

---

#### BUG-C01 — Token Rotation Breaks Client Sessions Permanently

**File:** `app/services/auth_manager.py:566`, `app/models/schemas.py:560`, `app/routes/auth.py:147`
**Summary:** `refresh_access_token()` rotates the refresh token and revokes **all** of a
user's old tokens, but `TokenRefreshResponse` does not include a `refresh_token` field.
Clients never receive the new refresh token. On their next refresh attempt they present the
now-revoked old token and receive 401. **Every user is permanently logged out after the first
token refresh.**

**Reproduction:**
1. `POST /v1/auth/login` → save `access_token` + `refresh_token`
2. `POST /v1/auth/refresh` with the refresh token → receive only `access_token` (no `refresh_token`)
3. Wait for access token to expire
4. `POST /v1/auth/refresh` again → **401 Unauthorized** (old token revoked, new one never delivered)

**Expected:** `POST /v1/auth/refresh` response includes both `access_token` and the new
(rotated) `refresh_token`.

**Root Cause:**
```python
# auth_manager.py:586 — returns new refresh token in dict
return {
    "access_token": access_token,
    "refresh_token": new_refresh_token,   # ← present in dict
    ...
}
# routes/auth.py:169 — passes dict to schema
return TokenRefreshResponse(**tokens)

# schemas.py:560 — schema has NO refresh_token field; field silently dropped
class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    # refresh_token MISSING
```

**Fix:**
```python
# schemas.py — add field to TokenRefreshResponse
class TokenRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str = Field(..., description="New JWT refresh token (rotation)")
    token_type: str
    expires_in: int
    refresh_expires_in: Optional[int] = None
```

**Effort:** 15 min · **Team:** Backend

---

#### BUG-C02 — Broken Regex Causes `re.error` on User Registration

**File:** `app/middleware/security_validation.py:240`
**Summary:** The username format validator uses an unterminated character class
(`r'^[a-zA-Z0-9_@.+$'`) which raises `re.error: unterminated character set` at runtime.
The `_validate_request` method catches all exceptions and returns `{"is_valid": False}`,
so **every registration request is rejected with a security validation error**.

**Note:** `SecurityValidationMiddleware` is not mounted in `main.py` (see BUG-M05), so this
specific crash does not currently affect production. However, the middleware is exported and
could be (re-)mounted, instantly breaking all registrations.

**Reproduction (isolated):**
```python
import re
re.match(r'^[a-zA-Z0-9_@.+$', 'alice')
# re.error: unterminated character set at position 1
```

**Fix:**
```python
# security_validation.py:240
if not re.match(r'^[a-zA-Z0-9_@.+$\-]{1,100}$', username):
```

**Effort:** 5 min · **Team:** Backend

---

### HIGH Severity

---

#### BUG-H01 — Alembic Migration Chain Has Two Heads (Fork)

**Files:** `app/alembic/versions/add_retry_config_to_webhook_deliveries.py`,
`app/alembic/versions/add_password_reset_tokens.py`
**Summary:** Both migrations declare `down_revision = 'add_unique_constraint_user_name_session_templates'`,
creating a fork. Alembic detects two heads (`45ba6d327ae0` and `add_mfa_backup_codes`) and
**`alembic upgrade head` fails** unless both heads are explicitly specified.

**Reproduction:**
```bash
alembic heads
# add_mfa_backup_codes (head)
# 45ba6d327ae0 (head)

alembic upgrade head
# ERROR: Multiple head revisions are present...
```

**Expected:** Single linear chain, single head.

**Fix:** Merge the two heads into one merge migration:
```bash
alembic merge -m "merge_heads" add_mfa_backup_codes 45ba6d327ae0
```

**Effort:** 30 min · **Team:** Backend / DevOps

---

#### BUG-H02 — Stripe Webhook Secret Not Defined in Settings

**Files:** `app/routes/payments.py:134`, `app/config.py`
**Summary:** `payments.py` reads `getattr(settings, 'stripe_webhook_secret', None)` but
`Settings` never defines `stripe_webhook_secret`. The attribute always resolves to `None`,
causing the webhook endpoint to return HTTP 500 for every Stripe webhook event in all
environments.

**Reproduction:**
1. Configure Stripe to send webhooks to `POST /v1/payments/webhook`
2. Stripe sends any event → `endpoint_secret = None` → HTTP 500

**Expected:** Stripe signature is verified and events are processed.

**Fix:**
```python
# config.py — add inside __init__
self.stripe_webhook_secret: Optional[str] = os.getenv("STRIPE_WEBHOOK_SECRET")

# Add to production validation in __post_init__
if is_production and not self.stripe_webhook_secret:
    errors.append("STRIPE_WEBHOOK_SECRET must be set in production.")
```

**Effort:** 20 min · **Team:** Backend

---

#### BUG-H03 — Token Rotation Silently Logs Out All User Devices

**File:** `app/services/auth_manager.py:566`
**Summary:** During token refresh, the code revokes **all** non-revoked refresh tokens for
the user, not just the one being refreshed. A user with three active sessions (e.g., mobile,
desktop, API client) who refreshes on one device is silently logged out on all others.

**Root Cause:**
```python
# auth_manager.py — revokes ALL, not just the presented token
for old_token in db_tokens:    # db_tokens = ALL non-revoked for this user
    old_token.revoked = True
```

**Fix:** Only revoke the specific token that was presented:
```python
# Revoke only the matched token; keep others active
db_token.revoked = True
```

**Effort:** 15 min · **Team:** Backend

---

#### BUG-H04 — `SecurityValidationMiddleware` Implemented But Never Mounted

**Files:** `app/middleware/security_validation.py`, `app/main.py`
**Summary:** `SecurityValidationMiddleware` is a ~350-line security validator class that
checks for SQL injection, XSS, and malicious characters. It is exported from
`app/middleware/__init__.py` but is **never added to the middleware stack** in `create_app()`.
All validation logic is completely bypassed at runtime.

**Fix:** Add to `create_app()` in `main.py` (before AuthenticationMiddleware):
```python
from app.middleware.security_validation import SecurityValidationMiddleware

app.add_middleware(SecurityValidationMiddleware, enabled=True)
```

**Note:** Before mounting, first fix BUG-C02 (broken regex) and BUG-M01 (false positives).

**Effort:** 30 min · **Team:** Backend

---

#### BUG-H05 — Stripe Webhook Handlers are Log-Only Stubs

**File:** `app/routes/payments.py:196–340`
**Summary:** All five Stripe event handlers (`_handle_payment_succeeded`,
`_handle_payment_failed`, `_handle_dispute_created`, `_handle_dispute_closed`,
`_handle_refund`, `_handle_subscription_event`) **only write log entries** and perform no
database updates. Successful payments do not grant access, failed payments do not block
service, and cancelled subscriptions are not downgraded. The payment system is non-functional.

**Expected:** Handlers update a subscription/order model and adjust user entitlements.

**Fix:** Implement an `Order` / `Subscription` model and update it within each handler, or
use a job queue to process events asynchronously.

**Effort:** 3–5 days · **Team:** Backend

---

### MEDIUM Severity

---

#### BUG-M01 — SQL Injection Regex Produces Massive False Positives

**File:** `app/middleware/security_validation.py:72–82`
**Summary:** The SQL injection patterns use simple word-boundary matching that flags common
English words and email addresses:
- Pattern `\b(OR|AND|NOT|LIKE|IN|BETWEEN|EXISTS)\b` matches usernames like **"Anderson"**,
  **"Norton"**, email addresses like **"insert@domain.com"**.
- Pattern with empty alternation `(UNION|SELECT|...|EXEC|)` always matches every string due
  to the trailing `|)`.

**Fix:** Use stricter context-aware detection or a dedicated library (e.g., `sqlparse`).
At minimum remove the trailing `|)` and wrap patterns in `\b...\b` with anchors.

**Effort:** 2 hours · **Team:** Backend

---

#### BUG-M02 — CORS Wildcard Headers Conflict with Credentials

**File:** `app/config.py:134`
**Summary:** The default `cors_allow_headers = ["*"]` combined with
`cors_allow_credentials = True` violates the CORS specification. Browsers refuse credentialed
cross-origin requests when the server returns `Access-Control-Allow-Headers: *`. This will
silently break frontend authentication in production for any frontend not on the same origin.

**Fix:**
```python
# config.py
self.cors_allow_headers = [
    "Authorization", "Content-Type", "X-CSRF-Token",
    "X-API-Key", "Idempotency-Key"
]
```

**Effort:** 15 min · **Team:** Backend

---

#### BUG-M03 — Refresh Token Rotation Scalability (O(n) bcrypt)

**File:** `app/services/auth_manager.py:516–534`
**Summary:** During token refresh, all non-revoked tokens for the user are fetched and each
is bcrypt-verified in a loop. With N active tokens, this is O(N) bcrypt operations. A user
with 50 tokens requires 50 bcrypt verifications (each ~100ms), resulting in ~5-second
responses and a viable DoS vector.

**Fix:** Store a SHA-256 hash of the token alongside the bcrypt hash for O(1) lookup, using
bcrypt only for final confirmation:
```python
# Fast lookup: compare sha256 first
import hashlib
sha = hashlib.sha256(refresh_token.encode()).hexdigest()
db_token = db.query(RefreshToken).filter(
    RefreshToken.user_id == payload.user_id,
    RefreshToken.revoked.is_(False),
    RefreshToken.token_sha256 == sha,   # new column
).first()
```

**Effort:** 4 hours + migration · **Team:** Backend

---

#### BUG-M04 — Inactive User Account Returns Misleading Error on Login

**File:** `app/services/auth_manager.py:451`
**Summary:** When a user with SMTP disabled registers (auto-activated) vs SMTP enabled
(manual verification), the error message for inactive accounts exposes implementation detail:
`"Account is not activated. Please verify your email first."` — but for SMTP-disabled
environments, no email was ever sent. The message is incorrect and confusing.

**Fix:** Check whether a verification email was sent before giving email-specific advice, or
use a generic "Account pending activation" message.

**Effort:** 30 min · **Team:** Backend

---

#### BUG-M05 — API Documentation Disabled in Non-Development Environments

**File:** `app/main.py:167–170`
**Summary:**
```python
docs_url="/docs" if settings.environment == "development" else None,
redoc_url="/redoc" if settings.environment == "development" else None,
openapi_url="/openapi.json" if settings.environment == "development" else None,
```
No alternative documentation strategy exists for staging or production. API consumers and QA
teams have no discoverable reference.

**Fix:** Either enable docs behind an authentication check on staging, or generate a static
OpenAPI spec in CI and publish to an internal docs host.

**Effort:** 2 hours · **Team:** DevOps / Backend

---

#### BUG-M06 — Password Reset Has Duplicate Email-Sending Functions

**File:** `app/services/user_management.py:359–530`
**Summary:** Two nearly identical functions exist: `_send_password_reset_email` (line 359)
and `_send_password_reset_link_email` (line 462). The `reset_password` method calls the
second; the first is dead code. Also, `reset_password` (line 417) uses
`hashlib.sha256(reset_token.encode()).hexdigest()` to hash the token, while the verify path
in `app/routes/users.py` compares the raw token directly against `user.password_reset_token`
without hashing. **Password reset confirmation will always fail.**

**Reproduction:**
1. `POST /v1/users/reset-password` (admin reset) — stores `sha256(token)` in DB
2. Email contains plain `reset_token`
3. `POST /v1/users/reset-password/confirm` — compares `token == user.password_reset_token`
   → `sha256(token) != token` → always fails

**Fix:** Either hash in both places or store/compare the raw token (not both).

**Effort:** 1 hour · **Team:** Backend

---

#### BUG-M07 — `config_path` Allows Absolute Paths and Partial Traversal

**File:** `app/models/schemas.py:85`
**Summary:** The `config_path` validator blocks `..` but allows absolute paths like
`/etc/passwords.yaml` and partial traversal like `/proc/self/environ.yaml`. All paths are
validated for `..` as a substring, but `%2e%2e`, URL-encoded dots passed at schema level,
or OS-level symlinks are not considered.

**Fix:** Resolve the path against a known safe base directory whitelist at the service level,
not just in the schema validator.

**Effort:** 2 hours · **Team:** Backend

---

#### BUG-M08 — SMTP Connections Not Using TLS Certificate Verification

**File:** `app/services/user_management.py:401, 468, 537`
**Summary:** All three email-sending functions use:
```python
server = smtplib.SMTP(settings.smtp_server, settings.smtp_port)
server.starttls()
```
`starttls()` without `context=ssl.create_default_context()` uses an insecure SSL context
that does **not verify the server certificate**. Susceptible to MITM attacks on the mail
delivery path.

**Fix:**
```python
import ssl
context = ssl.create_default_context()
server.starttls(context=context)
```

**Effort:** 30 min · **Team:** Backend

---

#### BUG-M09 — `SecurityValidationMiddleware` Blocks Tabs, Newlines in All Inputs

**File:** `app/middleware/security_validation.py:95–110`
**Summary:** `MALICIOUS_CHARS` includes `\t` (tab), `\n` (newline), `\r` (carriage return).
The middleware would reject multi-line description fields, JSON payloads with formatted
strings, and any text area input. This is overly broad for a REST API.

**Fix:** Remove common whitespace from `MALICIOUS_CHARS`; retain only true control characters
(0x00–0x08, 0x0B–0x0C, 0x0E–0x1F).

**Effort:** 30 min · **Team:** Backend

---

#### BUG-M10 — `TokenPayload` Duplicate Class Definition

**File:** `app/services/auth_manager.py:20`, `app/services/authorization.py` (imported)
**Summary:** `TokenPayload` is defined in `auth_manager.py` but also imported and re-exported
from `authorization.py`. `routes/auth.py` imports `TokenPayload` from `authorization`, while
the middleware imports from `auth_manager`. There are two in-memory instances of the class
definition. Isinstance checks between them will fail silently in some code paths.

**Fix:** Canonicalize `TokenPayload` to a single source (e.g., `app/schemas/token.py`) and
import from there everywhere.

**Effort:** 1 hour · **Team:** Backend

---

### LOW Severity

---

#### BUG-L01 — `/v1/users/stats` Requires `USER_READ` (Not `USER_ADMIN`)

**File:** `app/routes/users.py` — `get_user_stats` endpoint
**Summary:** Any user with `USER_READ` permission can retrieve aggregate statistics including
total user count, active users, and session counts. This aggregated data should require
`USER_ADMIN` to limit information exposure.

**Effort:** 5 min · **Team:** Backend

---

#### BUG-L02 — `UserCreateResponse` Leaks Internal Role Assignment

**File:** `app/routes/users.py:register_user`
**Summary:** The registration response includes `roles: ["viewer"]`, exposing the internal
role model to new registrants. This is low-risk but is an unintended information disclosure.

**Effort:** 10 min · **Team:** Backend

---

#### BUG-L03 — `ARRAY(Text)` Columns Incompatible with SQLite Test DB

**File:** `app/database/models.py:52, 132, 170, 267`
**Summary:** `User.roles`, `Session.tags`, `SessionTemplate.tags`, and `APIKey.permissions`
use `ARRAY(Text)` which is PostgreSQL-specific. Unit tests use SQLite in-memory which does
not support `ARRAY`. Tests that insert into these columns will silently fail or produce
incorrect results.

**Effort:** 2 hours (use JSON column type with adapter for SQLite) · **Team:** Backend

---

#### BUG-L04 — Rate Limit Headers Show Incorrect Limit in 429 Response Body

**File:** `app/middleware/rate_limiting.py:187`
**Summary:** The 429 response body logs `"limit": limit` (endpoint-specific, e.g., 10 for
auth) but the log line says `limit=settings.rate_limit_per_minute` (global, default 60).
Inconsistency misleads clients debugging rate limit issues.

**Effort:** 5 min · **Team:** Backend

---

#### BUG-L05 — `DeprecationMiddleware` Configured with Empty Dict

**File:** `app/main.py:223`
**Summary:** `configure_deprecated_endpoints({})` is called after `version.configure_deprecated_endpoints({})` is also called. The endpoint is called twice with no deprecated endpoints configured, which is harmless but indicates incomplete versioning strategy.

**Effort:** 5 min · **Team:** Backend

---

#### BUG-L06 — `base_url` Defaults to `https://localhost:8000` for Password Reset Links

**File:** `app/config.py:36`
**Summary:** Password reset emails use `settings.base_url` which defaults to
`https://localhost:8000`. Without explicit configuration, reset links are always unusable in
deployed environments.

**Fix:** Add `BASE_URL` to required production environment variable documentation and
validation.

**Effort:** 15 min · **Team:** DevOps / Backend

---

#### BUG-L07 — `/v1/auth/logout` Accepts Any Refresh Token for Any User

**File:** `app/routes/auth.py:193`
**Summary:** The logout endpoint revokes a refresh token, but it does not verify the provided
refresh token belongs to the currently authenticated user before revoking it. A user with a
valid access token could attempt to revoke another user's refresh token by guessing its value
(highly unlikely in practice due to token entropy, but the authorization check is missing).

**Effort:** 30 min · **Team:** Backend

---

## Missing Features Log

| # | Feature | Status | Severity | Milestone |
|---|---|---|---|---|
| MF-01 | **Subscription / entitlement model** — No `Order`, `Subscription`, or `Entitlement` DB model. Payment events are logged but have no effect on user access. | ❌ Not implemented | Critical | Pre-launch |
| MF-02 | **Token refresh returns new refresh token** — Clients cannot maintain long-lived sessions because rotated token is never returned. | ❌ Broken (BUG-C01) | Critical | Pre-launch |
| MF-03 | **Stripe webhook secret configuration** — `STRIPE_WEBHOOK_SECRET` env var not defined in Settings. | ❌ Missing | Critical | Pre-launch |
| MF-04 | **Alembic single-head chain** — Cannot run `alembic upgrade head`; two branches diverge. | ❌ Broken (BUG-H01) | High | Pre-launch |
| MF-05 | **Email delivery for password reset confirm** — Reset token hashing mismatch means confirmation always fails. | ❌ Broken (BUG-M06) | High | Pre-launch |
| MF-06 | **Security input validation middleware mounted** — Implemented but not active. | ❌ Not mounted | High | Pre-launch |
| MF-07 | **API documentation for staging/production** — Docs disabled with no alternative. | ❌ Missing | Medium | Pre-launch |
| MF-08 | **Multi-device session support** — Refresh revokes all tokens; single-device only. | ⚠️ Partial | Medium | Post-launch |
| MF-09 | **Webhook retry background worker** — `WebhookDelivery` model tracks retries, but no Celery task or cron actually retries failed deliveries. | ❌ Missing | High | Pre-launch |
| MF-10 | **Admin user seeding script** — `create_demo_user.py` and `seeding_service.py` exist but no idempotent seed is part of the Docker startup flow. | ⚠️ Partial | Low | Pre-launch |
| MF-11 | **Email verification in staging/CI** — SMTP not configured → users auto-activated, creating a silent security gap in staging. | ⚠️ Partial | Low | Pre-launch |
| MF-12 | **OpenTelemetry Jaeger exporter** — `thrift` wheel fails to build (confirmed in test run). OTLP gRPC exporter should be used instead. | ⚠️ Degraded | Low | Post-launch |

---

## Actionable Recommendations

### Sprint 1 — Showstoppers (do before any production deployment)

| # | Action | File(s) | Effort | Owner |
|---|---|---|---|---|
| R01 | Fix `TokenRefreshResponse` — add `refresh_token` field | `schemas.py`, `auth.py` | 15 min | Backend |
| R02 | Fix broken regex in `security_validation.py` | `security_validation.py:240` | 5 min | Backend |
| R03 | Merge Alembic fork into single head | `alembic/versions/` | 30 min | Backend |
| R04 | Add `stripe_webhook_secret` to `Settings` | `config.py` | 20 min | Backend |
| R05 | Fix password reset token hashing mismatch | `user_management.py`, `users.py` | 1 hr | Backend |
| R06 | Implement webhook retry Celery task | `app/tasks/` | 1 day | Backend |

### Sprint 2 — Security Hardening

| # | Action | File(s) | Effort | Owner |
|---|---|---|---|---|
| R07 | Mount `SecurityValidationMiddleware` (after fixing BUG-C02, BUG-M01) | `main.py` | 30 min | Backend |
| R08 | Fix SQL injection false positives in validator | `security_validation.py:72–82` | 2 hrs | Backend |
| R09 | Restrict CORS `allow_headers` from wildcard to explicit list | `config.py:134` | 15 min | Backend |
| R10 | Fix SMTP TLS certificate verification | `user_management.py:401,468,537` | 30 min | Backend |
| R11 | Change refresh rotation to revoke only presented token | `auth_manager.py:566` | 15 min | Backend |
| R12 | Move `USER_READ` to `USER_ADMIN` on stats endpoint | `routes/users.py` | 5 min | Backend |
| R13 | Add `BASE_URL` to production env var checklist | `config.py`, `.env.example` | 15 min | DevOps |

### Sprint 3 — Product Completeness

| # | Action | Effort | Owner |
|---|---|---|---|
| R14 | Implement `Subscription` model + Stripe event handlers that update it | 3–5 days | Backend |
| R15 | Enable Swagger UI for staging behind auth header check | 2 hrs | Backend / DevOps |
| R16 | Optimise refresh token lookup (add `token_sha256` column) | 4 hrs + migration | Backend |
| R17 | Fix `ARRAY` vs JSON column portability for test SQLite | 2 hrs | Backend |
| R18 | Replace Jaeger/thrift exporter with OTLP gRPC in requirements | 30 min | DevOps |
| R19 | Canonicalize `TokenPayload` to single module | 1 hr | Backend |

---

## Detailed Technical Notes

### Authentication Architecture Assessment

The JWT + refresh-token design is sound. Key strengths:
- Tokens include a `jti` (JWT ID) for revocation via Redis blocklist — good.
- Access tokens expire in 30 minutes — good.
- Bcrypt + SHA-256 pre-hashing handles passwords > 72 bytes — good.
- Account lockout after 5 failed attempts — good.
- API key HMAC prefix for fast DB lookup — good.

Weaknesses already captured in bug inventory (C01, H03, M03).

### Middleware Stack Order Assessment

The declared order is correct in principle but note that Starlette adds middleware in
**reverse** order (last `add_middleware` call runs outermost). Verify the effective order by
tracing through `create_app`. Current code has `SecurityHeadersMiddleware` added after
`RateLimitingMiddleware`, which means security headers run **inside** rate limiting — that is
correct (security headers should be on every response, including 429s). However, `CORSMiddleware`
(added by `configure_cors`) runs innermost of all, which means preflight `OPTIONS` requests pass
through the full authentication stack — this is typically undesirable.

**Fix:** Move CORS configuration before the `add_middleware` calls, or ensure OPTIONS is in
`PUBLIC_PATHS`.

### Database Schema Assessment

- All models use `String(36)` UUIDs rather than native `UUID` type — acceptable for
  cross-DB portability, but PostgreSQL native UUIDs would be more efficient.
- `ARRAY(Text)` for roles, tags, and permissions is PostgreSQL-only. Consider `JSON` for
  portability or add a DB constraint that enforces PostgreSQL-only deployment.
- `RefreshToken` has a `token_hash` index declared as `unique=True` in the initial migration
  (line 210: `ix_refresh_tokens_token_hash`), but this is **not declared in the model class**.
  This discrepancy could cause migration drift.
- The `AuditLog` model uses `backref="audit_logs"` on `User` which conflicts with anything
  else trying to use that backref name. Use an explicit `relationship` instead.

### Test Coverage Assessment

The test suite is extensive (~80 test files). However:
- Unit tests use SQLite which does not support `ARRAY` columns used in production models.
  Tests that insert `roles`, `tags`, or `permissions` may produce incorrect results silently.
- Integration tests require live PostgreSQL and Redis, with no mock/test doubles documented.
- No tests exist for the Stripe payment flow.
- No tests for the token refresh response schema (the C01 bug would be caught immediately
  by a single test case).

### Performance Considerations

- Synchronous database operations in `AuthenticationMiddleware` and `RateLimitingMiddleware`
  run in thread pool executors — this is correct for Starlette async middleware.
- The O(N) bcrypt loop in `refresh_access_token` is the primary performance risk (BUG-M03).
- Connection pool settings (20 + 30 overflow) are reasonable for medium load.
- Redis is used for sessions, rate limiting, token revocation, idempotency keys, and cache —
  Redis failure brings down the entire application (Redis is required in lifespan startup).
  Consider graceful degradation for non-critical features.

---

## Appendix A — Environment Variable Checklist

Variables required before production deployment that are currently undocumented or missing:

```bash
# Required — missing from Settings validation
STRIPE_WEBHOOK_SECRET=whsec_...    # NEW — for Stripe webhook signature verification
BASE_URL=https://api.yourdomain.com  # Add to production required list

# Required — already validated in production
JWT_SECRET_KEY=<32+ char random>
CURSOR_SIGNING_KEY=<32+ char random>
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
CORS_ORIGINS=https://app.yourdomain.com

# Recommended
SMTP_SERVER=smtp.yourdomain.com
SMTP_USERNAME=noreply@yourdomain.com
SMTP_PASSWORD=<password>
WEBHOOK_SECRET_KEY=<32+ char random>
```

---

## Appendix B — Severity Classification

| Severity | Definition |
|---|---|
| **Critical** | Breaks a core user flow (login, registration, payment); causes data loss or security bypass |
| **High** | Prevents deployment or causes a major feature to be non-functional |
| **Medium** | Degrades security posture, user experience, or correctness in non-obvious ways |
| **Low** | Minor quality, consistency, or information-disclosure issues |

---

*Report generated by automated static analysis + manual code review of the full APGI API codebase.*
