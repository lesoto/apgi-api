# Deployment Guide

This guide provides step-by-step instructions for deploying the APGI Standalone API in various environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Configuration](#environment-configuration)
- [Docker Deployment](#docker-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Database Setup](#database-setup)
- [Celery Worker Setup](#celery-worker-setup)
- [Production Checklist](#production-checklist)
- [Monitoring and Maintenance](#monitoring-and-maintenance)
- [Scaling](#scaling)
- [Rollback Procedures](#rollback-procedures)

## Prerequisites

### Infrastructure Requirements

**Minimum Requirements (Development/Staging):**

- 2 CPU cores
- 4 GB RAM
- 20 GB disk space
- PostgreSQL 14+
- Redis 7+

**Recommended Requirements (Production):**

- 4+ CPU cores per API instance
- 8+ GB RAM per API instance
- 100+ GB disk space
- PostgreSQL 14+ with replication
- Redis 7+ with persistence
- Load balancer (nginx, HAProxy, or cloud provider)

### Software Requirements

- Docker 20.10+ and Docker Compose 2.0+ (for Docker deployment)
- Kubernetes 1.24+ (for Kubernetes deployment)
- Python 3.11+ (for manual deployment)
- PostgreSQL client tools (for database management)

### Network Requirements

- Outbound internet access for package installation
- Inbound access on port 8000 (API)
- Access to PostgreSQL (default port 5432)
- Access to Redis (default port 6379)

## Environment Configuration

### Required Environment Variables

Create a `.env` file with the following variables:

```bash
# Environment
ENVIRONMENT=production  # development, staging, or production

# API Settings
API_TITLE=APGI Standalone API
API_VERSION=1.0.0
HOST=0.0.0.0
PORT=8000

# Database Configuration
DATABASE_URL=postgresql://username:password@postgres-host:5432/apgi_api
# For production, use connection pooling:
# DATABASE_URL=postgresql://username:password@postgres-host:5432/apgi_api?pool_size=10&max_overflow=20

# Redis Configuration
REDIS_URL=redis://redis-host:6379/0

# Celery Configuration
CELERY_BROKER_URL=redis://redis-host:6379/1
CELERY_RESULT_BACKEND=redis://redis-host:6379/2

# Authentication
JWT_SECRET_KEY=your-secure-secret-key-minimum-32-characters-long
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS Configuration
CORS_ORIGINS=https://your-frontend-domain.com,https://another-domain.com
CORS_ALLOW_CREDENTIALS=true

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60

# Logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### Security Considerations

**Production Environment:**

- `JWT_SECRET_KEY` must be at least 32 characters and cryptographically random
- `CORS_ORIGINS` must be explicitly configured (no wildcards with credentials)
- `DATABASE_URL` should use SSL/TLS connections
- Never commit `.env` files to version control
- Use secrets management (AWS Secrets Manager, HashiCorp Vault, etc.)

**Generate a secure JWT secret:**

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Docker Deployment

### Building the Docker Image

**Production Image:**

```bash
cd standalone-api
docker build -t apgi-api:latest -f deployment/Dockerfile .
```

**Development Image:**

```bash
docker build -t apgi-api:dev -f deployment/Dockerfile.dev .
```

### Docker Compose Deployment

**1. Create environment file:**

```bash
cp .env.production .env
# Edit .env with your configuration
```

**2. Start all services:**

```bash
docker-compose -f deployment/docker-compose.yml up -d
```

This starts:

- PostgreSQL database
- Redis cache
- API server (3 instances behind load balancer)
- Celery worker (2 instances)

**3. Run database migrations:**

```bash
docker-compose -f deployment/docker-compose.yml exec api alembic upgrade head
```

**4. Verify deployment:**

```bash
# Check health
curl http://localhost:8000/health

# Check readiness
curl http://localhost:8000/health/ready

# View logs
docker-compose -f deployment/docker-compose.yml logs -f api
```

**5. Stop services:**

```bash
docker-compose -f deployment/docker-compose.yml down
```

**6. Stop and remove volumes (WARNING: deletes data):**

```bash
docker-compose -f deployment/docker-compose.yml down -v
```

### Docker Compose Production Configuration

For production, use `docker-compose.prod.yml`:

```bash
# Start production stack
docker-compose -f deployment/docker-compose.prod.yml up -d

# Scale API instances
docker-compose -f deployment/docker-compose.prod.yml up -d --scale api=5

# Scale Celery workers
docker-compose -f deployment/docker-compose.prod.yml up -d --scale celery_worker=3
```

## Kubernetes Deployment

### Kubernetes Prerequisites

- Kubernetes cluster (1.24+)
- kubectl configured to access your cluster
- Container registry (Docker Hub, ECR, GCR, etc.)

### Step 1: Push Docker Image to Registry

```bash
# Tag image
docker tag apgi-api:latest your-registry.com/apgi-api:1.0.0

# Push to registry
docker push your-registry.com/apgi-api:1.0.0
```

### Step 2: Create Kubernetes Secrets

```bash
# Create secret for database credentials
kubectl create secret generic apgi-secrets \
  --from-literal=database-url='postgresql://user:pass@postgres:5432/apgi_api' \
  --from-literal=redis-url='redis://redis:6379/0' \
  --from-literal=jwt-secret='your-secure-jwt-secret-key'

# Verify secret
kubectl get secrets apgi-secrets
```

### Step 3: Deploy PostgreSQL and Redis

**PostgreSQL Deployment:**

```yaml
# postgres-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:14-alpine
        env:
        - name: POSTGRES_DB
          value: apgi_api
        - name: POSTGRES_USER
          value: apgi_user
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: apgi-secrets
              key: postgres-password
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
```

**Redis Deployment:**

```yaml
# redis-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        volumeMounts:
        - name: redis-storage
          mountPath: /data
      volumes:
      - name: redis-storage
        persistentVolumeClaim:
          claimName: redis-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: redis
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

### Step 4: Deploy API

```yaml
# api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: apgi-api
  labels:
    app: apgi-api
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
        image: your-registry.com/apgi-api:1.0.0
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
        - name: CELERY_BROKER_URL
          value: "redis://redis:6379/1"
        - name: CELERY_RESULT_BACKEND
          value: "redis://redis:6379/2"
        - name: CORS_ORIGINS
          value: "https://your-frontend.com"
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
          timeoutSeconds: 5
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
          timeoutSeconds: 5
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
```

### Step 5: Deploy Celery Workers

```yaml
# celery-deployment.yaml
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
        image: your-registry.com/apgi-api:1.0.0
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
        - name: CELERY_BROKER_URL
          value: "redis://redis:6379/1"
        - name: CELERY_RESULT_BACKEND
          value: "redis://redis:6379/2"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
```

### Step 6: Apply Kubernetes Manifests

```bash
# Create persistent volumes (if not using dynamic provisioning)
kubectl apply -f postgres-pvc.yaml
kubectl apply -f redis-pvc.yaml

# Deploy data services
kubectl apply -f postgres-deployment.yaml
kubectl apply -f redis-deployment.yaml

# Wait for data services to be ready
kubectl wait --for=condition=ready pod -l app=postgres --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis --timeout=300s

# Deploy API
kubectl apply -f api-deployment.yaml

# Deploy Celery workers
kubectl apply -f celery-deployment.yaml

# Verify deployments
kubectl get deployments
kubectl get pods
kubectl get services
```

### Step 7: Run Database Migrations

```bash
# Get API pod name
API_POD=$(kubectl get pods -l app=apgi-api -o jsonpath='{.items[0].metadata.name}')

# Run migrations
kubectl exec -it $API_POD -- alembic upgrade head
```

### Step 8: Configure Ingress (Optional)

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: apgi-api-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.yourdomain.com
    secretName: apgi-api-tls
  rules:
  - host: api.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: apgi-api
            port:
              number: 80
```

```bash
kubectl apply -f ingress.yaml
```

## Database Setup

### Initial Database Creation

**Using PostgreSQL client:**

```bash
# Connect to PostgreSQL
psql -h postgres-host -U postgres

# Create database
CREATE DATABASE apgi_api;

# Create user
CREATE USER apgi_user WITH PASSWORD 'secure_password';

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE apgi_api TO apgi_user;

# Exit
\q
```

### Running Migrations

**Docker:**

```bash
docker-compose exec api alembic upgrade head
```

**Kubernetes:**

```bash
kubectl exec -it <api-pod-name> -- alembic upgrade head
```

**Manual:**
```bash
cd standalone-api
alembic upgrade head
```

### Migration Management

**View migration history:**

```bash
alembic history
```

**View current version:**

 
```bash
alembic current
```

**Rollback one migration:**

 
```bash
alembic downgrade -1
```

**Rollback to specific version:**

```bash
alembic downgrade <revision_id>
```

**Create new migration:**

```bash
alembic revision --autogenerate -m "Description of changes"
```

### Database Backup

**Backup:**

```bash
pg_dump -h postgres-host -U apgi_user apgi_api > backup_$(date +%Y%m%d_%H%M%S).sql
```

**Restore:**

```bash
psql -h postgres-host -U apgi_user apgi_api < backup_20240115_120000.sql
```

**Automated backups (cron):**

```bash
# Add to crontab
0 2 * * * pg_dump -h postgres-host -U apgi_user apgi_api > /backups/apgi_api_$(date +\%Y\%m\%d).sql
```

## Celery Worker Setup

### Starting Celery Workers

**Docker:**

```bash
docker-compose -f deployment/docker-compose.yml up -d celery_worker
```

**Kubernetes:**

```bash
kubectl apply -f celery-deployment.yaml
```

**Manual:**

 
```bash
celery -A app.celery_app worker --loglevel=info
```

### Scaling Workers

**Docker Compose:**

```bash
docker-compose -f deployment/docker-compose.yml up -d --scale celery_worker=5
```

**Kubernetes:**

 
```bash
kubectl scale deployment apgi-celery-worker --replicas=5
```

### Monitoring Workers

**View worker status:**

```bash
celery -A app.celery_app inspect active
celery -A app.celery_app inspect stats
```

**View task queue:**
```bash
celery -A app.celery_app inspect reserved
```

### Worker Configuration

Workers can be configured via environment variables:

```bash
# Concurrency (number of worker processes)
CELERY_WORKER_CONCURRENCY=4

# Task time limits
CELERY_TASK_TIME_LIMIT=3600        # 1 hour hard limit
CELERY_TASK_SOFT_TIME_LIMIT=3300   # 55 minute soft limit

# Prefetch multiplier (tasks to prefetch per worker)
CELERY_WORKER_PREFETCH_MULTIPLIER=4
```

## Production Checklist

Before deploying to production, verify:

### Security

- [ ] `JWT_SECRET_KEY` is cryptographically random (32+ characters)
- [ ] `CORS_ORIGINS` is explicitly configured (no wildcards)
- [ ] Database uses SSL/TLS connections
- [ ] Redis uses password authentication
- [ ] Secrets are stored in secrets manager (not in code)
- [ ] API is behind HTTPS/TLS termination
- [ ] Rate limiting is enabled
- [ ] CSRF protection is enabled

### Configuration

- [ ] `ENVIRONMENT=production`
- [ ] `LOG_LEVEL=INFO` or `WARNING`
- [ ] Database connection pooling is configured
- [ ] Redis persistence is enabled (AOF or RDB)
- [ ] Celery result expiration is set
- [ ] All required environment variables are set

### Infrastructure

- [ ] PostgreSQL has automated backups
- [ ] Redis has persistence enabled
- [ ] Load balancer is configured with health checks
- [ ] Monitoring and alerting are set up
- [ ] Log aggregation is configured
- [ ] Resource limits are set (CPU, memory)

### Testing

- [ ] Health checks return 200 OK
- [ ] Readiness checks verify all dependencies
- [ ] Authentication flow works end-to-end
- [ ] Session creation and management work
- [ ] Task submission and retrieval work
- [ ] Database migrations are up to date

### Documentation

- [ ] Deployment runbook is complete
- [ ] Rollback procedures are documented
- [ ] On-call contacts are documented
- [ ] Monitoring dashboards are created

## Monitoring and Maintenance

### Health Checks

**Basic health:**

```bash
curl http://api-host:8000/health
```

**Readiness (checks dependencies):**

 
```bash
curl http://api-host:8000/health/ready
```

**Liveness:**

 
```bash
curl http://api-host:8000/health/live
```

### Metrics

**Prometheus metrics:**

```bash
curl http://api-host:8000/metrics
```

Key metrics to monitor:

- `http_requests_total` - Total request count
- `http_request_duration_seconds` - Request latency
- `http_requests_in_progress` - Active requests
- `database_connections_active` - Database connection pool usage
- `celery_tasks_total` - Task execution count
- `celery_task_duration_seconds` - Task execution time

### Log Aggregation

Logs are written to stdout in JSON format. Configure log aggregation:

**ELK Stack:**

- Filebeat → Logstash → Elasticsearch → Kibana

**Cloud Providers:**

- AWS: CloudWatch Logs
- GCP: Cloud Logging
- Azure: Azure Monitor

**Example log query (Elasticsearch):**

```json
{
  "query": {
    "bool": {
      "must": [
        { "match": { "level": "ERROR" }},
        { "range": { "timestamp": { "gte": "now-1h" }}}
      ]
    }
  }
}
```

### Alerting

Configure alerts for:

- Error rate > 10 errors/minute for 5 minutes
- Response time p95 > 1000ms for 5 minutes
- Health check failures
- Database connection failures
- Redis connection failures
- Celery worker failures
- Disk space < 10%
- Memory usage > 90%

## Scaling

### Horizontal Scaling

**API Instances:**
```bash
# Docker Compose
docker-compose up -d --scale api=5

# Kubernetes
kubectl scale deployment apgi-api --replicas=5
```

**Celery Workers:**
```bash
# Docker Compose
docker-compose up -d --scale celery_worker=3

# Kubernetes
kubectl scale deployment apgi-celery-worker --replicas=3
```

### Auto-scaling (Kubernetes)

```yaml
# api-hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: apgi-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: apgi-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

```bash
kubectl apply -f api-hpa.yaml
```

### Database Scaling

**Read Replicas:**

- Configure PostgreSQL streaming replication
- Route read queries to replicas
- Keep writes on primary

**Connection Pooling:**

- Use PgBouncer for connection pooling
- Configure pool size based on load

### Redis Scaling

**Redis Cluster:**

- Deploy Redis Cluster for horizontal scaling
- Configure sharding for large datasets

**Redis Sentinel:**

- Deploy Redis Sentinel for high availability
- Automatic failover on primary failure

## Rollback Procedures

### Application Rollback

**Docker:**
```bash
# Tag current version
docker tag apgi-api:latest apgi-api:backup

# Pull previous version
docker pull your-registry.com/apgi-api:1.0.0

# Restart with previous version
docker-compose down
docker-compose up -d
```

**Kubernetes:**
```bash
# Rollback to previous deployment
kubectl rollout undo deployment/apgi-api

# Rollback to specific revision
kubectl rollout undo deployment/apgi-api --to-revision=2

# View rollout history
kubectl rollout history deployment/apgi-api
```

### Database Rollback

**Rollback one migration:**
```bash
alembic downgrade -1
```

**Rollback to specific version:**

```bash
alembic downgrade <revision_id>
```

**Restore from backup:**
```bash
# Stop API
docker-compose stop api

# Restore database
psql -h postgres-host -U apgi_user apgi_api < backup_20240115_120000.sql

# Start API
docker-compose start api
```

### Emergency Procedures

**Complete system rollback:**
1. Stop all API instances
2. Stop all Celery workers
3. Restore database from backup
4. Deploy previous application version
5. Verify health checks
6. Gradually restore traffic

**Partial rollback (canary):**
1. Deploy previous version alongside current
2. Route 10% traffic to previous version
3. Monitor error rates and performance
4. Gradually increase traffic to previous version
5. Decommission current version when stable

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed troubleshooting guidance.

### Quick Diagnostics

**Check API logs:**
```bash
# Docker
docker-compose logs -f api

# Kubernetes
kubectl logs -f deployment/apgi-api
```

**Check database connectivity:**
```bash
psql -h postgres-host -U apgi_user apgi_api -c "SELECT 1"
```

**Check Redis connectivity:**
```bash
redis-cli -h redis-host ping
```

**Check Celery workers:**
```bash
celery -A app.celery_app inspect ping
```

## Support

For issues or questions:
- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Review logs for error messages
- Check health endpoints for dependency status
- Contact DevOps team: devops@example.com
