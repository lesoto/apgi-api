# Design: test-coverage-100

## Overview

This design describes the strategy for achieving 100% statement and branch coverage across all `app/` modules, starting from the current ~30% baseline. The approach is layered: fix broken tests and consolidate duplicates first, then fill coverage gaps module-by-module using a consistent fixture and mocking strategy, and finally enforce the gate in `pyproject.toml`.

The key architectural insight is that the app has two test modes:
- `test_mode=True` — disables `AuthenticationMiddleware`, `CSRFMiddleware`, `SecurityValidationMiddleware`, and `ResponseSchemaValidationMiddleware`. Used for all unit and route tests.
- `test_mode=False` — full middleware stack active. Used only for integration tests that specifically verify middleware behaviour.

All external I/O (Redis, PostgreSQL via psycopg2, Celery broker, Stripe, OpenTelemetry, SMTP) must be mocked. No live services are required to run the test suite.

---

## Architecture

### Test Layer Structure

```
tests/
├── conftest.py                  # Root: env vars, Hypothesis profiles, shared SQLite fixtures
├── unit/
│   ├── conftest.py              # psycopg2, opentelemetry, celery_app sys.modules patches
│   └── test_*.py                # Isolated unit tests (test_mode=True)
├── integration/
│   └── test_middleware_stack.py # Full-stack tests (test_mode=False, SQLite in-memory)
├── property/
│   └── test_*.py                # Hypothesis property tests
└── security/
    └── test_security_basics.py  # Security-focused tests
```

### Fixture Hierarchy

```
conftest.py (root)
  └── JWT_SECRET_KEY, CURSOR_SIGNING_KEY, WEBHOOK_SECRET_KEY env vars (setdefault)
  └── Hypothesis profiles: ci (100 examples), dev (20), thorough (1000)
  └── test_db_engine / test_db_session (SQLite in-memory)

tests/unit/conftest.py
  └── mock_psycopg2 (function-scoped, manual — not autouse)
  └── mock_opentelemetry (autouse, function-scoped)
  └── mock_celery_app (autouse, function-scoped)
```

### TestClient Patterns

Unit/route tests:
```python
from starlette.testclient import TestClient
from app.main import create_app

@pytest.fixture
def client():
    app = create_app(test_mode=True)
    with TestClient(app) as c:
        yield c
```

Middleware integration tests:
```python
@pytest.fixture
def full_stack_client():
    app = create_app(test_mode=False)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
```

---

## Components and Interfaces

### 1. Zero-Coverage Module Tests

Each currently-uncovered module gets a dedicated test file. The table below maps modules to test files and the primary mocking strategy.

| Module | Test File | Key Mocks |
|---|---|---|
| `app/main.py` | `tests/unit/test_main_comprehensive.py` | `init_db`, `redis.asyncio`, `init_cache_service`, route inits |
| `app/cli.py` | `tests/unit/test_cli.py` | `CliRunner`, `alembic`, `celery_app`, `seeding_service`, `init_db` |
| `app/middleware/logging.py` | `tests/unit/test_logging_middleware.py` | `call_next` mock |
| `app/exception_handlers.py` | `tests/unit/test_exception_handlers.py` | `TestClient(create_app(test_mode=True))` |
| `app/create_db.py` | `tests/unit/test_create_db.py` (consolidated) | `mock_psycopg2` fixture |
| `app/create_demo_user.py` | `tests/unit/test_create_demo_user.py` | `SessionLocal`, `AuthManager` |
| `app/middleware/profiling.py` | `tests/unit/test_profiling_middleware.py` | `call_next` mock, `cProfile` |
| `app/tasks/webhook_tasks.py` | `tests/unit/test_webhook_tasks.py` | `SessionLocal`, `WebhookManager`, `asyncio.run` |
| `app/reset_db.py` | `tests/unit/test_reset_db.py` (consolidated) | `mock_psycopg2` fixture |

### 2. Service Tests

All service tests use `unittest.mock.patch` or `MagicMock` to replace database sessions, Redis clients, and external HTTP calls. The pattern is:

```python
@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def service(mock_db):
    return SessionManager(mock_db)
```

Services with async methods use `AsyncMock` for coroutine returns.

### 3. Route Tests

All route tests use `TestClient(create_app(test_mode=True))`. Database dependencies are overridden via FastAPI's `app.dependency_overrides`:

```python
from app.database.connection import get_db

@pytest.fixture
def client(mock_db_session):
    app = create_app(test_mode=True)
    app.dependency_overrides[get_db] = lambda: mock_db_session
    with TestClient(app) as c:
        yield c
```

Stripe is already patched at module level in `tests/unit/conftest.py`.

### 4. Middleware Integration Tests

These tests live in `tests/integration/test_middleware_stack.py` and use `create_app(test_mode=False)`. They require:
- A valid JWT token generated with the test `JWT_SECRET_KEY`
- A CSRF token flow (GET to obtain cookie, then POST with header)
- Mocked Redis for rate limiting (or a real in-process Redis mock)

```python
def make_jwt(user_id="test-user", secret=None):
    import jwt, datetime
    secret = secret or os.environ["JWT_SECRET_KEY"]
    payload = {
        "sub": user_id, "user_id": user_id, "username": "testuser",
        "roles": ["user"], "token_type": "access",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        "iat": datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, secret, algorithm="HS256")
```

### 5. Celery Task Tests

Celery tasks are tested by calling the underlying Python function directly (bypassing the broker), or by using `task.apply()` with `CELERY_TASK_ALWAYS_EAGER=True`:

```python
def test_process_pending_webhooks(mock_db, mock_webhook_manager):
    with patch("app.tasks.webhook_tasks.SessionLocal", return_value=mock_db):
        with patch("app.tasks.webhook_tasks.WebhookManager", return_value=mock_webhook_manager):
            result = process_pending_webhooks.apply()
            assert result.successful()
```

### 6. CLI Tests

CLI commands are tested with `click.testing.CliRunner`:

```python
from click.testing import CliRunner
from app.cli import cli

def test_migrate_command():
    runner = CliRunner()
    with patch("alembic.config.Config"), patch("alembic.command.upgrade"):
        result = runner.invoke(cli, ["migrate"])
        assert result.exit_code == 0
```

### 7. psycopg2-Dependent Module Tests

`app/create_db.py` and `app/reset_db.py` import `psycopg2` at module level. Tests must use the `mock_psycopg2` fixture from `tests/unit/conftest.py` and re-import the module inside the test after patching:

```python
def test_create_database_success(mock_psycopg2):
    import importlib
    import app.create_db as create_db_mod
    importlib.reload(create_db_mod)
    mock_psycopg2.connect.return_value.__enter__ = MagicMock()
    # ... configure mock and call create_db_mod.create_database()
```

### 8. Coverage Gate Configuration

`pyproject.toml` changes required:
- `addopts` in `[tool.pytest.ini_options]`: add `--cov-fail-under=100`
- `[tool.coverage.report]`: add `fail_under = 100`
- `[tool.coverage.run]`: add `branch = true`

### 9. Test Consolidation

Duplicate files to consolidate:
- `test_create_db.py` + `test_create_db_fixed.py` → `test_create_db.py`
- `test_reset_db.py` + `test_reset_db_fixed.py` → `test_reset_db.py`

The `_fixed` variants should be deleted after their passing tests are merged into the canonical files.

---

## Data Models

### Hypothesis Strategies for Schema Round-Trip Tests

Pydantic models in `app/models/schemas.py` are tested using Hypothesis `builds()` strategy. The pattern for each schema group:

```python
from hypothesis import given, settings
from hypothesis import strategies as st
from app.models.schemas import UserCreate

user_strategy = st.builds(
    UserCreate,
    username=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))),
    email=st.emails(),
    password=st.text(min_size=8, max_size=128),
)

@given(user_strategy)
def test_user_schema_round_trip(user):
    assert UserCreate.model_validate(user.model_dump()) == user
```

### JWT Payload Model

For JWT round-trip property tests:

```python
jwt_payload_strategy = st.fixed_dictionaries({
    "user_id": st.uuids().map(str),
    "username": st.text(min_size=1, max_size=50),
    "roles": st.lists(st.sampled_from(["user", "admin"]), min_size=0, max_size=3),
    "token_type": st.just("access"),
})
```

### Rate Limiter State

The rate limiter `check_rate_limit(key, limit)` returns `(allowed: bool, remaining: int, reset_time: float)`. The monotonicity property operates on this interface.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Schema dict round-trip

*For any* valid instance of a Pydantic model in `app/models/schemas.py`, calling `Model.model_validate(instance.model_dump())` produces an object equal to the original instance.

**Validates: Requirements 6.1, 12.1**

### Property 2: Schema JSON round-trip

*For any* valid instance of a Pydantic model in `app/models/schemas.py`, calling `Model.model_validate_json(instance.model_dump_json())` produces an object equal to the original instance.

**Validates: Requirements 6.2**

### Property 3: Session serialization round-trip

*For any* valid session object, serializing it to a dict/JSON and then deserializing produces an equivalent object.

**Validates: Requirements 12.2**

### Property 4: SecurityValidationMiddleware is a total function

*For any* string input passed as a JSON body field, `SecurityValidationMiddleware._validate_request` either returns `{"is_valid": True}` or `{"is_valid": False}` — it never raises an unhandled exception.

**Validates: Requirements 12.3**

### Property 5: JWT encode-decode round-trip

*For any* valid JWT payload dict (with user_id, username, roles, token_type="access"), encoding with `AuthManager.create_access_token` and then decoding with `AuthManager.decode_token` returns a payload equivalent to the original.

**Validates: Requirements 12.4**

### Property 6: Rate limiter remaining count is monotonically non-increasing

*For any* rate limit key and limit value, calling `check_rate_limit(key, limit)` twice in sequence returns a `remaining` value on the second call that is less than or equal to the `remaining` value from the first call.

**Validates: Requirements 12.5**

### Property 7: Task registry get-function round-trip

*For any* valid `TaskType` enum value, `get_task_function(task_type)` returns the same callable object that is stored in `TASK_FUNCTIONS[task_type]`.

**Validates: Requirements 12.6**

### Property 8: Security headers present on all responses

*For any* request to any endpoint served by `create_app()`, the response includes the `X-Content-Type-Options`, `X-Frame-Options`, and `Strict-Transport-Security` headers.

**Validates: Requirements 9.6**

---

## Error Handling

### Mock Failure Paths

Every service and route test must cover at least one error path in addition to the happy path. Standard patterns:

- **Database errors**: `mock_db.query.side_effect = SQLAlchemyError("db error")`
- **Redis unavailable**: `mock_redis.get.side_effect = redis.RedisError("connection refused")`
- **Stripe errors**: `stripe.PaymentIntent.create.side_effect = stripe.error.StripeError("card declined")`
- **Celery task failure**: assert `result.state == "FAILURE"` after `task.apply()` with a side-effect exception

### Exception Handler Coverage

`app/exception_handlers.py` registers handlers for custom exception types. Each handler is covered by raising the corresponding exception type through a test route:

```python
# In test: trigger the handler via a route that raises the exception
response = client.get("/test-route-that-raises-NotFoundError")
assert response.status_code == 404
```

### psycopg2 Error Paths

`app/create_db.py` has a `DuplicateDatabase` catch path. `app/reset_db.py` has `InsufficientPrivilege` and generic `Exception` paths. Both are covered by configuring `mock_psycopg2.connect.side_effect` or `mock_psycopg2.errors.DuplicateDatabase`.

---

## Testing Strategy

### Dual Testing Approach

Both unit tests and property-based tests are required. They are complementary:
- Unit tests verify specific examples, error conditions, and integration points
- Property tests verify universal invariants across generated inputs

### Unit Test Focus Areas

- One test per acceptance criterion happy path
- One test per error/exception path per handler
- Integration points between route → service → DB
- CLI command success and failure (sys.exit) paths
- Middleware dispatch with enabled=True and enabled=False

### Property-Based Testing with Hypothesis

The project already uses Hypothesis. All property tests must:
- Use the `@given` decorator with explicit strategies
- Reference the design property they validate in a comment: `# Feature: test-coverage-100, Property N: <text>`
- Run at minimum 100 iterations (enforced by the `ci` profile already configured in `tests/conftest.py`)
- Be tagged with `@pytest.mark.property`

Each correctness property above maps to exactly one property-based test function.

**Profile selection** (already implemented in `tests/conftest.py`):
```python
settings.load_profile("ci" if os.getenv("CI") else "dev")
```

### Coverage Gate

After all tests pass, `pyproject.toml` is updated:

```toml
[tool.pytest.ini_options]
addopts = "... --cov-fail-under=100"

[tool.coverage.run]
branch = true

[tool.coverage.report]
fail_under = 100
```

The `branch = true` setting ensures both statement and branch coverage are measured, catching untested conditional arms.

### Test Execution Order and Isolation

- All tests are function-scoped (no shared mutable state)
- `mock_opentelemetry` and `mock_celery_app` are `autouse=True` in `tests/unit/conftest.py`
- `mock_psycopg2` is opt-in (not autouse) to avoid interfering with tests that don't need it
- Integration tests in `tests/integration/` may use a shared `session`-scoped SQLite engine for performance

### Middleware Integration Test Strategy

`tests/integration/test_middleware_stack.py` uses `create_app(test_mode=False)` with:
- `patch("app.database.connection.init_db")` to skip real DB init
- `patch("app.services.cache_service.init_cache_service")`
- `patch("redis.asyncio.from_url")` returning an `AsyncMock` that responds to `ping()`
- `patch` on all route `init_*` functions

This allows the full middleware stack to run without any live infrastructure.
