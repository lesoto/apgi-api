# Utility Scripts

## start.sh / start.ps1

Development environment startup script that:

- Checks for required dependencies (Docker, Docker Compose)
- Creates `.env.development` from `.env.example` if needed
- Starts all Docker services (PostgreSQL, Redis, API, Celery worker)
- Waits for services to become healthy
- Runs database migrations
- Displays service URLs and useful commands

**Usage:**

```bash
# Linux/macOS/Git Bash
./scripts/start.sh

# Windows PowerShell
.\scripts\start.ps1
```

**Requirements:**

- Docker
- Docker Compose

### migrate.sh / migrate.ps1

Database migration script that:

- Runs Alembic migrations with error handling
- Auto-detects whether to run locally or in Docker
- Supports custom migration targets
- Provides helpful error messages

**Usage:**

```bash
# Linux/macOS/Git Bash
./scripts/migrate.sh [target] [mode]

# Windows PowerShell
.\scripts\migrate.ps1 [target] [mode]

# Examples:
./scripts/migrate.sh                    # Migrate to latest (head)
./scripts/migrate.sh head docker        # Force Docker mode
./scripts/migrate.sh +1                 # Migrate one version forward
./scripts/migrate.sh -1                 # Migrate one version backward
./scripts/migrate.sh base               # Downgrade to base
```

**Parameters:**

- `target` (optional): Migration target (default: `head`)
  - `head` - Latest migration
  - `+1` / `-1` - Relative migration
  - `<revision>` - Specific revision
  - `base` - Downgrade to base
- `mode` (optional): Execution mode (default: `auto`)
  - `auto` - Auto-detect (prefer Docker if running)
  - `docker` - Force Docker execution
  - `local` - Force local execution

### health_check.sh / health_check.ps1

Health check script for monitoring that:

- Checks the API health endpoint
- Returns appropriate exit codes for monitoring systems
- Supports custom URLs and timeouts
- Provides verbose output for debugging

**Usage:**

```bash
# Linux/macOS/Git Bash
./scripts/health_check.sh [OPTIONS]

# Windows PowerShell
.\scripts\health_check.ps1 [OPTIONS]

# Examples:
./scripts/health_check.sh                                    # Check localhost:8000
./scripts/health_check.sh --url http://api.example.com:8000  # Custom URL
./scripts/health_check.sh --endpoint /health/live            # Custom endpoint
./scripts/health_check.sh --timeout 5 --verbose              # 5s timeout, verbose
./scripts/health_check.sh --quiet                            # Silent mode (monitoring)
```

**Options:**

- `-u, --url URL` / `-Url URL`: API base URL (default: `http://localhost:8000`)
- `-e, --endpoint PATH` / `-Endpoint PATH`: Health endpoint path (default: `/health/ready`)
- `-t, --timeout SECONDS` / `-Timeout SECONDS`: Request timeout (default: `10`)
- `-v, --verbose` / `-Verbose`: Enable verbose output
- `-q, --quiet` / `-Quiet`: Suppress all output (only exit codes)
- `-h, --help` / `-Help`: Show help message

**Exit Codes:**

- `0` - Service is healthy
- `1` - Service is unhealthy
- `2` - Connection error or timeout

**Environment Variables:**

- `API_URL` - API base URL
- `HEALTH_ENDPOINT` - Health endpoint path
- `TIMEOUT` - Request timeout in seconds
- `VERBOSE` - Enable verbose output (`true`/`false`)
- `QUIET` - Suppress output (`true`/`false`)

### seed.sh / seed.ps1

Database seeding script that:

- Seeds the database with test data for development and testing
- Supports different data types (users, sessions, tasks)
- Auto-detects whether to run locally or in Docker
- Provides force reseeding option

**Usage:**

```bash
# Linux/macOS/Git Bash
./scripts/seed.sh [COMMAND] [OPTIONS]

# Windows PowerShell
.\scripts\seed.ps1 [COMMAND] [OPTIONS]

# Examples:
./scripts/seed.sh users                    # Seed users in development
./scripts/seed.sh all --env test           # Seed all data for test environment
./scripts/seed.sh sessions --mode docker   # Seed sessions using Docker
./scripts/seed.sh all --force              # Force reseed all data
```

**Commands:**

- `users` - Seed user accounts
- `sessions` - Seed session data
- `tasks` - Seed task data
- `all` - Seed all data types (default)

**Options:**

- `-e, --env ENV` / `-Env ENV`: Environment (development, staging, test) [default: development]
- `-m, --mode MODE` / `-Mode MODE`: Execution mode (docker, local) [default: auto]
- `-f, --force` / `-Force`: Force reseeding (drop existing data)
- `-h, --help` / `-Help`: Show help message

**Environment Variables:**

- `SEED_USERS_COUNT` - Number of users to create [default: 10]
- `SEED_SESSIONS_COUNT` - Number of sessions per user [default: 5]
- `SEED_TASKS_COUNT` - Number of tasks per session [default: 3]

### ci_cd.sh / ci_cd.ps1

CI/CD pipeline script that:

- Runs tests, linting, and builds
- Handles deployment to staging and production
- Supports promotion and rollback operations
- Provides health checks and cleanup utilities

**Usage:**

```bash
# Linux/macOS/Git Bash
./scripts/ci_cd.sh [COMMAND] [OPTIONS]

# Windows PowerShell
.\scripts\ci_cd.ps1 [COMMAND] [OPTIONS]

# Examples:
./scripts/ci_cd.sh test                    # Run all tests
./scripts/ci_cd.sh lint                    # Run linting checks
./scripts/ci_cd.sh build                   # Build Docker images
./scripts/ci_cd.sh deploy --env staging    # Deploy to staging
./scripts/ci_cd.sh promote                 # Promote staging to production
./scripts/ci_cd.sh rollback --env production # Rollback production
./scripts/ci_cd.sh health --env staging    # Check staging health
```

**Commands:**

- `test` - Run all tests (unit, integration, property-based)
- `lint` - Run code linting and formatting checks
- `build` - Build Docker images
- `deploy` - Deploy to staging environment
- `promote` - Promote staging to production
- `rollback` - Rollback to previous version
- `health` - Run health checks on deployed service
- `cleanup` - Clean up old Docker images and containers

**Options:**

- `-e, --env ENV` / `-Env ENV`: Target environment (staging, production) [default: staging]
- `-v, --version VER` / `-Version VER`: Version tag for deployment
- `-f, --force` / `-Force`: Force operation without confirmation
- `-d, --dry-run` / `-DryRun`: Show what would be done without executing
- `-h, --help` / `-Help`: Show help message

**Environment Variables:**

- `CI_ENVIRONMENT` - Target environment (staging/production)
- `DOCKER_REGISTRY` - Docker registry URL
- `DOCKER_USERNAME` - Docker registry username
- `DOCKER_PASSWORD` - Docker registry password
- `DEPLOY_VERSION` - Version tag for deployment

### perf_test.sh / perf_test.ps1

Performance testing script that:

- Runs load, stress, spike, and soak tests
- Measures response times and throughput
- Generates JSON results with statistics
- Supports custom concurrency and duration

**Usage:**

```bash
# Linux/macOS/Git Bash
./scripts/perf_test.sh [TEST_TYPE] [OPTIONS]

# Windows PowerShell
.\scripts\perf_test.ps1 [TEST_TYPE] [OPTIONS]

# Examples:
./scripts/perf_test.sh load                           # Run load test for 60 seconds
./scripts/perf_test.sh stress --concurrency 50        # Run stress test with 50 concurrent users
./scripts/perf_test.sh spike --duration 30            # Run spike test for 30 seconds
./scripts/perf_test.sh all --url http://api.example.com --output results.json
```

**Test Types:**

- `load` - Run load testing with concurrent requests
- `stress` - Run stress testing to find breaking points
- `spike` - Run spike testing with sudden traffic bursts
- `soak` - Run soak testing for extended periods
- `all` - Run all test types (default)

**Options:**

- `-u, --url URL` / `-Url URL`: API base URL [default: http://localhost:8000]
- `-d, --duration SEC` / `-Duration SEC`: Test duration in seconds [default: 60]
- `-c, --concurrency N` / `-Concurrency N`: Number of concurrent users [default: 10]
- `-r, --rate N` / `-Rate N`: Request rate per second [default: 20]
- `-t, --timeout SEC` / `-Timeout SEC`: Request timeout [default: 10]
- `-o, --output FILE` / `-Output FILE`: Output file for results [default: perf_results.json]
- `-v, --verbose` / `-Verbose`: Enable verbose output
- `-h, --help` / `-Help`: Show help message

**Environment Variables:**

- `API_URL` - API base URL
- `TEST_DURATION` - Test duration in seconds
- `CONCURRENCY` - Number of concurrent users
- `REQUEST_RATE` - Request rate per second
- `REQUEST_TIMEOUT` - Request timeout in seconds
- `OUTPUT_FILE` - Output file for results

## Script Permissions

On Linux/macOS, make scripts executable:

```bash
chmod +x scripts/*.sh
```

## Integration with Monitoring Systems

The `health_check.sh` script is designed to integrate with monitoring systems like:

- **Nagios/Icinga**: Use exit codes to determine service status
- **Prometheus**: Combine with blackbox_exporter
- **Kubernetes**: Use as liveness/readiness probe
- **Docker**: Use in HEALTHCHECK directive
- **Systemd**: Use in service health checks

**Example Kubernetes Probe:**

```yaml
livenessProbe:
  exec:
    command:
    - /app/scripts/health_check.sh
    - --endpoint
    - /health/live
    - --quiet
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  exec:
    command:
    - /app/scripts/health_check.sh
    - --endpoint
    - /health/ready
    - --quiet
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 5
  failureThreshold: 3
```

**Example Systemd Service:**

```ini
[Unit]
Description=APGI API Health Check
After=apgi-api.service

[Service]
Type=oneshot
ExecStart=/opt/apgi/scripts/health_check.sh --quiet
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Example Cron Job:**

```bash
# Check API health every 5 minutes
*/5 * * * * /opt/apgi/scripts/health_check.sh --quiet || \
  echo "API health check failed" | \
  mail -s "APGI API Alert" admin@example.com
```

## Troubleshooting

### start.sh fails with "Docker daemon is not running"

**Solution:** Start Docker Desktop or the Docker daemon:

- Windows: Start Docker Desktop
- Linux: `sudo systemctl start docker`
- macOS: Start Docker Desktop

### migrate.sh fails with "Alembic is not installed"

**Solution:** Install Alembic:

```bash
pip install alembic
```

Or use Docker mode:

```bash
./scripts/migrate.sh head docker
```

### health_check.sh fails with "curl is not installed"

**Solution:** Install curl:

- Ubuntu/Debian: `sudo apt-get install curl`
- CentOS/RHEL: `sudo yum install curl`
- macOS: `brew install curl`
- Windows: Use PowerShell version (`health_check.ps1`)

### Services don't become healthy

**Solution:** Check service logs:

```bash
cd deployment
docker-compose logs -f
```

Common issues:

- PostgreSQL: Check database credentials in `.env.development`
- Redis: Check if port 6379 is already in use
- API: Check if port 8000 is already in use

## Additional Resources

- [Deployment Guide](../docs/DEPLOYMENT.md)
- [Configuration Guide](../docs/CONFIGURATION.md)
- [API Documentation](../docs/REST-API.md)
- [Main README](../README.md)
