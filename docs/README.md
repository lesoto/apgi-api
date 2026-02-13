# APGI API

This is the REST API for the APGI consciousness modeling system. The API provides a complete interface for managing simulation sessions, executing experimental tasks, and accessing consciousness modeling results.

## Features

- **Session Management**: Create, control, and monitor simulation sessions
- **Asynchronous Task Execution**: Run long-running experiments via Celery task queue
- **JWT Authentication**: Secure API access with role-based permissions
- **Data Export**: Export session data in JSON and CSV formats
- **Health Monitoring**: Comprehensive health checks and Prometheus metrics
- **Horizontal Scaling**: Stateless design supports multiple API instances
- **Production Ready**: Docker deployment, database migrations, graceful shutdown

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Docker and Docker Compose (recommended for local development)

### Local Development Setup (Docker Compose - Recommended)

The fastest way to get started is using Docker Compose, which sets up all services automatically:

1. **Clone the repository and navigate to the standalone-api directory:**

   ```bash
   cd standalone-api
   ```

2. **Start all services:**

   ```bash
   docker-compose -f deployment/docker-compose.yml up
   ```

3. **Access the API:**

- API: <http://localhost:8000>
- Interactive docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>
- Metrics: <http://localhost:8000/metrics>

The Docker Compose setup includes:

- API server with hot-reload
- PostgreSQL database
- Redis cache
- Celery worker for async tasks

### Local Development Setup (Manual)

If you prefer to run services manually:

1. **Copy environment configuration:**

   ```bash
   cp .env.development .env
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # For development tools
   ```

3. **Start PostgreSQL and Redis:**

   ```bash
   # Using Docker Compose for just the data services
   docker-compose -f deployment/docker-compose.yml up -d postgres redis
   ```

4. **Run database migrations:**

   ```bash
   alembic upgrade head
   ```

5. **Start the API server:**

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

6. **Start Celery worker (in a separate terminal):**

   ```bash
   celery -A app.celery_app worker --loglevel=info
   ```

7. **Access the API:**

- API: <http://localhost:8000>
- Interactive docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

## API Endpoints

### Authentication

- `POST /v1/auth/login` - User login (returns access and refresh tokens)
- `POST /v1/auth/refresh` - Refresh access token
- `POST /v1/auth/logout` - Logout and invalidate tokens

### Sessions

- `POST /v1/sessions` - Create new simulation session
- `GET /v1/sessions/{id}` - Get session details
- `POST /v1/sessions/{id}/start` - Start or resume session
- `POST /v1/sessions/{id}/pause` - Pause session
- `POST /v1/sessions/{id}/stop` - Stop session
- `POST /v1/sessions/{id}/reset` - Reset session to initial state
- `DELETE /v1/sessions/{id}` - Delete session

### State Queries

- `GET /v1/sessions/{id}/state` - Get current simulation state
- `GET /v1/sessions/{id}/metrics` - Get simulation metrics

### Async Tasks

- `POST /v1/tasks` - Submit asynchronous task
- `GET /v1/tasks/{task_id}` - Get task status
- `GET /v1/tasks/{task_id}/result` - Get task result
- `DELETE /v1/tasks/{task_id}` - Cancel task

### Data Export

- `GET /v1/sessions/{id}/export/json` - Export session as JSON
- `GET /v1/sessions/{id}/export/csv` - Export session as CSV

### Health & Monitoring

- `GET /health` - Basic health check
- `GET /health/ready` - Readiness probe (checks dependencies)
- `GET /health/live` - Liveness probe
- `GET /metrics` - Prometheus metrics
- `GET /version` - API version information

For detailed API documentation, visit <http://localhost:8000/docs> when the server is running.

## Configuration

The API uses environment variables for configuration. See `.env.example` for all available options.

### Environment Files

- `.env.example` - Template with all configuration options documented
- `.env.development` - Development defaults (safe for local development)
- `.env.production` - Production template (requires configuration)

### Key Configuration Variables

|Variable|Description|Required|
|----------|-------------|----------|
|`ENVIRONMENT`|Environment: development, staging, or production|Yes|
|`DATABASE_URL`|PostgreSQL connection string|Yes|
|`REDIS_URL`|Redis connection string|Yes|
|`JWT_SECRET_KEY`|Secret key for JWT token signing (32+ chars)|Yes|
|`CORS_ORIGINS`|Comma-separated list of allowed origins|Yes (production)|

### Environment-Specific Behavior

**Development:**

- Debug logging enabled
- Auto-reload on code changes
- Relaxed security validation
- Default JWT secret provided (with warning)

**Production:**

- Strict security validation
- Requires explicit configuration
- Fails fast on missing/insecure settings
- No default secrets

## Project Structure

```text
standalone-api/
├── app/                    # Application code
│   ├── config.py          # Configuration management
│   ├── main.py            # FastAPI application entry point
│   ├── database/          # Database models and connection
│   ├── middleware/        # Middleware components
│   ├── models/            # Pydantic request/response models
│   ├── routes/            # API route handlers
│   ├── services/          # Business logic services
│   ├── tasks/             # Celery async tasks
│   └── utils/             # Utility functions
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── property/         # Property-based tests
├── deployment/           # Deployment configuration
│   ├── Dockerfile        # Production Docker image
│   └── docker-compose.yml # Local development orchestration
├── docs/                 # Documentation
└── scripts/              # Utility scripts
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test types
pytest tests/unit/          # Unit tests only
pytest tests/integration/   # Integration tests only
pytest tests/property/      # Property-based tests only

# Run specific test file
pytest tests/unit/test_config.py

# Run tests with verbose output
pytest -v
```

### Code Quality

```bash
# Format code
black app/ tests/

# Sort imports
isort app/ tests/

# Lint code
flake8 app/ tests/

# Type checking
mypy app/
```

### Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history

# View current version
alembic current
```

### Utility Scripts

The `scripts/` directory contains helpful utilities:

```bash
# Start development environment
./scripts/start.sh          # Linux/Mac
./scripts/start.ps1         # Windows

# Run database migrations
./scripts/migrate.sh        # Linux/Mac
./scripts/migrate.ps1       # Windows

# Check API health
./scripts/health_check.sh   # Linux/Mac
./scripts/health_check.ps1  # Windows
```

## Deployment

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed deployment instructions.

### Docker Deployment

```bash
# Build production image
docker build -t apgi-api:latest -f deployment/Dockerfile .

# Run with Docker Compose
docker-compose -f deployment/docker-compose.yml up
```

## Documentation

- [Configuration Guide](docs/CONFIGURATION.md) - Complete configuration reference
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment instructions
- [Migration Guide](docs/MIGRATION.md) - Migrating from legacy API
- [Troubleshooting Guide](docs/TROUBLESHOOTING.md) - Common issues and solutions
- [API Documentation](<http://localhost:8000/docs>) - Interactive API docs (when server is running)

## Architecture

The standalone API follows a layered architecture:

- **Routes Layer**: FastAPI route handlers for HTTP endpoints
- **Services Layer**: Business logic and orchestration
- **Database Layer**: SQLAlchemy ORM models and connection management
- **Middleware Stack**: Authentication, CORS, rate limiting, logging, metrics
- **Task Queue**: Celery workers for asynchronous task execution
- **Cache Layer**: Redis for session state and rate limiting

Key design principles:

- Stateless API instances for horizontal scaling
- Request-scoped database sessions
- JWT-based authentication with role-based access control
- Structured JSON logging for observability
- Graceful shutdown with in-flight request completion

## Security

- **Authentication**: JWT tokens with 30-minute expiration
- **Authorization**: Role-based access control (RBAC)
- **CSRF Protection**: Token validation for state-changing operations
- **Rate Limiting**: Configurable per-user/IP limits
- **Input Validation**: Pydantic schema validation on all requests
- **Password Hashing**: Bcrypt with appropriate cost factor
- **Secrets Management**: Environment variables, never in code

## Monitoring

The API exposes comprehensive monitoring capabilities:

- **Health Checks**: `/health`, `/health/ready`, `/health/live`
- **Metrics**: Prometheus metrics at `/metrics`
- **Structured Logging**: JSON logs with request IDs for tracing
- **Error Tracking**: Automatic error logging with context

Key metrics tracked:

- Request rate and response times (p50, p95, p99)
- Error rates by endpoint
- Active sessions and tasks
- Database connection pool usage
- Cache hit rates

## Troubleshooting

### Common Issues

**API won't start:**

- Check that PostgreSQL and Redis are running
- Verify environment variables are set correctly
- Check logs for configuration validation errors

**Database connection errors:**

- Verify `DATABASE_URL` is correct
- Ensure PostgreSQL is accessible from the API container
- Check database credentials

**Authentication failures:**

- Verify `JWT_SECRET_KEY` is set and matches across instances
- Check token expiration times
- Ensure clock synchronization across servers

For more detailed troubleshooting, see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Contributing

### Development Workflow

1. Create a feature branch from `main`
2. Make your changes with tests
3. Run code quality checks: `black`, `isort`, `flake8`, `mypy`
4. Run test suite: `pytest`
5. Submit pull request with description

### Testing Requirements

- Unit tests for new functions and classes
- Integration tests for API endpoints
- Property-based tests for universal properties
- Minimum 80% code coverage

## License

Copyright © 2024 APGI System
