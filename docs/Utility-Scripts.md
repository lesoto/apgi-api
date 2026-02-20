# Utility Scripts

## Available Scripts

### start.sh / start.ps1

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
*/5 * * * * /opt/apgi/scripts/health_check.sh --quiet || echo "API health check failed" | mail -s "APGI API Alert" admin@example.com
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
- [API Documentation](../docs/API.md)
- [Main README](../README.md)
