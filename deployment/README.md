# Docker Deployment Guide

This directory contains Docker configuration files for deploying the APGI Standalone API.

## Files

- **Dockerfile** - Production-optimized multi-stage build
- **Dockerfile.dev** - Development build with hot-reload
- **docker-compose.yml** - Local development environment
- **docker-compose.prod.yml** - Production-like testing environment

## Quick Start - Development

1. Navigate to the deployment directory:
```bash
cd standalone-api/deployment
```

2. Start all services:
```bash
docker-compose up -d
```

3. Run database migrations:
```bash
docker-compose exec api alembic upgrade head
```

4. Access the API:
- API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

5. View logs:
```bash
docker-compose logs -f api
docker-compose logs -f celery_worker
```

6. Stop services:
```bash
docker-compose down
```

## Production-Like Testing

1. Set required environment variables:
```bash
export JWT_SECRET_KEY="your-secure-secret-key-minimum-32-characters-long"
export CORS_ORIGINS="https://yourdomain.com"
export POSTGRES_PASSWORD="secure-database-password"
```

2. Start production environment:
```bash
docker-compose -f docker-compose.prod.yml up -d
```

3. Run database migrations:
```bash
docker-compose -f docker-compose.prod.yml exec api alembic upgrade head
```

4. Monitor services:
```bash
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs -f
```

## Building Images

### Development Image
```bash
cd standalone-api
docker build -f deployment/Dockerfile.dev -t apgi-api:dev .
```

### Production Image
```bash
cd standalone-api
docker build -f deployment/Dockerfile -t apgi-api:latest .
```

## Service Architecture

The Docker Compose setup includes:

- **postgres** - PostgreSQL 14 database
  - Port: 5432
  - Persistent volume for data
  - Health checks enabled

- **redis** - Redis 7 cache and message broker
  - Port: 6379
  - Persistent volume for data
  - Health checks enabled

- **api** - FastAPI application
  - Port: 8000
  - Depends on postgres and redis
  - Hot-reload in development
  - Health checks enabled

- **celery_worker** - Celery task worker
  - Processes asynchronous tasks
  - Depends on postgres and redis
  - Auto-restart on failure

## Environment Variables

### Required for Production

- `JWT_SECRET_KEY` - Secret key for JWT tokens (min 32 characters)
- `CORS_ORIGINS` - Comma-separated list of allowed origins
- `POSTGRES_PASSWORD` - Database password

### Optional Configuration

- `ENVIRONMENT` - Environment name (development/staging/production)
- `LOG_LEVEL` - Logging level (DEBUG/INFO/WARNING/ERROR)
- `RATE_LIMIT_PER_MINUTE` - Rate limit threshold
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` - Token expiration time

## Health Checks

All services include health checks:

- **postgres**: `pg_isready` command
- **redis**: `redis-cli ping` command
- **api**: HTTP GET to `/health` endpoint

Health checks ensure services are ready before dependent services start.

## Volumes

### Development
- `postgres_dev_data` - PostgreSQL data
- `redis_dev_data` - Redis data
- Source code mounted for hot-reload

### Production
- `postgres_prod_data` - PostgreSQL data
- `redis_prod_data` - Redis data with AOF persistence
- No source code mounts (baked into image)

## Networking

All services communicate via the `apgi-network` bridge network:
- Services can reference each other by service name
- Example: `postgres:5432`, `redis:6379`

## Troubleshooting

### Services won't start
```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs

# Restart specific service
docker-compose restart api
```

### Database connection issues
```bash
# Check postgres health
docker-compose exec postgres pg_isready -U apgi_dev

# Connect to database
docker-compose exec postgres psql -U apgi_dev -d apgi_api_dev
```

### Redis connection issues
```bash
# Check redis health
docker-compose exec redis redis-cli ping

# Connect to redis
docker-compose exec redis redis-cli
```

### Reset everything
```bash
# Stop and remove all containers, networks, and volumes
docker-compose down -v

# Rebuild and start fresh
docker-compose up -d --build
```

## Security Notes

### Development
- Uses default passwords (DO NOT use in production)
- Debug logging enabled
- CORS allows localhost origins
- Hot-reload enabled

### Production
- Requires secure JWT secret key
- Requires explicit CORS origins
- Runs as non-root user (UID 1000)
- Minimal logging (WARNING level)
- No source code mounts
- Multi-stage build for smaller images

## Performance Tuning

### API Workers
Adjust uvicorn workers in production Dockerfile:
```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Celery Concurrency
Adjust celery worker concurrency:
```bash
celery -A app.celery_app worker --concurrency=4
```

### Database Connections
Configure connection pool in `app/config.py`:
- Pool size: 10
- Max overflow: 20

## Monitoring

### View Metrics
```bash
curl http://localhost:8000/metrics
```

### Check Health
```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
curl http://localhost:8000/health/live
```

### Container Stats
```bash
docker stats
```
