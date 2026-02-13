# Design Document: API Migration to Standalone Application

## Overview

This design document specifies the architecture and implementation approach for migrating the existing APGI REST API from its current embedded structure to a standalone, independently deployable application. The standalone API will maintain full backward compatibility while enabling independent deployment, scaling, and maintenance.

### Goals

- Extract API code into a self-contained standalone application
- Enable independent deployment on a separate domain
- Maintain backward compatibility with existing clients
- Support horizontal scaling and high availability
- Provide comprehensive monitoring and observability
- Ensure production-ready security and configuration management

### Non-Goals

- Modifying the API interface or breaking existing clients
- Migrating the main APGI system or GUI components
- Implementing new API features beyond the migration scope
- Changing the underlying APGI system algorithms or models

## Architecture

### High-Level Architecture

```mermaid
graph TB
    subgraph "Standalone API Application"
        LB[Load Balancer]
        API1[API Instance 1]
        API2[API Instance 2]
        API3[API Instance N]
        Worker1[Celery Worker 1]
        Worker2[Celery Worker N]
    end
    
    subgraph "Data Layer"
        PG[(PostgreSQL)]
        Redis[(Redis Cache)]
    end
    
    subgraph "Clients"
        Web[Web Frontend]
        Mobile[Mobile App]
        CLI[CLI Tools]
    end
    
    Web --> LB
    Mobile --> LB
    CLI --> LB
    
    LB --> API1
    LB --> API2
    LB --> API3
    
    API1 --> PG
    API2 --> PG
    API3 --> PG
    
    API1 --> Redis
    API2 --> Redis
    API3 --> Redis
    
    Worker1 --> Redis
    Worker2 --> Redis
    Worker1 --> PG
    Worker2 --> PG
```

### Directory Structure


The standalone API will be organized in a new `standalone-api/` directory:

```
standalone-api/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Configuration management
│   ├── exceptions.py           # Custom exception definitions
│   ├── exception_handlers.py  # Exception handler registration
│   ├── logging_config.py       # Structured logging configuration
│   ├── celery_app.py          # Celery configuration
│   ├── alembic.ini            # Alembic configuration
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py      # Database connection and session management
│   │   └── models.py          # SQLAlchemy ORM models
│   │
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── authentication.py  # JWT authentication middleware
│   │   ├── csrf.py            # CSRF protection
│   │   ├── rate_limiting.py   # Rate limiting middleware
│   │   ├── logging.py         # Request logging middleware
│   │   ├── metrics.py         # Prometheus metrics middleware
│   │   ├── alerting.py        # Error alerting middleware
│   │   ├── deprecation.py     # API deprecation warnings
│   │   ├── request_size_limit.py  # Request size limiting
│   │   └── schema_validation.py   # Response schema validation
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py         # Pydantic request/response models
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py            # Authentication endpoints
│   │   ├── users.py           # User management endpoints
│   │   ├── sessions.py        # Session management endpoints
│   │   ├── state.py           # State query endpoints
│   │   ├── tasks.py           # Async task endpoints
│   │   ├── export.py          # Data export endpoints
│   │   ├── health.py          # Health check endpoints
│   │   ├── metrics.py         # Metrics endpoints
│   │   └── version.py         # Version and deprecation info
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_manager.py    # JWT token management
│   │   ├── authorization.py   # Permission checking
│   │   ├── user_management.py # User CRUD operations
│   │   ├── session_manager.py # Session lifecycle management
│   │   ├── task_executor.py   # Celery task execution
│   │   ├── data_export.py     # Data export service
│   │   ├── health_check.py    # Health check service
│   │   ├── rate_limiter.py    # Rate limiting service
│   │   └── webhook_manager.py # Webhook notification service
│   │
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── task_registry.py   # Task registration
│   │   └── experimental_tasks.py  # Experimental task definitions
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   └── dependency_checker.py  # Startup dependency validation
│   │
│   └── alembic/
│       ├── env.py             # Alembic environment configuration
│       ├── script.py.mako     # Migration script template
│       └── versions/          # Database migration scripts
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Pytest configuration and fixtures
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── property/              # Property-based tests
│
├── deployment/
│   ├── Dockerfile             # Production Docker image
│   ├── Dockerfile.dev         # Development Docker image
│   ├── docker-compose.yml     # Local development orchestration
│   ├── docker-compose.prod.yml  # Production orchestration
│   └── k8s/                   # Kubernetes manifests (optional)
│       ├── deployment.yaml
│       ├── service.yaml
│       ├── ingress.yaml
│       └── configmap.yaml
│
├── docs/
│   ├── README.md              # Main documentation
│   ├── DEPLOYMENT.md          # Deployment guide
│   ├── CONFIGURATION.md       # Configuration reference
│   ├── API.md                 # API documentation
│   └── MIGRATION.md           # Migration guide from legacy API
│
├── scripts/
│   ├── start.sh               # Start script for development
│   ├── migrate.sh             # Database migration script
│   └── health_check.sh        # Health check script
│
├── .env.example               # Example environment configuration
├── .env.development           # Development environment defaults
├── .env.production            # Production environment template
├── requirements.txt           # Python dependencies
├── requirements-dev.txt       # Development dependencies
├── pyproject.toml             # Package metadata and build config
├── setup.py                   # Package installation script
└── README.md                  # Quick start guide
```


## Components and Interfaces

### 1. Application Entry Point (main.py)

The main application module creates and configures the FastAPI application with all middleware, routes, and lifecycle management.

**Key Responsibilities:**
- Create FastAPI application instance
- Configure middleware stack in correct order
- Register route handlers
- Manage application lifecycle (startup/shutdown)
- Initialize database and Redis connections
- Configure CORS and security settings

**Interface:**

```python
def create_app(test_mode: bool = False) -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Args:
        test_mode: If True, disables authentication and CSRF for testing
        
    Returns:
        Configured FastAPI application instance
    """
    
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    Handles resource initialization and cleanup.
    """
```

**Middleware Stack Order (outer to inner):**
1. RequestSizeLimitMiddleware - Reject oversized requests early
2. GZipMiddleware - Compress responses
3. PrometheusMetricsMiddleware - Track all requests
4. RequestLoggingMiddleware - Log all requests
5. AuthenticationMiddleware - Extract and verify JWT tokens
6. ResponseSchemaValidationMiddleware - Validate response schemas
7. CSRFMiddleware - CSRF protection for state-changing operations
8. DeprecationMiddleware - Track deprecated endpoint usage
9. RateLimitingMiddleware - Rate limit requests per user/IP
10. CORSMiddleware - Handle cross-origin requests

### 2. Configuration Management (config.py)

Centralized configuration system that loads settings from environment variables with validation and security checks.

**Key Responsibilities:**
- Load configuration from environment variables
- Provide sensible defaults for development
- Validate security-critical settings
- Fail fast on missing production requirements
- Support multiple environments (dev, staging, prod)

**Interface:**

```python
class Settings:
    """API configuration settings."""
    
    # API Settings
    api_title: str
    api_version: str
    
    # Server Settings
    host: str
    port: int
    
    # Database Settings
    database_url: str
    
    # Redis Settings
    redis_url: str
    
    # Celery Settings
    celery_broker_url: str
    celery_result_backend: str
    
    # Authentication Settings
    jwt_secret_key: str
    jwt_algorithm: str
    jwt_access_token_expire_minutes: int
    
    # CORS Settings
    cors_origins: List[str]
    cors_allow_credentials: bool
    
    # Rate Limiting
    rate_limit_enabled: bool
    rate_limit_per_minute: int
    
    # Logging
    log_level: str
    
    def __post_init__(self):
        """Validate security settings after initialization."""

settings = Settings()  # Global settings instance
```

**Security Validations:**
- JWT secret key must be set and secure (32+ characters) in production
- CORS origins must be explicitly configured (no wildcard with credentials)
- Database URL must use secure connection in production
- All security warnings logged during startup

### 3. Database Layer (database/)

SQLAlchemy-based database layer with connection pooling, session management, and ORM models.

**Key Responsibilities:**
- Manage database connections with pooling
- Provide session factory for request-scoped sessions
- Define ORM models for all entities
- Initialize database schema on startup
- Create default users for testing

**Interface:**

```python
# Connection Management
engine: Engine  # SQLAlchemy engine with connection pooling
SessionLocal: sessionmaker  # Session factory

def init_db() -> None:
    """Initialize database by creating all tables."""
    
def close_db() -> None:
    """Close database connections."""
    
def get_db() -> Generator[Session, None, None]:
    """Dependency function to get database session."""
    
@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for database session."""

# ORM Models
class User(Base):
    """User model for authentication and authorization."""
    __tablename__ = "users"
    
    id: int
    user_id: str
    username: str
    email: str
    password_hash: str
    roles: List[str]
    created_at: datetime
    updated_at: datetime

class Session(Base):
    """Session model for simulation sessions."""
    __tablename__ = "sessions"
    
    id: int
    session_id: str
    user_id: str
    state: str
    config: dict
    created_at: datetime
    updated_at: datetime
```

**Connection Pooling Configuration:**
- Pool size: 10 connections
- Max overflow: 20 connections
- Pre-ping: Enabled (verify connections before use)
- Pool recycle: 3600 seconds

### 4. Authentication and Authorization (services/auth_manager.py, services/authorization.py)

JWT-based authentication system with role-based access control.

**Key Responsibilities:**
- Generate and verify JWT access and refresh tokens
- Hash and verify passwords using bcrypt
- Manage token expiration and refresh
- Enforce role-based permissions
- Provide authentication middleware

**Interface:**

```python
class AuthManager:
    """JWT token and password management."""
    
    def __init__(self, db: Session):
        """Initialize with database session."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt."""
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify password against hash."""
    
    def create_access_token(self, user_id: str, roles: List[str]) -> str:
        """Create JWT access token."""
    
    def create_refresh_token(self, user_id: str) -> str:
        """Create JWT refresh token."""
    
    def verify_token(self, token: str, expected_type: str) -> TokenPayload:
        """Verify JWT token and extract payload."""
    
    def refresh_access_token(self, refresh_token: str) -> str:
        """Generate new access token from refresh token."""

class Permission(Enum):
    """Permission definitions."""
    SESSION_CREATE = "session:create"
    SESSION_READ = "session:read"
    SESSION_CONTROL = "session:control"
    SESSION_DELETE = "session:delete"
    USER_MANAGE = "user:manage"
    EXPORT_DATA = "export:data"

def require_permission(permission: Permission):
    """Dependency to require specific permission."""
    
def get_current_user(request: Request) -> TokenPayload:
    """Dependency to get current authenticated user."""
```

**Token Structure:**
- Access tokens: 30 minute expiration
- Refresh tokens: 7 day expiration
- Algorithm: HS256
- Payload includes: user_id, roles, token_type, exp, iat


### 5. Session Management (services/session_manager.py)

Manages simulation session lifecycle with Redis caching and PostgreSQL persistence.

**Key Responsibilities:**
- Create and configure simulation sessions
- Manage session state transitions (created → running → paused → stopped)
- Store session state in Redis for fast access
- Persist session metadata in PostgreSQL for durability
- Handle concurrent session access
- Clean up expired sessions

**Interface:**

```python
class SessionLifecycleState(Enum):
    """Session lifecycle states."""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"

class SessionManager:
    """Manages simulation session lifecycle."""
    
    def __init__(self, redis_client: redis.Redis, db_session_factory):
        """Initialize with Redis and database session factory."""
    
    async def create_session(self, request: SessionCreateRequest) -> str:
        """Create new simulation session."""
    
    async def get_session(self, session_id: str) -> SimulationSession:
        """Retrieve session by ID."""
    
    async def update_session_state(
        self, session_id: str, state: SessionLifecycleState
    ) -> None:
        """Update session state."""
    
    async def delete_session(self, session_id: str) -> None:
        """Delete session and clean up resources."""
    
    async def list_user_sessions(self, user_id: str) -> List[str]:
        """List all sessions for a user."""
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up sessions inactive for 24+ hours."""

class SimulationSession:
    """Represents an active simulation session."""
    
    session_id: str
    state: SessionLifecycleState
    config: dict
    created_at: datetime
    updated_at: datetime
    
    async def start(self) -> dict:
        """Start or resume simulation."""
    
    async def pause(self) -> dict:
        """Pause simulation."""
    
    async def stop(self) -> dict:
        """Stop simulation."""
    
    async def reset(self) -> dict:
        """Reset simulation to initial state."""
    
    async def get_state(self) -> dict:
        """Get current simulation state."""
```

**State Transition Rules:**
- CREATED → RUNNING (start)
- RUNNING → PAUSED (pause)
- PAUSED → RUNNING (start/resume)
- RUNNING → STOPPED (stop)
- PAUSED → STOPPED (stop)
- STOPPED → CREATED (reset)
- Any state → FAILED (on error)

**Caching Strategy:**
- Session state stored in Redis with 24-hour TTL
- Session metadata persisted in PostgreSQL
- Cache invalidation on state changes
- Lazy loading from database if not in cache

### 6. Task Queue (celery_app.py, tasks/)

Celery-based asynchronous task execution for long-running operations.

**Key Responsibilities:**
- Execute experimental tasks asynchronously
- Track task status and results
- Handle task timeouts and failures
- Support task cancellation
- Provide task result retrieval

**Interface:**

```python
# Celery Application
celery_app = Celery(
    "apgi_tasks",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Task Configuration
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    task_time_limit=3600,      # 1 hour hard limit
    task_soft_time_limit=3300,  # 55 minute soft limit
    result_expires=86400,       # 24 hour result expiration
)

# Task Definitions
@celery_app.task(name="experimental.attentional_blink")
def run_attentional_blink_task(session_id: str, config: dict) -> dict:
    """Execute attentional blink experiment."""

@celery_app.task(name="experimental.binocular_rivalry")
def run_binocular_rivalry_task(session_id: str, config: dict) -> dict:
    """Execute binocular rivalry experiment."""

@celery_app.task(name="experimental.change_blindness")
def run_change_blindness_task(session_id: str, config: dict) -> dict:
    """Execute change blindness experiment."""

# Task Registry
class TaskRegistry:
    """Registry of available experimental tasks."""
    
    @staticmethod
    def get_available_tasks() -> List[str]:
        """Get list of available task names."""
    
    @staticmethod
    def get_task_info(task_name: str) -> dict:
        """Get task metadata and parameters."""
```

**Task Execution Flow:**
1. Client submits task via API endpoint
2. API creates task record in database
3. Task queued to Celery via Redis
4. Worker picks up task from queue
5. Worker executes task with timeout
6. Worker stores result in Redis backend
7. Client polls for task status/result

### 7. Route Handlers (routes/)

FastAPI route handlers organized by resource type.

**Key Routes:**

```python
# Authentication Routes (auth.py)
POST   /v1/auth/login          # User login, returns access + refresh tokens
POST   /v1/auth/refresh        # Refresh access token
POST   /v1/auth/logout         # Logout (invalidate tokens)

# User Routes (users.py)
GET    /v1/users/me            # Get current user profile
PUT    /v1/users/me            # Update current user profile
POST   /v1/users               # Create new user (admin only)
GET    /v1/users/{user_id}     # Get user by ID (admin only)

# Session Routes (sessions.py)
POST   /v1/sessions            # Create new session
GET    /v1/sessions/{id}       # Get session details
POST   /v1/sessions/{id}/start # Start/resume session
POST   /v1/sessions/{id}/pause # Pause session
POST   /v1/sessions/{id}/stop  # Stop session
POST   /v1/sessions/{id}/reset # Reset session
DELETE /v1/sessions/{id}       # Delete session

# State Routes (state.py)
GET    /v1/sessions/{id}/state # Get current simulation state
GET    /v1/sessions/{id}/metrics # Get simulation metrics

# Task Routes (tasks.py)
POST   /v1/tasks               # Submit async task
GET    /v1/tasks/{task_id}     # Get task status
GET    /v1/tasks/{task_id}/result # Get task result
DELETE /v1/tasks/{task_id}     # Cancel task

# Export Routes (export.py)
GET    /v1/sessions/{id}/export/json # Export session as JSON
GET    /v1/sessions/{id}/export/csv  # Export session as CSV

# Health Routes (health.py)
GET    /health                 # Basic health check
GET    /health/ready           # Readiness probe (checks dependencies)
GET    /health/live            # Liveness probe

# Metrics Routes (metrics.py)
GET    /metrics                # Prometheus metrics

# Version Routes (version.py)
GET    /version                # API version info
GET    /deprecated             # List of deprecated endpoints
```

**Route Handler Pattern:**

```python
@router.post("/v1/sessions", response_model=SessionCreateResponse)
async def create_session(
    request: SessionCreateRequest,
    manager: SessionManager = Depends(get_session_manager),
    current_user: TokenPayload = Depends(get_current_user),
    _: None = Depends(require_permission(Permission.SESSION_CREATE)),
):
    """Create new simulation session."""
    session_id = await manager.create_session(request)
    return SessionCreateResponse(session_id=session_id, ...)
```

### 8. Middleware Components (middleware/)

**Authentication Middleware (authentication.py):**
- Extracts JWT token from Authorization header
- Verifies token signature and expiration
- Attaches user identity to request.state
- Returns 401 for invalid/expired tokens
- Skips public endpoints (/, /health, /docs, /auth/*)

**CSRF Middleware (csrf.py):**
- Generates CSRF tokens for sessions
- Validates CSRF tokens on state-changing requests (POST, PUT, DELETE)
- Stores tokens in secure HTTP-only cookies
- Validates X-CSRF-Token header matches cookie
- Returns 403 for CSRF validation failures

**Rate Limiting Middleware (rate_limiting.py):**
- Tracks request counts per user/IP in Redis
- Enforces configurable rate limits (default: 60 req/min)
- Returns 429 Too Many Requests when limit exceeded
- Includes Retry-After header in rate limit responses
- Supports different limits for different endpoints

**Request Logging Middleware (logging.py):**
- Logs all incoming requests with structured JSON
- Includes: method, path, status, duration, user_id, request_id
- Generates unique request ID for tracing
- Logs request/response bodies for debugging (configurable)
- Integrates with centralized logging systems

**Metrics Middleware (metrics.py):**
- Tracks Prometheus metrics for all requests
- Metrics: request_count, request_duration, active_requests, error_rate
- Labels: method, path, status_code
- Exposes metrics at /metrics endpoint
- Supports custom business metrics


## Data Models

### Database Schema

**Users Table:**
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    roles JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_user_id ON users(user_id);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
```

**Sessions Table:**
```sql
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(255) NOT NULL REFERENCES users(user_id),
    state VARCHAR(50) NOT NULL,
    config JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_session_id ON sessions(session_id);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_state ON sessions(state);
CREATE INDEX idx_sessions_created_at ON sessions(created_at);
```

**Tasks Table:**
```sql
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(255) UNIQUE NOT NULL,
    session_id VARCHAR(255) REFERENCES sessions(session_id),
    task_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    result JSONB,
    error TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tasks_task_id ON tasks(task_id);
CREATE INDEX idx_tasks_session_id ON tasks(session_id);
CREATE INDEX idx_tasks_status ON tasks(status);
```

### Pydantic Models

**Request Models:**

```python
class SessionCreateRequest(BaseModel):
    """Request to create a new session."""
    config: dict
    description: Optional[str] = None

class SessionActionRequest(BaseModel):
    """Request for session action (start/pause/stop)."""
    pass  # No body needed, action in URL

class LoginRequest(BaseModel):
    """User login request."""
    username: str
    password: str

class RefreshTokenRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str

class TaskSubmitRequest(BaseModel):
    """Request to submit async task."""
    task_name: str
    session_id: str
    config: dict
```

**Response Models:**

```python
class SessionCreateResponse(BaseModel):
    """Response for session creation."""
    session_id: str
    status: str
    created_at: datetime
    config: dict

class SessionResponse(BaseModel):
    """Response for session details."""
    session_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    config: dict
    description: Optional[str]

class SessionActionResponse(BaseModel):
    """Response for session action."""
    session_id: str
    status: str
    timestamp: datetime

class LoginResponse(BaseModel):
    """Response for successful login."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TaskResponse(BaseModel):
    """Response for task submission."""
    task_id: str
    status: str
    created_at: datetime

class TaskStatusResponse(BaseModel):
    """Response for task status."""
    task_id: str
    status: str
    result: Optional[dict]
    error: Optional[str]
    created_at: datetime
    updated_at: datetime

class HealthResponse(BaseModel):
    """Response for health check."""
    status: str
    timestamp: datetime
    version: str
    dependencies: Optional[dict]

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: ErrorDetail

class ErrorDetail(BaseModel):
    """Error detail structure."""
    code: str
    message: str
    timestamp: datetime
    details: Optional[dict]
```

### Redis Data Structures

**Session State Cache:**
```
Key: session:{session_id}:state
Type: Hash
TTL: 24 hours
Fields:
  - state: current state (running/paused/stopped)
  - config: JSON-encoded configuration
  - updated_at: last update timestamp
```

**Rate Limiting:**
```
Key: ratelimit:{user_id}:{minute}
Type: String (counter)
TTL: 60 seconds
Value: request count in current minute
```

**CSRF Tokens:**
```
Key: csrf:{session_id}
Type: String
TTL: 60 minutes
Value: CSRF token
```

**Task Results:**
```
Key: celery-task-meta-{task_id}
Type: Hash
TTL: 24 hours
Fields: (managed by Celery)
  - status: task status
  - result: JSON-encoded result
  - traceback: error traceback if failed
```


## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property Reflection

After analyzing all acceptance criteria, several properties can be consolidated to avoid redundancy:

**Consolidated Properties:**
- Multiple CORS-related properties (7.3, 7.4) can be combined into a single comprehensive CORS header property
- Multiple error response properties (19.2-19.7) can be consolidated into fewer comprehensive error handling properties
- Multiple logging properties (10.1, 10.2, 10.3, 10.7) can be combined into comprehensive logging properties
- Multiple authentication/authorization properties (8.4, 19.3, 19.4) can be consolidated
- Multiple health check examples (9.1-9.7) are specific test cases, not separate properties
- Multiple backward compatibility properties (11.2-11.4) can be combined into a single compatibility property

### Core Properties

**Property 1: Configuration Environment Variable Override**
*For any* configuration setting, when an environment variable is set for that setting, the environment variable value should override the default value.
**Validates: Requirements 2.2**

**Property 2: Configuration Validation Error Logging**
*For any* configuration validation failure, the system should log the specific configuration key and validation error before exiting.
**Validates: Requirements 2.5**

**Property 3: Database Migration Round-Trip**
*For any* database migration, running upgrade followed by downgrade should return the database to its original state.
**Validates: Requirements 3.6**

**Property 4: CORS Headers on All Responses**
*For any* HTTP response when CORS is enabled, the response should include Access-Control-Allow-Origin, Access-Control-Allow-Methods, and Access-Control-Allow-Headers.
**Validates: Requirements 7.3, 7.4**

**Property 5: JWT Token Validation on Protected Routes**
*For any* protected route, requests without valid JWT tokens should be rejected with 401 Unauthorized status.
**Validates: Requirements 8.4**

**Property 6: Password Hashing with Bcrypt**
*For any* password, hashing it with bcrypt should produce a hash that can be verified against the original password, and the hash should not be verifiable against any other password.
**Validates: Requirements 8.7**

**Property 7: Structured JSON Logging Format**
*For any* log message, it should be valid JSON containing at minimum: timestamp, level, message, and component fields.
**Validates: Requirements 10.1**

**Property 8: Request Logging Completeness**
*For any* HTTP request, a log entry should be created containing method, path, status_code, response_time, and request_id fields.
**Validates: Requirements 10.2**

**Property 9: Request ID Propagation**
*For any* HTTP request, all log messages generated during that request should contain the same request_id value.
**Validates: Requirements 10.3**

**Property 10: Error Logging with Context**
*For any* error that occurs during request processing, the error log should contain the exception type, message, stack trace, and request context.
**Validates: Requirements 10.7**

**Property 11: Backward Compatibility - Request Format**
*For any* valid request accepted by the Legacy_API, the Standalone_API should accept the same request format and return a successful response.
**Validates: Requirements 11.2**

**Property 12: Backward Compatibility - Response Format**
*For any* request, the response schema from the Standalone_API should match the response schema from the Legacy_API (same fields, same types).
**Validates: Requirements 11.3**

**Property 13: Backward Compatibility - Status Codes**
*For any* request, the HTTP status code returned by the Standalone_API should match the status code returned by the Legacy_API for the same request.
**Validates: Requirements 11.4**

**Property 14: Task Status Retrieval**
*For any* submitted task, querying the task status by task_id should return the current status (pending, running, completed, or failed).
**Validates: Requirements 15.4**

**Property 15: Task Result Retrieval**
*For any* completed task, querying the task result by task_id should return the result data that was produced by the task execution.
**Validates: Requirements 15.5**

**Property 16: Task Serialization Round-Trip**
*For any* task with parameters and result, serializing to JSON and deserializing should preserve the task data without loss.
**Validates: Requirements 15.8**

**Property 17: Deprecation Headers on Deprecated Endpoints**
*For any* endpoint marked as deprecated, responses should include a Deprecation header with deprecation information.
**Validates: Requirements 16.3, 16.6**

**Property 18: Deprecated Endpoint Logging**
*For any* request to a deprecated endpoint, a log entry should be created indicating the endpoint path and deprecation status.
**Validates: Requirements 16.4**

**Property 19: Export Authorization**
*For any* user attempting to export session data, they should only be able to export sessions that belong to them (user_id matches).
**Validates: Requirements 17.3**

**Property 20: Export Metadata Completeness**
*For any* exported session, the export should include session_id, created_at, updated_at, config, and state fields.
**Validates: Requirements 17.4**

**Property 21: Export Content-Type Headers**
*For any* export request, the response should include appropriate Content-Type (application/json or text/csv) and Content-Disposition headers.
**Validates: Requirements 17.6**

**Property 22: Session Concurrent Modification Prevention**
*For any* session, when two concurrent requests attempt to modify the session state, only one should succeed and the other should receive a conflict error.
**Validates: Requirements 18.8**

**Property 23: Request Validation Error Response**
*For any* request with invalid payload, the response should be 422 Unprocessable Entity with a detailed error message indicating which fields failed validation.
**Validates: Requirements 19.1, 19.2**

**Property 24: Authentication Failure Response**
*For any* request with invalid or missing authentication, the response should be 401 Unauthorized with a WWW-Authenticate header.
**Validates: Requirements 19.3**

**Property 25: Authorization Failure Response**
*For any* request where the authenticated user lacks required permissions, the response should be 403 Forbidden with an explanation.
**Validates: Requirements 19.4**

**Property 26: Not Found Response**
*For any* request for a non-existent resource, the response should be 404 Not Found.
**Validates: Requirements 19.5**

**Property 27: Server Error Response and Logging**
*For any* unhandled exception during request processing, the response should be 500 Internal Server Error and the full error should be logged with stack trace.
**Validates: Requirements 19.6**

**Property 28: Sensitive Information Exclusion from Errors**
*For any* error response sent to clients, the response should not contain sensitive information such as database connection strings, internal file paths, or stack traces.
**Validates: Requirements 19.7**

**Property 29: Response Compression for Large Responses**
*For any* response with body size greater than 1KB, when the client supports gzip encoding, the response should be compressed.
**Validates: Requirements 20.1**

**Property 30: Request Size Limiting**
*For any* request with body size exceeding the configured limit (default 10MB), the request should be rejected with 413 Payload Too Large before processing.
**Validates: Requirements 20.2**


## Error Handling

### Error Categories

**1. Configuration Errors (Startup)**
- Missing required environment variables
- Invalid configuration values
- Insecure production settings
- Action: Log specific error, exit with non-zero code

**2. Authentication Errors (Runtime)**
- Missing JWT token
- Invalid JWT token signature
- Expired JWT token
- Action: Return 401 Unauthorized with WWW-Authenticate header

**3. Authorization Errors (Runtime)**
- Insufficient permissions for operation
- Attempting to access another user's resources
- Action: Return 403 Forbidden with explanation

**4. Validation Errors (Runtime)**
- Invalid request payload
- Missing required fields
- Type mismatches
- Action: Return 422 Unprocessable Entity with field-level errors

**5. Resource Errors (Runtime)**
- Session not found
- User not found
- Task not found
- Action: Return 404 Not Found

**6. State Errors (Runtime)**
- Invalid state transition (e.g., pausing a stopped session)
- Concurrent modification conflict
- Action: Return 409 Conflict with current state

**7. Dependency Errors (Runtime)**
- Database connection failure
- Redis connection failure
- Celery broker unavailable
- Action: Return 503 Service Unavailable, log error, trigger alert

**8. Rate Limiting Errors (Runtime)**
- Too many requests from user/IP
- Action: Return 429 Too Many Requests with Retry-After header

**9. Internal Errors (Runtime)**
- Unhandled exceptions
- Programming errors
- Action: Return 500 Internal Server Error, log full error with stack trace, trigger alert

### Error Response Format

All error responses follow a consistent JSON structure:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "timestamp": "2024-01-15T10:30:00Z",
    "details": {
      "field": "Additional context",
      "request_id": "req_abc123"
    }
  }
}
```

### Error Handling Strategy

**Fail Fast:**
- Configuration errors prevent startup
- Dependency errors during startup prevent startup
- Invalid requests rejected immediately

**Graceful Degradation:**
- Redis unavailable: Disable rate limiting, continue serving requests
- Celery unavailable: Return 503 for task submission, continue serving other endpoints

**Error Propagation:**
- Database errors: Rollback transaction, return 500
- External service errors: Return 503 with retry guidance
- Validation errors: Return 422 with field-level details

**Logging:**
- All errors logged with full context
- Error rate monitored for alerting
- Stack traces logged server-side, never sent to clients

### Circuit Breaker Pattern

For external dependencies (database, Redis, Celery):
- Track failure rate over sliding window
- Open circuit after threshold failures (e.g., 5 failures in 1 minute)
- Return 503 immediately when circuit open
- Attempt recovery after cooldown period (e.g., 30 seconds)
- Close circuit after successful health check

## Testing Strategy

### Dual Testing Approach

The testing strategy employs both unit tests and property-based tests as complementary approaches:

**Unit Tests:**
- Specific examples demonstrating correct behavior
- Edge cases and boundary conditions
- Integration points between components
- Error conditions and failure scenarios
- Mock external dependencies for isolation

**Property-Based Tests:**
- Universal properties that hold for all inputs
- Comprehensive input coverage through randomization
- Minimum 100 iterations per property test
- Each test references its design document property
- Tag format: `Feature: api-migration, Property N: [property text]`

### Testing Layers

**1. Unit Tests (tests/unit/)**

Test individual components in isolation:
- Configuration loading and validation
- JWT token generation and verification
- Password hashing and verification
- Session state transitions
- Request/response serialization
- Middleware behavior

Example unit tests:
```python
def test_config_loads_from_env():
    """Test that configuration loads from environment variables."""
    
def test_jwt_token_expires():
    """Test that JWT tokens expire after configured time."""
    
def test_password_hash_verification():
    """Test that password hashes can be verified."""
    
def test_session_state_transition_created_to_running():
    """Test valid state transition from created to running."""
    
def test_invalid_state_transition_raises_error():
    """Test that invalid state transitions raise errors."""
```

**2. Integration Tests (tests/integration/)**

Test component interactions:
- API endpoint to database flow
- Authentication middleware to route handler flow
- Session manager to Redis and PostgreSQL
- Celery task submission to worker execution
- Health checks verifying all dependencies

Example integration tests:
```python
async def test_create_session_end_to_end():
    """Test session creation from API request to database persistence."""
    
async def test_authentication_flow():
    """Test login, token generation, and authenticated request."""
    
async def test_task_submission_and_retrieval():
    """Test submitting task, checking status, and retrieving result."""
    
async def test_health_check_with_dependencies():
    """Test health check verifies database and Redis connectivity."""
```

**3. Property-Based Tests (tests/property/)**

Test universal properties across many generated inputs:

```python
from hypothesis import given, strategies as st

@given(st.text(min_size=1))
def test_property_1_config_env_override(config_key):
    """
    Feature: api-migration, Property 1: Configuration Environment Variable Override
    For any configuration setting, environment variable should override default.
    """
    
@given(st.text(min_size=8))
def test_property_6_password_hashing(password):
    """
    Feature: api-migration, Property 6: Password Hashing with Bcrypt
    For any password, bcrypt hash should verify correctly.
    """
    
@given(st.dictionaries(st.text(), st.text()))
def test_property_16_task_serialization_roundtrip(task_data):
    """
    Feature: api-migration, Property 16: Task Serialization Round-Trip
    For any task data, JSON serialization round-trip should preserve data.
    """
```

### Test Configuration

**Property-Based Test Settings:**
- Library: Hypothesis (Python)
- Iterations: 100 minimum per property
- Seed: Fixed for reproducibility in CI
- Shrinking: Enabled to find minimal failing examples
- Deadline: 1000ms per example

**Test Database:**
- Separate test database instance
- Reset between test runs
- Use transactions for test isolation
- Seed with test fixtures

**Test Redis:**
- Separate Redis database (db=15)
- Flush between test runs
- Mock for unit tests, real for integration tests

**Test Coverage Goals:**
- Line coverage: 80% minimum
- Branch coverage: 75% minimum
- Critical paths: 100% coverage
- Error handling: 100% coverage

### Continuous Integration

**Pre-commit Checks:**
- Code formatting (black, isort)
- Linting (flake8, mypy)
- Unit tests
- Fast property tests (10 iterations)

**CI Pipeline:**
- Full unit test suite
- Full integration test suite
- Full property test suite (100 iterations)
- Coverage report generation
- Security scanning (bandit)
- Dependency vulnerability scanning

**Test Environments:**
- Development: Local Docker Compose
- CI: GitHub Actions with Docker services
- Staging: Kubernetes cluster with test data
- Production: Smoke tests only (health checks)


## Deployment Architecture

### Local Development

**Docker Compose Setup:**
```yaml
services:
  postgres:
    image: postgres:14-alpine
    environment:
      POSTGRES_DB: apgi_api_dev
      POSTGRES_USER: apgi_dev
      POSTGRES_PASSWORD: dev_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_dev_data:/var/lib/postgresql/data
      
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_dev_data:/data
      
  api:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    environment:
      ENVIRONMENT: development
      DATABASE_URL: postgresql://apgi_dev:dev_password@postgres:5432/apgi_api_dev
      REDIS_URL: redis://redis:6379/0
    volumes:
      - ./app:/app/app
    depends_on:
      - postgres
      - redis
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
      
  celery_worker:
    build:
      context: .
      dockerfile: Dockerfile.dev
    environment:
      ENVIRONMENT: development
      DATABASE_URL: postgresql://apgi_dev:dev_password@postgres:5432/apgi_api_dev
      REDIS_URL: redis://redis:6379/0
      CELERY_BROKER_URL: redis://redis:6379/1
      CELERY_RESULT_BACKEND: redis://redis:6379/2
    volumes:
      - ./app:/app/app
    depends_on:
      - postgres
      - redis
    command: celery -A app.celery_app worker --loglevel=info
```

**Development Workflow:**
1. Clone repository
2. Copy `.env.example` to `.env`
3. Run `docker-compose up`
4. API available at http://localhost:8000
5. API docs at http://localhost:8000/docs
6. Run migrations: `docker-compose exec api alembic upgrade head`

### Production Deployment

**Multi-Stage Dockerfile:**
```dockerfile
# Build stage
FROM python:3.11-slim as builder
WORKDIR /app
RUN apt-get update && apt-get install -y gcc postgresql-client
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim
WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 apgi && chown -R apgi:apgi /app
USER apgi

# Copy dependencies from builder
COPY --from=builder --chown=apgi:apgi /root/.local /home/apgi/.local
ENV PATH=/home/apgi/.local/bin:$PATH

# Copy application code
COPY --chown=apgi:apgi app/ ./app/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Kubernetes Deployment:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: apgi-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: apgi-api
  template:
    metadata:
      labels:
        app: apgi-api
    spec:
      containers:
      - name: api
        image: apgi-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: apgi-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: apgi-secrets
              key: redis-url
        - name: JWT_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: apgi-secrets
              key: jwt-secret
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: apgi-api
spec:
  selector:
    app: apgi-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: apgi-celery-worker
spec:
  replicas: 2
  selector:
    matchLabels:
      app: apgi-celery-worker
  template:
    metadata:
      labels:
        app: apgi-celery-worker
    spec:
      containers:
      - name: worker
        image: apgi-api:latest
        command: ["celery", "-A", "app.celery_app", "worker", "--loglevel=info"]
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: apgi-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: apgi-secrets
              key: redis-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
```

### Scaling Strategy

**Horizontal Scaling:**
- API instances: Scale based on CPU/memory usage
- Celery workers: Scale based on queue depth
- Database: Read replicas for read-heavy workloads
- Redis: Redis Cluster for high availability

**Load Balancing:**
- Round-robin for API instances
- Sticky sessions not required (stateless API)
- Health check-based routing
- Automatic failover for unhealthy instances

**Auto-scaling Rules:**
- Scale up API when CPU > 70% for 5 minutes
- Scale down API when CPU < 30% for 10 minutes
- Scale up workers when queue depth > 100 for 5 minutes
- Minimum 2 API instances, maximum 10
- Minimum 1 worker, maximum 5

### Monitoring and Observability

**Metrics Collection:**
- Prometheus scrapes /metrics endpoint
- Grafana dashboards for visualization
- Key metrics:
  - Request rate (requests/second)
  - Response time (p50, p95, p99)
  - Error rate (errors/second)
  - Active sessions
  - Queue depth
  - Database connection pool usage
  - Cache hit rate

**Logging:**
- Structured JSON logs to stdout
- Log aggregation with ELK stack or CloudWatch
- Log levels: DEBUG (dev), INFO (staging), WARNING (prod)
- Request tracing with correlation IDs
- Error logs trigger alerts

**Alerting:**
- Error rate > 10 errors/minute for 5 minutes
- Response time p95 > 1000ms for 5 minutes
- Health check failures
- Database connection failures
- Redis connection failures
- Celery worker failures
- Disk space < 10%

**Tracing:**
- Distributed tracing with OpenTelemetry
- Trace requests across API, database, Redis, Celery
- Identify slow queries and bottlenecks
- Visualize request flow

### Security Considerations

**Network Security:**
- API behind load balancer with TLS termination
- Database and Redis in private subnet
- Security groups restrict access
- VPC peering for cross-region communication

**Application Security:**
- JWT tokens with short expiration
- CSRF protection for state-changing operations
- Rate limiting per user/IP
- Input validation on all endpoints
- SQL injection prevention (parameterized queries)
- XSS prevention (output encoding)
- Secrets in environment variables, never in code

**Data Security:**
- Passwords hashed with bcrypt
- Database encryption at rest
- TLS for all network communication
- Audit logging for sensitive operations
- Regular security scanning (Snyk, Bandit)

**Compliance:**
- GDPR: User data deletion support
- SOC 2: Audit logging, access controls
- HIPAA: Encryption, access logging (if applicable)

### Backup and Disaster Recovery

**Database Backups:**
- Automated daily backups
- Point-in-time recovery (PITR)
- Backup retention: 30 days
- Cross-region backup replication
- Regular restore testing

**Redis Backups:**
- RDB snapshots every 6 hours
- AOF for durability
- Backup retention: 7 days
- Redis Cluster for high availability

**Disaster Recovery:**
- RTO (Recovery Time Objective): 1 hour
- RPO (Recovery Point Objective): 15 minutes
- Multi-region deployment for critical systems
- Automated failover procedures
- Regular DR drills

### Migration Strategy

**Phase 1: Parallel Deployment**
- Deploy standalone API alongside legacy API
- Route 10% of traffic to standalone API
- Monitor for errors and performance issues
- Gradually increase traffic to 50%, then 100%

**Phase 2: Data Migration**
- Migrate existing sessions to new database schema
- Verify data integrity
- Keep legacy API running for rollback

**Phase 3: Cutover**
- Route 100% traffic to standalone API
- Monitor for 48 hours
- Decommission legacy API if stable

**Rollback Plan:**
- Keep legacy API running for 2 weeks
- Database backups before migration
- Feature flag to route traffic back to legacy
- Automated rollback on error rate threshold

