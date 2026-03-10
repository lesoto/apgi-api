# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

APGI System API — a FastAPI REST API for Allostatic Precision-Gated Ignition consciousness modeling. Stack: FastAPI + PostgreSQL + Redis + Celery, with JWT authentication and RBAC.

## Development Commands

### Start development environment (Docker)

```bash
./scripts/start.sh
# Starts PostgreSQL, Redis, API, and Celery worker via Docker Compose
# API: http://localhost:8000 | Docs: http://localhost:8000/docs
```

### Run locally (without Docker)

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
celery -A app.celery_app worker --loglevel=info --concurrency=2
```

### Database migrations

```bash
alembic upgrade head                          # Apply all migrations
alembic revision --autogenerate -m "message"  # Generate new migration
# Migrations live in app/alembic/versions/
```

### Install dependencies

```bash
pip install -r requirements-dev.txt  # Includes test/lint tools
```

### Testing

```bash
pytest                                              # All tests
pytest tests/unit/                                  # Unit tests only
pytest tests/integration/                           # Integration tests
pytest tests/property/                              # Property-based (Hypothesis)
pytest tests/unit/test_task_registry.py             # Single test file
pytest tests/unit/test_task_registry.py::TestClass::test_method  # Single test
pytest --hypothesis-profile=ci                      # Full Hypothesis runs (100 examples)
```

### Linting and formatting

```bash
black app/ tests/
isort app/ tests/
flake8 app/ tests/    # Config in .flake8 (max-line-length=120)
mypy app/
```

## Architecture

### Application factory

`app/main.py` defines `create_app(test_mode=False)` which wires all middleware and routers. `test_mode=True` disables AuthenticationMiddleware, CSRFMiddleware, and ResponseSchemaValidationMiddleware. The `lifespan` context manager handles startup/shutdown: initializes DB, Redis, then calls `init_*()` on routes that need it.

### Configuration

`app/config.py` — a `Settings` class that reads all config from environment variables. It validates security settings on init and **raises `ValueError` in production** if `JWT_SECRET_KEY`, `CURSOR_SIGNING_KEY`, or `DATABASE_URL`/`REDIS_URL` are missing or insecure. Both keys must be ≥32 characters.

### Middleware stack (outermost to innermost)

`RequestSizeLimitMiddleware` → `GZipMiddleware` → `PrometheusMetricsMiddleware` → `ProfilingMiddleware` (optional) → `RequestLoggingMiddleware` → `APIVersioningMiddleware` → `ResponseSchemaValidationMiddleware` → `CSRFMiddleware` → `AuthenticationMiddleware` → `DeprecationMiddleware` → `RateLimitingMiddleware` → `CORSMiddleware`

### Route initialization pattern

Several routers require explicit initialization during lifespan (not at import time):

- `sessions.init_session_routes(redis_client)` — provides Redis for session storage
- `tasks.init_task_routes()` — sets up task registry
- `export.init_export_routes(session_mgr)` — provides session manager
- `health.init_health_routes(redis_client)` — provides Redis for health checks

### Key directories

- `app/routes/` — FastAPI routers: `auth`, `users`, `sessions`, `templates`, `state`, `tasks`, `export`, `metrics`, `health`, `version`
- `app/services/` — Business logic: `auth_manager`, `session_manager`, `user_management`, `task_executor`, `webhook_manager`, `cache_service`, `rate_limiter`, `authorization`
- `app/middleware/` — Starlette middleware classes
- `app/database/models.py` — SQLAlchemy ORM (`User`, `Session`, `Task`, and related models)
- `app/database/connection.py` — Engine and `SessionLocal` factory
- `app/tasks/` — Celery task definitions (`experimental_tasks.py`) and `task_registry.py`
- `app/celery_app.py` — Celery app configured to use Redis broker (db/1) and backend (db/2)

### Database

PostgreSQL via SQLAlchemy (sync ORM). Redis db/0 for caching/sessions, db/1 for Celery broker, db/2 for Celery results. Optional database sharding via `app/database/sharded_connection.py` (disabled by default; enable with `DATABASE_SHARDS_ENABLED=true`).

### Authentication flow

JWT tokens obtained via `POST /v1/auth/login`. All endpoints except `/health`, `/docs`, `/openapi.json` require `Authorization: Bearer <token>`. Refresh via `POST /v1/auth/refresh`. TOTP/MFA supported via `pyotp`.

### Test setup

Unit tests use SQLite in-memory (`sqlite:///:memory:`). The `conftest.py` at `tests/` provides fixtures for DB engine, session, mock DB connection, and environment variables. Hypothesis profiles: `dev` (20 examples, default locally), `ci` (100 examples), `thorough` (1000 examples).

## Required Environment Variables

Minimum for development (see `.env` for full list):

```bash
ENVIRONMENT=development
DATABASE_URL=postgresql://apgi_dev:dev_password@localhost:5432/apgi_api_dev
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=<random string, min 32 chars>
CURSOR_SIGNING_KEY=<random string, min 32 chars>
```

Generate keys: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
