# APGI API — Production Readiness Audit Report

**Project:** APGI System API (Allostatic Precision-Gated Ignition)
**Stack:** FastAPI · PostgreSQL · Redis · Celery · JWT · RBAC
**Audit Date:** 2026-03-12
**Auditor:** Claude Code (automated end-to-end review)
**Branch:** `claude/audit-production-readiness-Y32OB`

---

## Executive Summary

The APGI API is a well-structured FastAPI application with a thoughtful security architecture: layered middleware (auth, CSRF, rate-limiting, security-headers, schema validation), JWT + API-key dual authentication, RBAC permissions, audit logging, and SSRF-protected webhook delivery. The codebase demonstrates engineering maturity in most areas.

However, **three critical and five high-severity issues** block production deployment as-is. The most severe is a **plaintext-password-in-logs** vulnerability that could expose user credentials to anyone with log access. Additional blockers are **non-functional Stripe webhook handlers** (all payment lifecycle events are stubs) and a **missing authorization check** on the user-listing endpoint that enables full user enumeration by any authenticated user.

After remediation of the critical and high issues, the application is close to production quality.

---

## KPI Scores

| Dimension | Score | Status |
|---|---|---|
| Functional Completeness | 68 / 100 | 🔴 NEEDS WORK |
| Security Posture | 62 / 100 | 🔴 NEEDS WORK |
| Error Handling & Resilience | 82 / 100 | 🟡 ACCEPTABLE |
| Code Quality & Maintainability | 78 / 100 | 🟡 ACCEPTABLE |
| Observability & Ops-Readiness | 75 / 100 | 🟡 ACCEPTABLE |
| **Overall Health** | **73 / 100** | **🟡 NOT PRODUCTION-READY** |

> **Thresholds:** 🟢 ≥ 90 Production-ready · 🟡 70–89 Acceptable with fixes · 🔴 < 70 Blocked

---

## Bug Inventory

### CRITICAL (3)

---

#### BUG-001 — Plaintext Password Written to Logs

| Field | Detail |
|---|---|
| **Severity** | CRITICAL |
| **File** | `app/services/user_management.py:434, 476–478` |
| **Category** | Security — Credential Exposure |

**Description:** When SMTP is not configured, `_send_new_password_email()` logs the user's new plaintext password to the application log at INFO level (line 434) and again at WARNING level (line 476–478) on email delivery failure.

```python
# Line 434 — logs plaintext password
logger.info(f"Password reset for {email}: new password is {new_password}")

# Lines 476-478 — logs plaintext password on email failure
logger.warning(
    f"Password reset failed to send email, password for {email}: {new_password}"
)
```

**Expected:** Passwords must **never** appear in logs. Sensitive data must be redacted.
**Actual:** Any log aggregator (Splunk, CloudWatch, Loki, stdout) will capture the plaintext password.
**Reproduction:** Call `POST /v1/users/{user_id}/reset-password` with no SMTP server configured.

**Fix:**
```python
# Remove both log lines that include new_password.
# If SMTP is unavailable, log only that delivery failed:
logger.warning(f"Password reset email not delivered to {email}: SMTP not configured")
```

---

#### BUG-002 — Email Verification Token Written to Logs

| Field | Detail |
|---|---|
| **Severity** | CRITICAL |
| **File** | `app/services/user_management.py:495` |
| **Category** | Security — Token Exposure |

**Description:** When SMTP is not configured, `_send_verification_email()` logs the raw email-verification token. An attacker with log access can extract this token and activate any user account without owning the email address.

```python
# Line 495 — logs raw verification token
logger.info(f"Email verification for {email}: token is {verification_token}")
```

**Expected:** Tokens must not appear in logs. At most log that a delivery was attempted.
**Actual:** Token is exposed in logs.
**Reproduction:** Register a user with no SMTP configured; inspect application logs.

**Fix:** Remove the log line; simply log `"Email verification not sent: SMTP not configured"`.

---

#### BUG-003 — User-Listing Endpoint Missing Authorization Check

| Field | Detail |
|---|---|
| **Severity** | CRITICAL |
| **File** | `app/routes/users.py:225–288` |
| **Endpoint** | `GET /v1/users/` |
| **Category** | Security — Broken Access Control (OWASP A01) |

**Description:** The `list_users` endpoint handler declares **no permission dependency**. Every authenticated user (including `viewer` role) can retrieve a paginated list of all users including their email addresses, activation status, roles, and timestamps.

```python
# No require_permission() dependency — any authenticated caller succeeds
@router.get("/", response_model=UsersListResponse, ...)
async def list_users(
    page: int = 1, per_page: int = 10, active_only: bool = True,
    db: Session = Depends(get_db),   # ← only DB session, no auth check
):
```

Compare with neighboring endpoints that correctly guard access:
```python
@router.get("/stats", dependencies=[Depends(require_permission(Permission.USER_READ))], ...)
@router.get("/{user_id}", dependencies=[Depends(require_permission(Permission.USER_READ))], ...)
```

**Expected:** Only admins / users with `USER_READ` permission can list all users.
**Actual:** Any authenticated user can enumerate the full user directory.
**Reproduction:** Authenticate as `viewer`, then `GET /v1/users/`.

**Fix:** Add `dependencies=[Depends(require_permission(Permission.USER_ADMIN))]` to `list_users`.

---

### HIGH (5)

---

#### BUG-004 — All Stripe Webhook Event Handlers Are Stubs

| Field | Detail |
|---|---|
| **Severity** | HIGH |
| **File** | `app/routes/payments.py:165–202` |
| **Endpoint** | `POST /v1/payments/webhook` |
| **Category** | Functional Incompleteness |

**Description:** The Stripe webhook handler correctly validates the `Stripe-Signature` header and parses events, but all event-type branches contain only `# TODO:` comments with no business logic. Payment confirmations, failures, refunds, disputes, and subscription lifecycle events are silently discarded.

```python
if event_type == "payment_intent.succeeded":
    logger.info(f"Payment succeeded: {payment_intent['id']}")
    # TODO: Update order status, send confirmation email, etc.
elif event_type == "payment_intent.payment_failed":
    # TODO: Handle failed payment, notify user, etc.
elif event_type == "charge.dispute.created":
    # TODO: Handle dispute, notify admin, etc.
# ... (all branches are stubs)
```

**Expected:** Payments trigger order fulfillment; refunds update order status; disputes alert admins.
**Actual:** All payment events are acknowledged (HTTP 200) but no action is taken.

---

#### BUG-005 — Payment Intent Endpoint Missing Business-Level Auth Scope

| Field | Detail |
|---|---|
| **Severity** | HIGH |
| **File** | `app/routes/payments.py:50–88` |
| **Endpoint** | `POST /v1/payments/create-intent` |
| **Category** | Security — Insufficient Authorization |

**Description:** The `create_payment_intent` endpoint has no `require_permission` or role check. Any authenticated user (including `viewer`) can create payment intents for any product in the catalogue. While the authentication middleware ensures the caller is logged in, there is no business-level control limiting payment creation to subscribed or authorized users.

**Expected:** Only authorized users (e.g., those with an active subscription or explicit permission) should be able to initiate payments.
**Actual:** Any `viewer`-role user can POST to create a payment intent.

---

#### BUG-006 — Admin Password Reset Sends Plaintext Password in Email Body

| Field | Detail |
|---|---|
| **Severity** | HIGH |
| **File** | `app/services/user_management.py:376–417` |
| **Endpoint** | `POST /v1/users/{user_id}/reset-password` |
| **Category** | Security — Insecure Password Handling |

**Description:** The admin-triggered `reset_password()` method generates (or accepts) a new password and passes it directly to `_send_password_reset_email()`. The email body contains the literal new password:

```python
body = f"""...Your new password is: {new_password}..."""
```

Sending passwords in email bodies is a security anti-pattern: emails are stored in transit logs, email servers, and inboxes indefinitely.

**Expected:** Emit a time-limited reset link; never transmit the password itself.
**Actual:** Plaintext new password is emailed to the user.

---

#### BUG-007 — OTLP Trace Exporter Uses Hardcoded `insecure=True`

| Field | Detail |
|---|---|
| **Severity** | HIGH |
| **File** | `app/tracing.py:91` |
| **Category** | Security — Data-in-Transit Exposure |

**Description:** The OTLP exporter is configured with `insecure=True`, which disables TLS for trace data transmission. This is hard-coded and cannot be overridden via environment variable.

```python
otlp_exporter = OTLPSpanExporter(
    endpoint=otlp_endpoint,
    insecure=True,  # TODO: Make configurable for production
    headers=os.getenv("OTLP_HEADERS", ""),
)
```

Traces may contain request paths, user IDs, and timing information. Transmitting them unencrypted over a network is a compliance and confidentiality risk.

**Expected:** TLS-enabled by default; `insecure` configurable via `OTLP_INSECURE=true` env var.
**Actual:** All traces sent unencrypted regardless of environment.

---

#### BUG-008 — New User Stuck Inactive When SMTP Is Not Configured

| Field | Detail |
|---|---|
| **Severity** | HIGH |
| **File** | `app/services/user_management.py:60–85` |
| **Endpoint** | `POST /v1/users/register` |
| **Category** | Functional — Registration Flow Broken |

**Description:** `create_user()` saves the user to the database with `is_active=False` and then calls `_send_verification_email()`. When SMTP is not configured, `_send_verification_email` silently returns after a warning log. The user record is committed to the database but the verification token is never delivered, leaving the account permanently inactive with no way for the user to activate it.

```python
user = User(is_active=False, ...)  # Committed to DB
self.db.commit()
# SMTP not configured → token silently discarded, account stuck
self._send_verification_email(user.email, verification_token)
```

**Expected:** Graceful degradation: either auto-activate users when SMTP is not configured, or return an error so the caller knows registration succeeded but email was not sent.
**Actual:** User is registered but permanently locked out unless an admin manually activates the account.

---

### MEDIUM (7)

---

#### BUG-009 — Default User Created with Non-UUID `user_id`

| Field | Detail |
|---|---|
| **Severity** | MEDIUM |
| **File** | `app/database/connection.py:141–143` |
| **Category** | Data Model Inconsistency |

**Description:** `create_default_user()` sets `user_id=secure_username` where `secure_username` is `"default_<16hexchars>"` (24 chars). The `user_id` column is semantically a UUID (`String(36)`, generated via `uuid.uuid4()`). This bypasses the UUID generation and inserts a non-UUID primary key, which is inconsistent with all other user records and breaks any UUID-based filtering or validation.

**Fix:** Use `user_id=str(uuid.uuid4())` separately and store `secure_username` only in the `username` field.

---

#### BUG-010 — Shadow Import of `Session` in sessions.py

| Field | Detail |
|---|---|
| **Severity** | MEDIUM |
| **File** | `app/routes/sessions.py:17` |
| **Category** | Code Quality — Import Bug |

**Description:** `Session` is imported twice on the same line:

```python
from app.database.models import Session as SessionModel, Task, Session
```

The trailing `Session` (without alias) immediately shadows the `SessionModel` alias, making the alias useless. Any code that tries to reference `SessionModel` will use the correct alias, but the bare `Session` name at the end pollutes the namespace unnecessarily.

---

#### BUG-011 — Duplicate `StructuredLogger` Import in `main.py`

| Field | Detail |
|---|---|
| **Severity** | MEDIUM |
| **File** | `app/main.py:44, 75` |
| **Category** | Code Quality |

**Description:** `StructuredLogger` is imported twice:

```python
# Line 44
from app.middleware.logging import RequestLoggingMiddleware, StructuredLogger, configure_structured_logging
# ...
# Line 75 — duplicate
from app.middleware.logging import StructuredLogger
```

---

#### BUG-012 — Duplicate Values in Stripe Key Validation Lists

| Field | Detail |
|---|---|
| **Severity** | MEDIUM |
| **File** | `app/config.py:410–420` |
| **Category** | Code Quality — Validator Bug |

**Description:** The Stripe production key validation lists each contain the same value twice:

```python
if self.stripe_secret_key in ["sk_test_placeholder", "sk_test_placeholder"] or ...:
if self.stripe_publishable_key in ["pk_test_placeholder", "pk_test_placeholder"] or ...:
```

The duplicate entries are harmless but indicate copy-paste errors and reduce code clarity.

---

#### BUG-013 — Session State Endpoints Miss Ownership Validation

| Field | Detail |
|---|---|
| **Severity** | MEDIUM |
| **File** | `app/routes/state.py` |
| **Endpoints** | `GET /v1/sessions/{session_id}/state` and related |
| **Category** | Security — IDOR (Insecure Direct Object Reference) |

**Description:** The state access endpoints (`/state`, `/state/ignition-history`, `/state/prediction-errors`, etc.) require `SESSION_READ` permission but do **not** validate that the requesting user owns the session. Any user with `researcher` or `admin` role can read the complete state of any session by guessing or iterating session IDs.

Compare with the sessions router which has an explicit `validate_session_ownership()` call that enforces ownership unless `is_admin=True`.

**Reproduction:** Authenticate as user A, create a session, note its `session_id`. Authenticate as user B (researcher role), call `GET /v1/sessions/{session_id}/state`.

---

#### BUG-014 — Double DB Query in `list_users` for Pagination Count

| Field | Detail |
|---|---|
| **Severity** | MEDIUM |
| **File** | `app/routes/users.py:265–272` |
| **Category** | Performance |

**Description:** `list_users` calls `user_service.get_user_stats()` twice — once for `total_users` and again for `active_users` — triggering two separate aggregate queries:

```python
total_users = user_service.get_user_stats()["total_users"]   # Query 1
if active_only:
    total_count = user_service.get_user_stats()["active_users"]  # Query 2 (redundant)
```

Both values are available from a single call. Under load this doubles unnecessary DB round-trips.

---

#### BUG-015 — `stripe` Package Version Is Unpinned

| Field | Detail |
|---|---|
| **Severity** | MEDIUM |
| **File** | `requirements.txt:29` |
| **Category** | Dependency Management |

**Description:** `stripe` is listed without a version constraint:

```
stripe
```

Stripe regularly releases breaking API changes. An unpinned dependency risks silent breakage on the next `pip install`.

**Fix:** Pin to a specific version, e.g. `stripe>=7.0.0,<8.0.0`.

---

### LOW (4)

---

#### BUG-016 — `/v1/users/reset-password` Endpoint Not Guarded Against Brute-Force

| Field | Detail |
|---|---|
| **Severity** | LOW |
| **File** | `app/routes/users.py:480–522` |
| **Category** | Security — Rate Limiting Gap |

**Description:** `POST /v1/users/reset-password` is a public endpoint (no auth required) that accepts an email address. The rate limiter's `auth:attempt` bucket (10 req/min) applies to `/v1/auth*` paths only; this endpoint maps to the `global` bucket (60 req/min), providing weaker protection against bulk email enumeration attempts.

---

#### BUG-017 — Missing Alembic Head Validation in CI/CD

| Field | Detail |
|---|---|
| **Severity** | LOW |
| **File** | `app/alembic/versions/` |
| **Category** | Ops-Readiness |

**Description:** Migration filenames mix sequential numeric IDs (`001_`, `002_`, `003_`) with hash-based IDs (`45ba6d327ae0_`, `50e7513df3b0_`). There is no CI step that runs `alembic check` to verify the ORM models and migration chain are in sync. Schema drift is likely to surface silently in production.

---

#### BUG-018 — Hardcoded Mock PaymentIntent Secret in Staging

| Field | Detail |
|---|---|
| **Severity** | LOW |
| **File** | `app/routes/payments.py:86–88` |
| **Category** | Testing / Staging Correctness |

**Description:** Non-production environments return a hardcoded fake secret:

```python
return PaymentIntentCreateResponse(
    clientSecret="pi_3MtwBwLkdIwHu7ix28a3tqPa_secret_a1b2c3d4e5f6g7h8i9j0"
)
```

This gives staging environments a false success path, meaning payment flows always appear to succeed without hitting Stripe Test Mode. Staging should use Stripe Test keys to exercise the actual Stripe integration.

---

#### BUG-019 — `PATCH` Method Missing for Partial User Updates

| Field | Detail |
|---|---|
| **Severity** | LOW |
| **File** | `app/routes/users.py:405` |
| **Category** | API Design |

**Description:** Only `PUT /v1/users/{user_id}` is available for user updates. The endpoint signature accepts all fields as optional, making it behave semantically like `PATCH`. REST conventions recommend `PATCH` for partial updates and `PUT` for full replacement. The current route may confuse clients that follow REST strictly.

---

## Missing Features / Incomplete Implementations

| # | Feature | Location | Status | Milestone Impact |
|---|---|---|---|---|
| MF-001 | Stripe `payment_intent.succeeded` handler | `payments.py:169` | Stub (TODO) | P0 — Revenue |
| MF-002 | Stripe `payment_intent.payment_failed` handler | `payments.py:175` | Stub (TODO) | P0 — Revenue |
| MF-003 | Stripe `charge.dispute.created/closed` handler | `payments.py:181,187` | Stub (TODO) | P0 — Compliance |
| MF-004 | Stripe `charge.refunded` handler | `payments.py:196` | Stub (TODO) | P0 — Revenue |
| MF-005 | Stripe `customer.subscription.*` handler | `payments.py:202` | Stub (TODO) | P0 — Subscriptions |
| MF-006 | Subscription lifecycle management | (no module) | Missing entirely | P0 — Business logic |
| MF-007 | OTLP `insecure` flag configurable | `tracing.py:91` | Hardcoded | P1 — Observability |
| MF-008 | Email verification graceful fallback | `user_management.py:76` | Broken flow | P1 — Onboarding |
| MF-009 | Cursor-based pagination (list endpoints) | All list routes | Offset-only | P2 — Scalability |
| MF-010 | Alembic head check in CI | `.github/` | Not present | P2 — Ops Safety |

---

## Dimension Assessments

### 1. Functional Completeness — 68/100

The core APGI session lifecycle (create → run → pause → stop → export) appears complete. Authentication, MFA, RBAC, API keys, templates, tasks, webhooks, and metrics are implemented. The critical gap is the **entire payment/subscription module**, which accepts Stripe events but implements none of the business logic handlers (MF-001 through MF-005). Without these handlers the product cannot process payments or manage subscriptions.

### 2. Security Posture — 62/100

Positive: layered middleware, JWT revocation via Redis, account lockout after 5 failures, SSRF-protected webhooks, HMAC-signed cursors, bcrypt+SHA256 password hashing, security headers, CSRF protection, CORS configuration, audit logging.

Detractors: BUG-001/002 (plaintext credentials in logs), BUG-003 (user enumeration), BUG-006 (passwords emailed), BUG-007 (unencrypted traces), BUG-013 (IDOR on session state).

### 3. Error Handling & Resilience — 82/100

Global exception handlers normalize all errors (APIError, ValidationError, HTTPException, catch-all 500). Middleware degrades gracefully when Redis is unavailable. Database session rollback is handled consistently. Rate limiter falls back gracefully without Redis. The main gap: `_send_verification_email()` swallows errors silently (BUG-008) and several TODO webhook handlers never surface failures.

### 4. Code Quality & Maintainability — 78/100

Clean separation of concerns (routes → services → models), consistent use of dependency injection, property-based and unit tests with Hypothesis, type annotations throughout. Issues: duplicate imports (BUG-010/011), non-UUID default user ID (BUG-009), unpinned stripe dependency (BUG-015).

### 5. Observability & Ops-Readiness — 75/100

Structured JSON logging, Prometheus metrics endpoint, OpenTelemetry support, alerting middleware, health/readiness/liveness probes, audit logging to database. Gap: OTLP forced insecure (BUG-007), no `alembic check` CI step (BUG-017), docs disabled in production (correct behavior but internal teams may need a solution like a VPN-gated docs endpoint).

---

## Prioritized Remediation Recommendations

### Immediate (Before Any Production Deployment)

| # | Action | File(s) | Effort |
|---|---|---|---|
| R-01 | Remove plaintext password/token log lines | `user_management.py:434,476–478,495` | < 1h |
| R-02 | Add `require_permission(Permission.USER_ADMIN)` to `list_users` | `routes/users.py:225` | < 30m |
| R-03 | Replace password-in-email with token-link flow | `user_management.py:376–417` | 2–4h |
| R-04 | Implement Stripe webhook event handlers | `routes/payments.py:165–202` | 1–2 days |
| R-05 | Handle SMTP-unavailable gracefully in registration | `user_management.py:60–85` | 2h |

### Short-Term (Sprint 1)

| # | Action | File(s) | Effort |
|---|---|---|---|
| R-06 | Make OTLP `insecure` configurable via env var | `tracing.py:91` | 30m |
| R-07 | Add session ownership validation to state routes | `routes/state.py` | 2h |
| R-08 | Fix default user UUID generation | `connection.py:141–143` | 30m |
| R-09 | Add `require_permission` to payment-intent endpoint | `routes/payments.py:50` | 30m |
| R-10 | Pin `stripe` package to a specific version range | `requirements.txt:29` | 15m |

### Medium-Term (Sprint 2)

| # | Action | File(s) | Effort |
|---|---|---|---|
| R-11 | Clean up duplicate imports (`sessions.py`, `main.py`) | listed files | 30m |
| R-12 | Consolidate double `get_user_stats()` call in `list_users` | `routes/users.py:265` | 30m |
| R-13 | Add `alembic check` step to CI pipeline | `.github/workflows/` | 1h |
| R-14 | Replace hardcoded mock secret with Stripe Test Mode | `routes/payments.py:86` | 1h |
| R-15 | Implement subscription lifecycle management module | new service | 3–5 days |
| R-16 | Add `PATCH /v1/users/{user_id}` for partial updates | `routes/users.py` | 1h |
| R-17 | Apply stricter rate limit to `/v1/users/reset-password` | `middleware/rate_limiting.py` | 1h |

---

## Appendix — Audit Coverage

| Area | Files Reviewed | Verdict |
|---|---|---|
| Application entry / factory | `main.py`, `config.py` | Reviewed |
| Authentication | `middleware/authentication.py`, `services/auth_manager.py` | Reviewed |
| Authorization | `services/authorization.py` | Reviewed |
| CSRF protection | `middleware/csrf.py` | Reviewed |
| Rate limiting | `middleware/rate_limiting.py`, `services/rate_limiter.py` | Reviewed |
| Security headers | `middleware/security_headers.py` | Reviewed |
| CORS | `middleware/cors_config.py` | Reviewed |
| Routes | `auth`, `users`, `sessions`, `state`, `tasks`, `export`, `templates`, `payments`, `api_keys`, `webhooks`, `admin`, `health`, `version` | All reviewed |
| Services | `auth_manager`, `authorization`, `user_management`, `session_manager`, `webhook_manager`, `cache_service`, `rate_limiter` | Reviewed |
| Database models | `database/models.py`, `database/connection.py` | Reviewed |
| Alembic migrations | `alembic/versions/` (all 14 files) | Reviewed |
| Celery tasks | `tasks/experimental_tasks.py`, `tasks/task_registry.py` | Reviewed |
| Configuration | `config.py`, `.env.development`, `.env.production` | Reviewed |
| Error handling | `exception_handlers.py`, `exceptions.py` | Reviewed |
| Observability | `tracing.py`, `middleware/logging.py`, `middleware/metrics.py`, `middleware/alerting.py` | Reviewed |
| Tests | `tests/unit/` (18 files), `tests/integration/`, `tests/property/` | Structure reviewed |
| Dependencies | `requirements.txt`, `requirements-dev.txt`, `requirements-prod.txt` | Reviewed |
