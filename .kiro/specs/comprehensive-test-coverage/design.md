# Design Document: Comprehensive Test Coverage

## Overview

This design describes the technical approach to raising the APGI FastAPI backend from ~1% measured
coverage to ≥ 80% overall (≥ 90% for routes, services, and middleware) while eliminating the
suite instability caused by psycopg2/opentelemetry import side-effects, fictional API references,
and duplicate test files.

The strategy has four pillars:

1. **Stable conftest hierarchy** — module-level mocking of problematic imports before any app code
   is loaded, applied consistently across all test sub-directories.
2. **Layered test types** — unit (isolated, fast), integration (SQLite in-memory, mocked
   externals), property-based (Hypothesis), and security tests, each in its own directory.
3. **Consolidation** — one canonical test file per application module; duplicate/fictional files
   are removed or merged.
4. **Coverage gate** — `--cov-fail-under=80` enforced in `pyproject.toml` and the CI workflow.

---

## Architecture

```
tests/
├── conftest.py                  # Root: env vars, Hypothesis profiles, SQLite engine fixture
├── unit/
│   ├── conftest.py              # psycopg2 + opentelemetry sys.modules patches (autouse)
│   ├── services/                # One file per app/services/*.py
│   ├── routes/                  # One file per app/routes/*.py
│   ├── middleware/              # One file per app/middleware/*.py
│   └── core/                   # config, main, exceptions, database, cli, tracing
├── integration/
│   ├── conftest.py              # FastAPI TestClient + SQLite DB + mocked Redis/Stripe/SMTP
│   └── test_*.py
├── property/
│   ├── conftest.py              # Hypothesis settings (ci profile: 100 examples)
│   └── test_*.py
└── security/
    ├── conftest.py              # TestClient in non-test_mode=False, mocked DB
    └── test_*.py
```

The `app/tests/` directory (legacy) is excluded from coverage measurement and not executed by the
default pytest invocation.

---

## Components and Interfaces

### Conftest Hierarchy

#### `tests/conftest.py` (root)

Responsibilities:
- Set `ENVIRONMENT=development`, `JWT_SECRET_KEY`, `CURSOR_SIGNING_KEY`, `WEBHOOK_SECRET_KEY`,
  `DATABASE_URL=sqlite:///:memory:`, `REDIS_URL=redis://localhost:6379/1` via `os.environ` before
  any app module is imported.
- Provide `test_db_engine` and `test_db_session` fixtures (SQLite in-memory).
- Register Hypothesis profiles: `ci` (100 examples), `dev` (20 examples), `thorough` (1000).
- Load `ci` profile when `CI=true` env var is set, otherwise `dev`.

```python
# tests/conftest.py (key additions)
import os
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough-32chars!")
os.environ.setdefault("CURSOR_SIGNING_KEY", "test-cursor-key-that-is-long-enough-32chars!")
os.environ.setdefault("WEBHOOK_SECRET_KEY", "test-webhook-key-that-is-long-enough-32c!")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
```

These must be set **before** `from app.config import settings` is executed anywhere.

#### `tests/unit/conftest.py`

Responsibilities:
- Patch `psycopg2`, `psycopg2.extensions`, `psycopg2.errors` into `sys.modules` as `MagicMock`
  instances with explicit attributes (not `spec=[]`).
- Patch all `opentelemetry.*` sub-modules into `sys.modules`.
- Patch `app.celery_app` to prevent Celery from connecting to a broker at import time.
- All fixtures are `autouse=True` and scoped to `function` to prevent state leakage.

```python
# Pattern for safe sys.modules patching
@pytest.fixture(autouse=True)
def mock_psycopg2():
    mock = MagicMock()
    mock.extensions = MagicMock()
    mock.extensions.ISOLATION_LEVEL_AUTOCOMMIT = 0
    mock.errors = MagicMock()
    mock.errors.DuplicateDatabase = type("DuplicateDatabase", (Exception,), {})
    mock.errors.DuplicateObject = type("DuplicateObject", (Exception,), {})
    sys.modules["psycopg2"] = mock
    sys.modules["psycopg2.extensions"] = mock.extensions
    sys.modules["psycopg2.errors"] = mock.errors
    yield
    for key in ["psycopg2", "psycopg2.extensions", "psycopg2.errors"]:
        sys.modules.pop(key, None)
```

#### `tests/integration/conftest.py`

Responsibilities:
- Create a `TestClient` using `app.main.create_app(test_mode=True)` to disable CSRF and
  authentication middleware (routes use dependency injection overrides instead).
- Provide `db_session` fixture backed by SQLite in-memory with all ORM tables created via
  `Base.metadata.create_all(engine)`.
- Override `get_db` FastAPI dependency to inject the test session.
- Provide `mock_redis`, `mock_stripe`, `mock_smtp` fixtures using `unittest.mock.patch`.

```python
@pytest.fixture(scope="function")
def app_client(db_session):
    from app.main import create_app
    from app.database.connection import get_db
    test_app = create_app(test_mode=True)
    test_app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(test_app) as client:
        yield client
```

#### `tests/property/conftest.py`

Responsibilities:
- Load Hypothesis `ci` profile (100 examples, `deadline=None`,
  `suppress_health_check=[HealthCheck.too_slow]`).
- Provide `auth_manager` fixture with a mock DB session.

#### `tests/security/conftest.py`

Responsibilities:
- Create a `TestClient` with `test_mode=False` (all middleware active) but with DB dependency
  overridden to use SQLite in-memory.
- Provide `valid_token` and `expired_token` fixtures.

---

### Mocking Strategy

All external dependencies are mocked at the appropriate boundary:

| Dependency | Mock Location | Technique |
|---|---|---|
| psycopg2 | `tests/unit/conftest.py` | `sys.modules` replacement (autouse) |
| opentelemetry | `tests/unit/conftest.py` | `sys.modules` replacement (autouse) |
| SQLAlchemy Session | Unit tests | `MagicMock()` passed to service constructor |
| Redis | Unit/integration | `unittest.mock.patch("app.services.cache_service.redis_client")` |
| Stripe | Unit/integration | `unittest.mock.patch("stripe.PaymentIntent.create")` etc. |
| SMTP / smtplib | Unit | `unittest.mock.patch("smtplib.SMTP")` |
| Celery tasks | Unit | `unittest.mock.patch.object(task, "delay")` |
| `app.celery_app` | `tests/unit/conftest.py` | `sys.modules["app.celery_app"] = MagicMock()` |
| httpx.AsyncClient | Webhook tests | `unittest.mock.patch("httpx.AsyncClient.post")` |

**Key rule**: Never use `Mock(spec=[])` — use `MagicMock()` with explicit attribute assignment or
anonymous classes. `spec=[]` causes `AttributeError` on attribute access in Python 3.12+.

---

### Unit Test Design Patterns

#### Services

Each service test file follows this pattern:

```python
# tests/unit/services/test_auth_manager.py
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

@pytest.fixture
def db():
    return MagicMock()

@pytest.fixture
def auth_manager(db):
    from app.services.auth_manager import AuthManager
    return AuthManager(db)

class TestHashPassword:
    def test_hash_returns_bcrypt_string(self, auth_manager):
        h = auth_manager.hash_password("secret")
        assert h.startswith("$2b$")

    def test_verify_correct_password(self, auth_manager):
        h = auth_manager.hash_password("secret")
        assert auth_manager.verify_password("secret", h)

    def test_verify_wrong_password(self, auth_manager):
        h = auth_manager.hash_password("secret")
        assert not auth_manager.verify_password("wrong", h)
```

Services that depend on Redis (`CacheService`, `RateLimiter`) receive a `MagicMock` redis client
in their constructor. Async methods on the mock are replaced with `AsyncMock`.

#### Routes

Route tests use `fastapi.testclient.TestClient` with `create_app(test_mode=True)` and dependency
overrides:

```python
@pytest.fixture
def client(db_session):
    from app.main import create_app
    from app.database.connection import get_db
    from app.middleware.authentication import get_current_user
    app = create_app(test_mode=True)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: fake_user
    return TestClient(app)
```

Each route test class covers: happy path, missing auth (401), wrong permission (403), not found
(404), and invalid body (422).

#### Middleware

Middleware tests instantiate the middleware class directly and call `dispatch()` with a mock
`Request` and a mock `call_next` coroutine:

```python
async def test_auth_middleware_valid_token(valid_jwt):
    from app.middleware.authentication import AuthenticationMiddleware
    middleware = AuthenticationMiddleware(app=MagicMock())
    request = MagicMock()
    request.url.path = "/v1/users/me"
    request.headers = {"Authorization": f"Bearer {valid_jwt}"}
    request.state = MagicMock()

    async def call_next(req):
        return MagicMock(status_code=200, headers={})

    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 200
    assert request.state.authenticated is True
```

---

### Integration Test Design

Integration tests use SQLite in-memory via SQLAlchemy. The `Base.metadata.create_all(engine)` call
creates all tables before each test function. Foreign key enforcement is enabled for SQLite:

```python
from sqlalchemy import event
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA foreign_keys=ON")
```

Critical flows covered:

1. **Auth flow**: register → verify email (mock SMTP) → login → receive JWT
2. **Token refresh**: use access token → refresh → verify old refresh token revoked
3. **Logout**: login → logout → verify 401 on subsequent request
4. **Session lifecycle**: create → start → pause → resume → verify state transitions
5. **Stripe webhook**: POST `/v1/payments/webhook` with mocked `stripe.Webhook.construct_event`
6. **Rate limiting**: exceed limit → verify 429 with `Retry-After` header

---

### Property-Based Test Design

All property tests use Hypothesis with the `ci` profile (100 examples minimum).

Each test is tagged with a comment referencing the design property:
```python
# Feature: comprehensive-test-coverage, Property 1: Password hash round-trip
@given(password=st.text(min_size=1, max_size=72, alphabet=st.characters(
    blacklist_characters="\x00", blacklist_categories=["Cs"])))
def test_password_hash_roundtrip(password):
    ...
```

Generators used:
- Passwords: `st.text(min_size=1, max_size=72)` excluding null bytes and surrogates
- User IDs: `st.uuids().map(str)`
- Usernames: `st.from_regex(r"[a-zA-Z0-9_]{1,50}", fullmatch=True)`
- Roles: `st.lists(st.sampled_from(["admin", "viewer", "researcher"]), min_size=0, max_size=3)`
- Pagination: `st.integers(min_value=0, max_value=1000)` for skip, `st.integers(min_value=1, max_value=100)` for limit
- CORS origin strings: `st.text(alphabet=st.characters(whitelist_categories=["Lu","Ll","Nd","P"]), min_size=0, max_size=200)`
- Session states: `st.sampled_from(list(SessionLifecycleState))`

---

### Security Test Design

Security tests run with all middleware active (`test_mode=False`) but with the DB dependency
overridden. They verify:

- Tampered JWT → 401
- Expired JWT → 401
- SQL injection in query params → 400
- Missing CSRF token on POST → 403
- Viewer role on admin endpoint → 403
- Non-UUID session ID → ValueError from validator

---

### Test Consolidation Approach

The following duplicate files will be consolidated (keeping the more comprehensive version and
merging unique test cases):

| Keep | Remove (merge into keep) |
|---|---|
| `test_cache_service.py` | `test_cache_service_simple.py` |
| `test_business_metrics.py` | `test_business_metrics_simple.py` |
| `test_cli.py` | `test_cli_simple.py`, `test_cli_comprehensive.py` |
| `test_profiling_service.py` | `test_profiling_service_simple.py` |
| `test_security_validation.py` | `test_security_validation_real.py`, `test_security_validation_comprehensive.py` |
| `test_sharded_connection.py` | `test_sharded_connection_comprehensive.py` |
| `test_schema_validation.py` | `test_schema_validation_middleware.py` |
| `test_task_routes.py` | `test_tasks_routes.py` |

Fictional test files (referencing non-existent APIs) will be rewritten from scratch against the
actual module interfaces.

---

## Data Models

No new data models are introduced. Tests operate against the existing SQLAlchemy ORM models in
`app/database/models.py` and Pydantic schemas in `app/models/schemas.py`.

Test fixtures that create model instances use the ORM constructors directly:

```python
from app.database.models import User
user = User(
    id=str(uuid4()),
    username="testuser",
    email="test@example.com",
    hashed_password=AuthManager.hash_password("TestPass123!"),
    is_active=True,
    is_verified=True,
)
db_session.add(user)
db_session.commit()
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a
system — essentially, a formal statement about what the system should do. Properties serve as the
bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Password Hash Round-Trip

*For any* non-empty password string (excluding null bytes), hashing it with `AuthManager.hash_password`
and then verifying with `AuthManager.verify_password` should return `True`.

**Validates: Requirements 2.13, 7.1**

---

### Property 2: Different Passwords Do Not Cross-Verify

*For any* two distinct non-empty password strings, verifying one against the hash of the other
should return `False`.

**Validates: Requirements 2.14**

---

### Property 3: Token Creation Round-Trip

*For any* valid `user_id` (UUID string), `username` (alphanumeric), and `roles` list,
`AuthManager.create_access_token` followed by `AuthManager.verify_token` should return a payload
containing the original `user_id`, `username`, and `roles`.

**Validates: Requirements 2.15, 7.2**

---

### Property 4: Invalid Request Body Returns 4xx

*For any* route handler that declares a Pydantic request body schema, sending a request body that
fails schema validation should result in an HTTP 400 or HTTP 422 response.

**Validates: Requirements 3.14**

---

### Property 5: Unauthenticated Request to Protected Route Returns 401

*For any* protected route path, a request with no `Authorization` header or an expired/invalid
token should result in HTTP 401, and the response should include a `WWW-Authenticate` header.

**Validates: Requirements 3.15, 4.14**

---

### Property 6: Unauthorized Request Returns 403

*For any* permission-protected endpoint, a request from a user whose roles do not include the
required permission should result in HTTP 403.

**Validates: Requirements 3.16, 9.5**

---

### Property 7: Missing Resource Returns 404

*For any* resource-fetching endpoint, a request referencing a resource ID that does not exist in
the database should result in HTTP 404.

**Validates: Requirements 3.17**

---

### Property 8: Valid Token Sets Authenticated State

*For any* valid, non-expired JWT access token presented to `AuthenticationMiddleware`, the
middleware should set `request.state.authenticated = True` and call `call_next`.

**Validates: Requirements 4.13**

---

### Property 9: Rate Limit Exceeded Returns 429

*For any* configured rate limit N, sending more than N requests within the time window from the
same client should result in HTTP 429 with a `Retry-After` header on the excess requests.

**Validates: Requirements 4.15**

---

### Property 10: Valid Settings Initialization

*For any* JWT secret key string of length ≥ 32 that does not match a known insecure prefix,
`Settings()` should initialize without raising `ValueError` in development mode.

**Validates: Requirements 5.13**

---

### Property 11: Pagination Length Invariant

*For any* valid `skip` (≥ 0) and `limit` (1–100) values, `UserManagementService.list_users`
should return a list whose length is ≤ `limit`.

**Validates: Requirements 7.3**

---

### Property 12: Session State Transition Invariant

*For any* `SessionLifecycleState` and any transition not listed in `ALLOWED_TRANSITIONS`, the
transition attempt should raise `ValueError`. For any allowed transition, it should succeed.

**Validates: Requirements 7.4**

---

### Property 13: CORS Origins Parsing Invariant

*For any* comma-separated string of origin values, `Settings._parse_cors_origins` should return a
list containing no empty strings and no strings with leading or trailing whitespace.

**Validates: Requirements 7.5**

---

### Property 14: Schema Model JSON Round-Trip

*For any* valid Pydantic schema model instance, `model.model_dump_json()` followed by
`Model.model_validate_json()` should produce an object equal to the original.

**Validates: Requirements 7.6**

---

### Property 15: Tampered Token Raises InvalidTokenError

*For any* valid JWT token whose payload has been modified (signature no longer matches),
`AuthManager.verify_token` should raise `InvalidTokenError`.

**Validates: Requirements 9.1**

---

### Property 16: SQL Injection Patterns Return 400

*For any* request containing a known SQL injection pattern (e.g., `' OR 1=1 --`, `; DROP TABLE`)
in a query parameter or path segment, `SecurityValidationMiddleware` should return HTTP 400.

**Validates: Requirements 9.3**

---

### Property 17: Missing CSRF Token Returns 403

*For any* state-mutating HTTP method (POST, PUT, PATCH, DELETE) to a non-exempt endpoint without
a valid CSRF token, `CSRFMiddleware` should return HTTP 403.

**Validates: Requirements 9.4**

---

### Property 18: Invalid Session ID Raises ValueError

*For any* string that is not a valid UUID v4, `validate_session_id` should raise `ValueError`.

**Validates: Requirements 9.6**

---

## Error Handling

### Import Errors at Collection Time

The root cause of most collection failures is that `app.config.Settings()` is instantiated at
module import time and raises `ValueError` when `JWT_SECRET_KEY` is missing. The fix is to set
all required environment variables in `tests/conftest.py` **before** any app import occurs.

For modules that import psycopg2 or opentelemetry at the top level, the `sys.modules` patches in
`tests/unit/conftest.py` must be applied before those modules are imported. Since pytest loads
`conftest.py` files before test files, the `autouse=True` fixtures ensure patches are in place.

### Segfaults from psycopg2

psycopg2's C extension can segfault when its internal state is corrupted by repeated
import/unimport cycles across test processes. The fix is to replace the entire `psycopg2` module
with a `MagicMock` at the start of each test function and clean up after. This prevents the C
extension from ever being loaded in the test process.

### Celery Broker Connection Hangs

Celery attempts to connect to the broker when the app module is imported if `celery_app` is
instantiated at module level. The fix is to mock `app.celery_app` in `sys.modules` before any
task module is imported.

### Stripe Webhook Signature Verification

Stripe's `stripe.Webhook.construct_event` raises `SignatureVerificationError` if the signature
header is missing or invalid. Integration tests mock this function to return a pre-built event
object, bypassing the signature check.

---

## Testing Strategy

### Dual Testing Approach

Both unit tests and property-based tests are required and complementary:

- **Unit tests** verify specific examples, error conditions, and integration points between
  components. They are fast and deterministic.
- **Property tests** verify universal invariants across many generated inputs. They catch edge
  cases that specific examples miss.

### Unit Test Balance

Unit tests should focus on:
- Specific happy-path examples demonstrating correct behavior
- Error conditions (invalid input, missing resource, permission denied)
- Integration points between a module and its direct dependencies

Avoid writing unit tests that duplicate what property tests already cover (e.g., don't write 10
unit tests for different password lengths when a property test covers all lengths).

### Property-Based Testing Configuration

Library: **Hypothesis** (already in `dev` dependencies)

Configuration in `tests/conftest.py`:
```python
from hypothesis import settings, HealthCheck

settings.register_profile("ci",
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much]
)
settings.register_profile("dev", max_examples=20, deadline=None,
    suppress_health_check=[HealthCheck.too_slow])

import os
settings.load_profile("ci" if os.getenv("CI") else "dev")
```

Each property test must be tagged:
```python
# Feature: comprehensive-test-coverage, Property N: <property text>
```

Each correctness property is implemented by exactly one property-based test function.

### Coverage Configuration

`pyproject.toml` additions:

```toml
[tool.pytest.ini_options]
addopts = """
  -ra -q --strict-markers
  --cov=app
  --cov-report=term-missing
  --cov-report=html
  --cov-fail-under=80
  --ignore=tests/load
  --ignore=tests/test_load.py
"""

[tool.coverage.run]
source = ["app"]
branch = true
omit = [
    "*/tests/*",
    "*/alembic/*",
    "*/__pycache__/*",
    "app/tests/*",
]

[tool.coverage.report]
fail_under = 80
show_missing = true
```

### CI/CD Integration

In `.github/workflows/ci-cd.yml`, the test step should:

```yaml
- name: Run tests with coverage
  env:
    CI: "true"
    JWT_SECRET_KEY: ${{ secrets.JWT_SECRET_KEY_TEST }}
    CURSOR_SIGNING_KEY: ${{ secrets.CURSOR_SIGNING_KEY_TEST }}
    WEBHOOK_SECRET_KEY: ${{ secrets.WEBHOOK_SECRET_KEY_TEST }}
    ENVIRONMENT: development
    DATABASE_URL: sqlite:///:memory:
  run: |
    pytest tests/ --ignore=tests/load -x -q
```

The `--cov-fail-under=80` in `addopts` causes pytest to exit non-zero if coverage drops below 80%,
blocking the CI build automatically.

### Test File Naming Convention

- `tests/unit/services/test_{module_name}.py` → covers `app/services/{module_name}.py`
- `tests/unit/routes/test_{module_name}.py` → covers `app/routes/{module_name}.py`
- `tests/unit/middleware/test_{module_name}.py` → covers `app/middleware/{module_name}.py`
- `tests/unit/core/test_{module_name}.py` → covers `app/{module_name}.py`
- `tests/integration/test_{flow_name}.py` → covers multi-module flows
- `tests/property/test_{domain}_properties.py` → covers property tests for a domain
- `tests/security/test_{concern}_security.py` → covers security tests for a concern
