# APGI System API — Production Readiness Audit Report

**Audit Date:** 2026-03-13
**Auditor:** Claude Code (claude-sonnet-4-6)
**Repository Branch:** `claude/audit-production-readiness-sQ1x5`
**Codebase Revision:** `6430505`
**Scope:** End-to-end production readiness audit of the APGI REST API (FastAPI + PostgreSQL + Redis + Celery)

---

## Executive Summary

The APGI System API is a well-structured FastAPI application with a thoughtful middleware stack, comprehensive RBAC, JWT authentication with MFA/backup-codes, and solid security practices in several areas (bcrypt+SHA-256 prehash, HMAC webhook signatures, SSRF prevention, CSRF protection). However, the codebase contains **two critical runtime-breaking bugs** that make core API endpoints completely non-functional, along with several high-severity security and correctness defects that must be resolved before production deployment.

The most urgent finding is that **`GET /v1/sessions` always returns a runtime error** due to a return statement that emits a Python type-annotation object instead of data. A second critical finding is that **password reset and Stripe webhook endpoints are gated behind authentication**, making them inaccessible to the clients that need them (unauthenticated users and Stripe respectively). Together with a missing `aiohttp` dependency that causes `ImportError` on first webhook delivery, these issues represent a trifecta of show-stoppers that must be resolved before any production deployment.

Overall application health is estimated at approximately **54/100** due to the severity and breadth of defects found.

---

## KPI Scores

| Dimension | Score | Status | Notes |
|---|---|---|---|
| **Functional Completeness** | 45/100 | 🔴 CRITICAL | Core endpoints broken; payments stubs only |
| **Security** | 62/100 | 🟡 HIGH | Auth bypass paths; API key integration broken |
| **Error Handling & Resilience** | 55/100 | 🟡 HIGH | Webhook retry bypassed; DB errors on login path |
| **Implementation Quality** | 68/100 | 🟡 MEDIUM | Duplicate code; inconsistent patterns |
| **Performance & Scalability** | 72/100 | 🟢 ACCEPTABLE | Double JWT verification; sync DB in executor |
| **Overall Health** | **54/100** | 🔴 NOT PRODUCTION-READY | — |

> **Scoring thresholds:** 🔴 Critical (<65) · 🟡 High (65–79) · 🟢 Acceptable (80–94) · ✅ Excellent (95+)

---

## Bug Inventory

### CRITICAL Severity

---

#### BUG-001 · `GET /v1/sessions` Always Fails — Wrong Return Value in `list_sessions`

| Field | Detail |
|---|---|
| **File** | `app/routes/sessions.py:284` |
| **Component** | Sessions Router |
| **Severity** | 🔴 CRITICAL |
| **Status** | Open |

**Description:**
The `list_sessions` handler returns the Python `Union` type-annotation object itself instead of the `SessionListResponse` instance. FastAPI will attempt to serialize a Python `type` object and raise an internal server error on every call.

**Reproduction steps:**
1. Authenticate and obtain a valid JWT token.
2. `GET /v1/sessions` (any pagination params).
3. Observe 500 Internal Server Error.

**Code (current — broken):**
```python
# sessions.py:284
return Union[SessionCreateResponse, SessionStatusResponse, SessionActionResponse, SessionResponse]  # type: ignore[return-value]
```

**Expected code:**
```python
return SessionListResponse(sessions=sessions, pagination=pagination)
```

**Impact:** 100% failure rate for session listing. All authenticated clients are affected.

---

#### BUG-002 · Password Reset & Stripe Webhook Endpoints Behind Authentication Wall

| Field | Detail |
|---|---|
| **File** | `app/middleware/authentication.py:55-69` |
| **Component** | AuthenticationMiddleware — PUBLIC_PATHS |
| **Severity** | 🔴 CRITICAL |
| **Status** | Open |

**Description:**
Three endpoints that must be reachable without a valid access token are not listed in `PUBLIC_PATHS`, so the middleware returns HTTP 401 before the route handlers execute:

1. `POST /v1/users/reset-password` — A user who has forgotten their password cannot be logged in to call this endpoint.
2. `POST /v1/users/reset-password/confirm` — Same issue; token confirmation requires being logged in.
3. `POST /v1/payments/webhook` — Stripe calls this from its own servers with no JWT; it will always receive 401 and acknowledge errors.

**Reproduction steps (password reset):**
1. Attempt `POST /v1/users/reset-password` with no `Authorization` header.
2. Observe `401 Authentication required`.

**Reproduction steps (Stripe webhook):**
1. Send a `POST /v1/payments/webhook` request with `Stripe-Signature` header but no JWT.
2. Observe `401 Authentication required`.

**Expected:** These endpoints must be added to `PUBLIC_PATHS` (and/or implement their own signature-based validation, as is already done in the webhook handler).

**Fix:**
```python
PUBLIC_PATHS = {
    # … existing entries …
    "/v1/users/reset-password",
    "/v1/users/reset-password/confirm",
    "/v1/payments/webhook",
}
```

---

### HIGH Severity

---

#### BUG-003 · `aiohttp` Missing From `requirements.txt` — Webhook Delivery Fails With `ImportError`

| Field | Detail |
|---|---|
| **File** | `requirements.txt`, `app/services/webhook_manager.py:14` |
| **Component** | Webhook Manager |
| **Severity** | 🔴 HIGH |
| **Status** | Open |

**Description:**
`webhook_manager.py` imports `aiohttp` at the top of the module. `aiohttp` is not listed in `requirements.txt` or `requirements-prod.txt`. Any attempt to deliver a webhook will raise `ImportError: No module named 'aiohttp'` at runtime, silently preventing all webhook deliveries.

**Reproduction:**
```bash
pip install -r requirements.txt
python -c "from app.services.webhook_manager import WebhookManager"
# ImportError: No module named 'aiohttp'
```

**Fix:** Add `aiohttp>=3.9.0` to `requirements.txt`.

---

#### BUG-004 · Admin Password Reset Stores Raw Token; Confirmation Expects Hash

| Field | Detail |
|---|---|
| **File** | `app/services/user_management.py:411-412`, `276-300` |
| **Component** | UserManagementService |
| **Severity** | 🔴 HIGH |
| **Status** | Open |

**Description:**
There are two code paths that initiate a password reset:
1. `request_password_reset()` (public flow) — stores `hashlib.sha256(reset_token).hexdigest()` in the DB.
2. `reset_password()` (admin-initiated) — stores the **raw token** via `setattr(user, "password_reset_token", reset_token)`.

`confirm_password_reset()` always hashes the submitted token before querying the DB. This means tokens generated by the admin flow will never match, making admin-initiated password resets permanently broken.

**Code (broken):**
```python
# user_management.py:411 — reset_password()
setattr(user, "password_reset_token", reset_token)  # stores raw token
```

**Code (confirm_password_reset expects hash):**
```python
# user_management.py:290
token_hash = hashlib.sha256(token.encode()).hexdigest()
user = db.query(User).filter(User.password_reset_token == token_hash)...
```

**Fix:** Change `reset_password()` to store `hashlib.sha256(reset_token.encode()).hexdigest()` instead of `reset_token`.

---

#### BUG-005 · Webhook Retry Logic Bypassed — All Failures Immediately Dead-Lettered

| Field | Detail |
|---|---|
| **File** | `app/services/webhook_manager.py:292-316` |
| **Component** | WebhookManager.deliver_webhook |
| **Severity** | 🔴 HIGH |
| **Status** | Open |

**Description:**
The `WebhookManager` defines a retry schedule (`[5, 30, 300, 1800, 3600]` seconds) but the actual delivery implementation never uses it. Both a non-2xx HTTP response and any exception during delivery immediately set `status = "dead_letter"`, bypassing all retry logic.

**Code (broken path for non-2xx response):**
```python
# webhook_manager.py:292
delivery.status = "dead_letter"  # should be "retry"
```

**Code (broken path for exceptions):**
```python
# webhook_manager.py:315
delivery.status = "dead_letter"  # should be "retry" with next_retry_at set
```

**Fix:** On non-2xx response or transient exception, set `status = "retry"`, calculate `next_retry_at` from `retry_delays[delivery.attempts]`, and only move to `"dead_letter"` once `attempts >= retry_count`.

---

#### BUG-006 · API Key Authentication Broken for All Protected Endpoints

| Field | Detail |
|---|---|
| **File** | `app/services/authorization.py:340-344`, `app/middleware/authentication.py:180-196` |
| **Component** | Authorization dependency / Authentication middleware |
| **Severity** | 🔴 HIGH |
| **Status** | Open |

**Description:**
The `AuthenticationMiddleware` correctly validates API keys from `X-API-Key` header and sets `request.state.user`. However, all protected route handlers use `Depends(get_current_user)` or `Depends(require_permission(...))`, which internally use `HTTPBearer()` — a FastAPI security scheme that **only reads the `Authorization: Bearer` header**. An API key request that provides `X-API-Key` but no `Authorization` header will fail at the FastAPI dependency injection layer with HTTP 403 (`HTTPBearer` raises `HTTPException(403)`), regardless of the successfully-authenticated middleware state.

**Impact:** API keys are effectively non-functional for any endpoint using `Depends(get_current_user)` or `Depends(require_permission(...))`. This covers all protected API endpoints.

**Fix:** Replace `HTTPBearer()` in `get_current_user` with a custom dependency that first reads `request.state.user` (set by middleware) before falling back to `HTTPBearer` extraction. This avoids double JWT verification and correctly handles API key users.

---

#### BUG-007 · HTTPS Webhook Delivery Breaks SSL — IP Pinning + Hostname Mismatch

| Field | Detail |
|---|---|
| **File** | `app/services/webhook_manager.py:257-276` |
| **Component** | WebhookManager.deliver_webhook |
| **Severity** | 🔴 HIGH |
| **Status** | Open |

**Description:**
To prevent DNS rebinding attacks, the webhook manager resolves the hostname at record-creation time and stores the resolved IP, then replaces the hostname with the raw IP in the URL before making the HTTP request:

```python
pinned_url = urlunparse((scheme, f"{delivery.resolved_ip}:{port}", ...))
```

For HTTPS webhooks, the code creates a default SSL context and sends the request to the IP-based URL. TLS certificate hostname verification fails because the certificate is issued for the original domain name, not the raw IP address. `aiohttp` (once installed) will raise `aiohttp.ClientConnectorCertificateError` on every HTTPS webhook delivery.

**Fix:** Use the `ssl` connector with the `hostname` override (`ssl.create_default_context()` and SNI hostname set to the original hostname) or use `aiohttp`'s `headers` option with the original `Host` header while connecting to the pinned IP.

---

#### BUG-008 · Payment Intent Creation Restricted to `SYSTEM_ADMIN` — Regular Users Blocked

| Field | Detail |
|---|---|
| **File** | `app/routes/payments.py:57` |
| **Component** | Payments Router |
| **Severity** | 🟡 HIGH |
| **Status** | Open |

**Description:**
The `POST /v1/payments/create-intent` endpoint uses `Depends(require_permission(Permission.SYSTEM_ADMIN))`. Only `ADMIN` role users have `SYSTEM_ADMIN` permission. Regular users (`RESEARCHER`, `VIEWER`) cannot initiate a payment flow, making the payment feature inaccessible to the intended audience.

**Fix:** Change the permission requirement to something that regular authenticated users possess (e.g., `SESSION_READ`, which all roles have, or a new `PAYMENT_CREATE` permission), depending on business requirements.

---

#### BUG-009 · Payment Webhook Handlers Are Stubs — No Business Logic Implemented

| Field | Detail |
|---|---|
| **File** | `app/routes/payments.py:217-367` |
| **Component** | Payments Router — webhook handlers |
| **Severity** | 🟡 HIGH |
| **Status** | Open |

**Description:**
All five payment event handlers (`_handle_payment_succeeded`, `_handle_payment_failed`, `_handle_dispute_created`, `_handle_dispute_closed`, `_handle_refund`, `_handle_subscription_event`) contain only `# TODO` comments with no implemented business logic. Payment events are acknowledged to Stripe but not acted upon — no database updates, no notifications, no subscription management.

**Impact:** Payments appear to succeed/fail from Stripe's perspective, but the application state is never updated. Users could pay without receiving their subscription benefits. Disputes and refunds are silently ignored.

**Fix:** Implement the business logic for each payment event handler before going live with payment processing.

---

#### BUG-010 · Login Endpoint DB Commit for Audit Log Blocks Token Issuance

| Field | Detail |
|---|---|
| **File** | `app/routes/auth.py:95-112` |
| **Component** | Authentication Router |
| **Severity** | 🟡 HIGH |
| **Status** | Open |

**Description:**
The login route creates an `AuditLog` entry and calls `db.commit()` before creating and returning JWT tokens. If the DB commit fails (e.g., transient network error, DB constraint violation on the audit table), the entire login request raises an unhandled exception. The user has authenticated successfully but receives a 500 error instead of tokens.

**Fix:** Move audit logging to a fire-and-forget background task or make it a best-effort operation that does not block token issuance:
```python
tokens = auth_manager.create_tokens_for_user(user, body.remember_me or False)
# Audit log after tokens are generated — best-effort
try:
    db.add(audit_entry); db.commit()
except Exception as e:
    logger.error("Audit log commit failed: %s", e)
    db.rollback()
return TokenResponse(**tokens)
```

---

### MEDIUM Severity

---

#### BUG-011 · Rate Limit Error Response Shows Incorrect Global Limit

| Field | Detail |
|---|---|
| **File** | `app/middleware/rate_limiting.py:263` |
| **Component** | RateLimitingMiddleware |
| **Severity** | 🟡 MEDIUM |
| **Status** | Open |

**Description:**
When rate limiting is triggered, the error response body reports `"limit": settings.rate_limit_per_minute` (the global default, 60 req/min). However, the actual limit that was violated is endpoint-specific (e.g., `auth:attempt` is 10/min). Clients receive misleading retry guidance.

**Fix:** Replace `settings.rate_limit_per_minute` with the per-endpoint `limit` variable in scope.

---

#### BUG-012 · Session Description Read From `config` Dict Instead of `description` Column

| Field | Detail |
|---|---|
| **File** | `app/routes/sessions.py:271, 405` |
| **Component** | Sessions Router |
| **Severity** | 🟡 MEDIUM |
| **Status** | Open |

**Description:**
`SessionResponse` objects are constructed with `description=session.config.get("description")`, pulling the description from the JSON config blob rather than the dedicated `description` column on the `Session` model. Any description set directly on the `description` column is silently ignored.

**Fix:** Use `description=sim_session.description` (direct column access).

---

#### BUG-013 · MFA Backup Code Verification Uses Non-Constant-Time Comparison

| Field | Detail |
|---|---|
| **File** | `app/routes/users.py:919` |
| **Component** | User Management — MFA |
| **Severity** | 🟡 MEDIUM |
| **Status** | Open |

**Description:**
Backup code verification uses `if hashed_code in user.mfa_backup_codes`, which is a standard Python `__contains__` call and performs non-constant-time comparison. An attacker who can measure response times could potentially infer information about stored backup codes.

**Fix:** Use `hmac.compare_digest` for each comparison or otherwise ensure constant-time behavior. Since the codes are hashed with SHA-256, the risk is low but not zero for high-precision timing attacks.

---

#### BUG-014 · Double Permission Dependency in `list_webhook_deliveries`

| Field | Detail |
|---|---|
| **File** | `app/routes/webhooks.py:44-53` |
| **Component** | Webhooks Router |
| **Severity** | 🟡 MEDIUM |
| **Status** | Open |

**Description:**
`list_webhook_deliveries` declares the same permission check twice: once in `dependencies=[Depends(require_permission(Permission.DATA_READ))]` and again in the function signature `current_user: TokenPayload = Depends(require_permission(Permission.DATA_READ))`. This causes the permission check (including DB audit logging) to run twice per request, adding latency.

**Fix:** Remove one of the two `require_permission(Permission.DATA_READ)` references. Use the function-signature form when the resolved user is needed in the handler body.

---

#### BUG-015 · Inconsistent Permission Levels on Webhook Delivery Endpoints

| Field | Detail |
|---|---|
| **File** | `app/routes/webhooks.py:44-148` |
| **Component** | Webhooks Router |
| **Severity** | 🟡 MEDIUM |
| **Status** | Open |

**Description:**
`GET /v1/webhooks/deliveries` requires `DATA_READ` (available to all roles), but `GET /v1/webhooks/deliveries/{id}` requires `SYSTEM_ADMIN` (admin only). A `RESEARCHER` user can list all webhook deliveries but cannot view details of any individual delivery — an inconsistent and likely unintentional permission model.

---

#### BUG-016 · Duplicate SMTP Email Methods — Stale `_send_new_password_email` Unreachable

| Field | Detail |
|---|---|
| **File** | `app/services/user_management.py:427-480` |
| **Component** | UserManagementService |
| **Severity** | 🟡 MEDIUM |
| **Status** | Open |

**Description:**
`UserManagementService` has three nearly identical SMTP email methods (`_send_password_reset_email`, `_send_password_reset_link_email`, `_send_new_password_email`) and a fourth for verification emails. `_send_new_password_email` is never called and contains misleading content (it says "use the password reset link" but takes a `new_password` argument). These duplicates increase maintenance risk.

---

### LOW Severity

---

#### BUG-017 · `.env.production` Committed With Placeholder Values

| Field | Detail |
|---|---|
| **File** | `.env.production` |
| **Component** | Configuration |
| **Severity** | 🟢 LOW |
| **Status** | Open |

**Description:**
`.env.production` is committed to version control with placeholder values (e.g., `DATABASE_URL=postgresql://CHANGE_ME:CHANGE_ME@CHANGE_ME:5432/apgi_api_prod`). While `.gitignore` prevents `.env` from being committed, the `.env.production` file is tracked. If a developer accidentaly fills in production values, they would be committed.

**Fix:** Rename to `.env.production.template` (matching the existing `.env.production.template` convention) or add `.env.production` to `.gitignore`.

---

#### BUG-018 · `cancel_task` in `tasks.py` Calls `get_task_status` With None Check That Can Never Be True

| Field | Detail |
|---|---|
| **File** | `app/routes/tasks.py:393-397` |
| **Component** | Tasks Router |
| **Severity** | 🟢 LOW |
| **Status** | Open |

**Description:**
`cancel_task` calls `executor.get_task_status(task_id, ...)` and checks `if task_status is None`. However `get_task_status` either returns a dict or raises `ValueError` — it never returns `None`. The `None` check is dead code and the real not-found path goes to the `except ValueError` branch below.

---

#### BUG-019 · `stripe` Package Version Pin Too Narrow — May Block Security Updates

| Field | Detail |
|---|---|
| **File** | `requirements.txt:29` |
| **Component** | Dependencies |
| **Severity** | 🟢 LOW |
| **Status** | Open |

**Description:**
`stripe>=7.0.0,<8.0.0` prevents picking up patch releases in `8.x` that may contain security fixes. Stripe's API client is frequently updated. Consider using `stripe>=7.0.0` or updating to the latest major.

---

#### BUG-020 · `created_at` Deserialization In Idempotency Cache Uses Naive `fromisoformat`

| Field | Detail |
|---|---|
| **File** | `app/routes/sessions.py:329-332` |
| **Component** | Sessions Router — Idempotency |
| **Severity** | 🟢 LOW |
| **Status** | Open |

**Description:**
When replaying a cached idempotency response, `created_at` is deserialized with `datetime.fromisoformat(cached_response["created_at"][:-1])` — stripping the trailing `Z` (UTC marker). This strips timezone info, creating a timezone-naive `datetime` object. If response models serialize with timezone-aware datetimes, comparison or serialization of the replayed response may produce inconsistent output.

---

## Missing Features Log

| ID | Feature | Scope | Status | Effort |
|---|---|---|---|---|
| MF-001 | Stripe payment webhook business logic (fulfillment, subscription management, refunds, disputes) | `payments.py` | Not implemented (TODO stubs only) | High |
| MF-002 | Webhook retry scheduling with exponential backoff | `webhook_manager.py` | Partially implemented (schema exists, logic bypassed) | Medium |
| MF-003 | API key integration with FastAPI `Depends(get_current_user)` | `authorization.py` | Architecture gap | Medium |
| MF-004 | Password complexity validation on registration/reset | `user_management.py`, schemas | No minimum length or complexity check | Low |
| MF-005 | Rate limiting on password reset endpoint | `rate_limiting.py` | Path not mapped in `_get_endpoint_identifier` | Low |
| MF-006 | Docs/OpenAPI exposed in production | `main.py:227-229` | Disabled, but no explicit docs policy/OAuth for prod | Low |
| MF-007 | Soft-delete filtering for sessions in state endpoint | `routes/state.py` | `is_deleted` flag not consistently respected | Low |

---

## Actionable Recommendations

### P0 — Deploy Blockers (Fix Before Any Production Traffic)

| # | Action | File(s) | Effort |
|---|---|---|---|
| 1 | **Fix `list_sessions` return statement** (BUG-001) | `sessions.py:284` | 30 min |
| 2 | **Add password reset + Stripe webhook to PUBLIC_PATHS** (BUG-002) | `authentication.py:55-69` | 15 min |
| 3 | **Add `aiohttp` to `requirements.txt`** (BUG-003) | `requirements.txt` | 5 min |
| 4 | **Fix `reset_password()` to hash the token before storage** (BUG-004) | `user_management.py:411` | 30 min |

### P1 — High Priority (Fix Within First Sprint)

| # | Action | File(s) | Effort |
|---|---|---|---|
| 5 | **Implement webhook retry scheduling** (BUG-005) | `webhook_manager.py:292-316` | 2 hrs |
| 6 | **Fix API key `get_current_user` integration** (BUG-006) | `authorization.py`, `authentication.py` | 2 hrs |
| 7 | **Fix HTTPS webhook SSL hostname verification** (BUG-007) | `webhook_manager.py:257-276` | 2 hrs |
| 8 | **Loosen payment intent permission to non-admin** (BUG-008) | `payments.py:57` | 15 min |
| 9 | **Implement payment webhook event handlers** (BUG-009) | `payments.py:217-367` | 2–4 days |
| 10 | **Move audit logging past token creation in login** (BUG-010) | `auth.py:95-112` | 30 min |

### P2 — Medium Priority (Fix Within Second Sprint)

| # | Action | File(s) | Effort |
|---|---|---|---|
| 11 | **Fix rate limit error message to use actual limit** (BUG-011) | `rate_limiting.py:263` | 15 min |
| 12 | **Use `description` column in `SessionResponse`** (BUG-012) | `sessions.py:271,405` | 15 min |
| 13 | **Remove duplicate permission check in webhook list** (BUG-014) | `webhooks.py:44-53` | 15 min |
| 14 | **Standardize webhook delivery permissions** (BUG-015) | `webhooks.py` | 30 min |
| 15 | **Add password complexity validation** (MF-004) | schemas, `user_management.py` | 1 hr |
| 16 | **Map `/v1/users/reset-password` to strict rate limit** (MF-005) | `rate_limiting.py` | 30 min |

### P3 — Low Priority / Maintenance (Backlog)

| # | Action | File(s) | Effort |
|---|---|---|---|
| 17 | **Remove `.env.production` from git tracking** (BUG-017) | `.gitignore` | 15 min |
| 18 | **Consolidate 4 near-identical SMTP methods** (BUG-016) | `user_management.py` | 1 hr |
| 19 | **Remove dead `_send_new_password_email` method** (BUG-016) | `user_management.py:427` | 15 min |
| 20 | **Fix idempotency cache `created_at` timezone** (BUG-020) | `sessions.py:329-332` | 15 min |
| 21 | **Use constant-time comparison in MFA backup codes** (BUG-013) | `users.py:919` | 30 min |
| 22 | **Update stripe version constraint** (BUG-019) | `requirements.txt` | 15 min |

---

## Detailed Findings by Area

### Authentication & Authorization

- **Strengths:** JWT with JTI-based revocation; bcrypt+SHA-256 prehash for passwords; TOTP MFA with backup codes; account lockout after 5 failed attempts; token rotation on refresh; `hmac.compare_digest` for timing-safe comparisons.
- **Weaknesses:** API key auth works at the middleware layer but is entirely broken at the route layer (BUG-006); password reset requires authentication (BUG-002); `CURSOR_SIGNING_KEY` is validated but never checked to differ from `JWT_SECRET_KEY`.

### Webhook System

- **Strengths:** SSRF prevention via IP resolution and private-network blocklist; HMAC-SHA256 payload signatures; dead-letter queue concept; delivery tracking in DB.
- **Weaknesses:** `aiohttp` missing (BUG-003); retry logic completely bypassed (BUG-005); HTTPS webhooks will fail on SSL hostname mismatch (BUG-007); `deliver_webhook()` is called in a `process_pending_deliveries` tight loop without any concurrency limit.

### Payment System

- **Strengths:** Stripe signature verification; structured event routing; error isolation (non-raise on handler errors).
- **Weaknesses:** All handlers are TODO stubs (BUG-009); webhook endpoint not accessible to Stripe (BUG-002); payment creation too restrictive (BUG-008); no `STRIPE_WEBHOOK_SECRET` key in `settings` class (handler reads `getattr(settings, "stripe_webhook_secret", None)` which will always be `None`).

### Session Management

- **Strengths:** Ownership validation helper; idempotency key support; pagination; soft delete.
- **Weaknesses:** `list_sessions` broken (BUG-001); description field inconsistency (BUG-012).

### Configuration & Environment

- **Strengths:** Production-fail-fast validation for secrets; insecure-default detection; URL format validation.
- **Weaknesses:** `settings` class has no `stripe_webhook_secret` attribute despite the payment webhook handler referencing it; `.env.production` in version control (BUG-017).

### Middleware Stack

- **Strengths:** Comprehensive stack (size limit → gzip → metrics → logging → versioning → schema validation → CSRF → auth → deprecation → rate limiting → security headers → CORS); all security headers present including HSTS; CSP correctly set.
- **Weaknesses:** CSRF skips all JWT-authenticated requests (correct) but this means the security burden falls entirely on JWT; rate limiting middleware correctly uses per-endpoint limits but error response incorrectly reports the global limit (BUG-011).

---

## Appendix: File-Level Quick Reference

| File | Critical Bugs | High Bugs | Medium Bugs |
|---|---|---|---|
| `app/routes/sessions.py` | BUG-001 | — | BUG-012, BUG-020 |
| `app/middleware/authentication.py` | BUG-002 | BUG-006 | — |
| `requirements.txt` | BUG-003 | — | — |
| `app/services/user_management.py` | BUG-004 | — | BUG-016 |
| `app/services/webhook_manager.py` | — | BUG-005, BUG-007 | — |
| `app/services/authorization.py` | — | BUG-006 | — |
| `app/routes/payments.py` | BUG-002 | BUG-008, BUG-009 | — |
| `app/routes/auth.py` | — | BUG-010 | — |
| `app/middleware/rate_limiting.py` | — | — | BUG-011 |
| `app/routes/webhooks.py` | — | — | BUG-014, BUG-015 |
| `app/routes/users.py` | — | — | BUG-013 |
| `.env.production` | — | — | BUG-017 |
| `app/routes/tasks.py` | — | — | BUG-018 (low) |
