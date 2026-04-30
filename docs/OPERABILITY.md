# APGI API Operability Contract

This document defines the runtime contract, startup sequence, and dependency matrix for the APGI REST API.

## Startup Sequence

1. **Environment Detection**: Load `.env` and validate basic settings (ENVIRONMENT, LOG_LEVEL).
2. **Dependency Check**:
    - **Hard Dependencies**: System fails if missing (FastAPI, SQLAlchemy, etc.).
    - **Soft Dependencies**: System logs warning and enters *Degraded Mode* (Redis, Celery, Prometheus).
3. **Config Validation**:
    - Production check for placeholder secrets (Stripe, JWT, Webhooks).
    - Entropy validation for signing keys.
4. **Service Initialization**:
    - Database connection pool setup.
    - Redis connection and cache service.
    - Middleware stack assembly.
5. **Lifespan Events**:
    - Database schema verification.
    - Default user synchronization.

## Dependency Matrix

| Component | Type | Impact of Failure | Mitigation |
| :--- | :--- | :--- | :--- |
| **PostgreSQL** | Hard | Application Crash | Fail-fast at startup |
| **Redis** | Soft | No Rate Limiting/Caching | Degraded Mode (allow requests without limits) |
| **Celery** | Soft | Background Tasks Fail | Log error, queue tasks in-memory if possible or fail task submission |
| **Stripe** | Soft | Payment Processing Fails | Return 503 for payment endpoints |

## Fail-Open vs Fail-Closed Decisions

- **Authentication**: **Fail-Closed**. Any failure in JWT verification results in 401.
- **Rate Limiting**: **Fail-Open**. If Redis is down, we allow requests to prevent a total outage, but log high-severity alerts.
- **Schema Validation**: **Configurable**. Default is Fail-Open (log error) unless `SCHEMA_VALIDATION_FAIL_ON_ERROR` is true.

## Backward Compatibility Guarantees

1. **Versioning**: API versions are prefixed (e.g., `/v1`).
2. **Deprecation Lifecycle**:
    - Minimum 3-month warning via `Deprecation` header.
    - `Sunset` header specifies end-of-life date.
    - Deprecated endpoints are documented in `/v1/version`.
