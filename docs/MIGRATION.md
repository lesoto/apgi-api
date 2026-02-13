# Migration Guide

This guide provides instructions for migrating from the legacy embedded API to the standalone APGI API.

## Table of Contents

- [Overview](#overview)
- [Differences from Legacy API](#differences-from-legacy-api)
- [Migration Strategy](#migration-strategy)
- [Pre-Migration Checklist](#pre-migration-checklist)
- [Migration Steps](#migration-steps)
- [Data Migration](#data-migration)
- [Client Migration](#client-migration)
- [Testing Migration](#testing-migration)
- [Rollback Procedures](#rollback-procedures)
- [Post-Migration Validation](#post-migration-validation)

## Overview

The standalone API is a complete extraction of the APGI REST API from the main application into an independently deployable service. The migration maintains full backward compatibility with existing clients while enabling independent deployment, scaling, and maintenance.

### Migration Goals

- Zero downtime migration
- Full backward compatibility
- Data integrity preservation
- Minimal client changes
- Rollback capability

### Migration Timeline

**Recommended Timeline:**

- Week 1: Pre-migration preparation and testing
- Week 2: Parallel deployment and traffic routing
- Week 3: Gradual traffic migration (10% → 50% → 100%)
- Week 4: Monitoring and optimization
- Week 5+: Legacy API decommissioning

## Differences from Legacy API

### API Interface

**Good News:** The standalone API maintains 100% backward compatibility with the legacy API.

**No Changes Required:**

- ✅ All endpoint paths remain the same
- ✅ All request formats remain the same
- ✅ All response formats remain the same
- ✅ All HTTP status codes remain the same
- ✅ All authentication mechanisms remain the same

### Deployment Architecture

**Changes:**
- **Legacy:** API embedded in main application
- **Standalone:** API deployed as separate service

**Impact:**

- Different deployment process
- Separate configuration management
- Independent scaling
- Separate monitoring

### Configuration

**Changes:**
- **Legacy:** Configuration in main application config files
- **Standalone:** Configuration via environment variables

**Impact:**

- Need to migrate configuration to environment variables
- Need to set up separate secrets management
- Need to configure CORS for new domain

### Database

**Changes:**
- **Legacy:** Shared database with main application
- **Standalone:** Dedicated database (recommended) or shared database

**Impact:**

- May need to migrate data to new database
- Need to run database migrations
- Need to configure database connection

### Dependencies

**Changes:**
- **Legacy:** Shared dependencies with main application
- **Standalone:** Independent dependency management

**Impact:**

- Separate requirements.txt
- Independent version updates
- Smaller Docker images

## Migration Strategy

### Recommended Approach: Parallel Deployment

Deploy the standalone API alongside the legacy API and gradually migrate traffic.

**Phases:**

1. **Preparation (Week 1)**
   - Deploy standalone API in staging
   - Run integration tests
   - Migrate data to standalone database
   - Configure monitoring

2. **Parallel Deployment (Week 2)**
   - Deploy standalone API in production
   - Keep legacy API running
   - Route 0% traffic to standalone API
   - Verify health checks

3. **Gradual Migration (Week 3)**
   - Route 10% traffic to standalone API
   - Monitor error rates and performance
   - Route 50% traffic to standalone API
   - Monitor for 48 hours
   - Route 100% traffic to standalone API

4. **Stabilization (Week 4)**
   - Monitor standalone API
   - Keep legacy API running for rollback
   - Optimize performance
   - Fix any issues

5. **Decommissioning (Week 5+)**
   - Verify standalone API is stable
   - Decommission legacy API
   - Remove legacy API code

### Alternative Approach: Big Bang Migration

Switch all traffic at once (not recommended for production).

**Use Cases:**

- Small deployments with low traffic
- Development/staging environments
- Maintenance window available

**Steps:**
1. Schedule maintenance window
2. Stop legacy API
3. Migrate data
4. Deploy standalone API
5. Verify health checks
6. Resume traffic

## Pre-Migration Checklist

### Infrastructure

- [ ] Provision PostgreSQL database for standalone API
- [ ] Provision Redis instance for standalone API
- [ ] Set up load balancer for standalone API
- [ ] Configure DNS for standalone API domain
- [ ] Set up SSL/TLS certificates
- [ ] Configure firewall rules

### Configuration

- [ ] Generate secure JWT secret key
- [ ] Configure CORS origins with new domain
- [ ] Set up database connection string
- [ ] Set up Redis connection string
- [ ] Configure Celery broker and backend
- [ ] Set up secrets management

### Monitoring

- [ ] Set up log aggregation
- [ ] Configure Prometheus metrics collection
- [ ] Create Grafana dashboards
- [ ] Set up alerting rules
- [ ] Configure health check monitoring

### Testing

- [ ] Run integration tests in staging
- [ ] Test authentication flow
- [ ] Test session management
- [ ] Test async task execution
- [ ] Test data export
- [ ] Load test standalone API

### Documentation

- [ ] Document new deployment process
- [ ] Document rollback procedures
- [ ] Update runbooks
- [ ] Train operations team

## Migration Steps

### Step 1: Deploy Standalone API in Staging

**1.1 Build Docker Image:**

```bash
cd standalone-api
docker build -t apgi-api:1.0.0 -f deployment/Dockerfile .
```

**1.2 Push to Registry:**

```bash
docker tag apgi-api:1.0.0 your-registry.com/apgi-api:1.0.0
docker push your-registry.com/apgi-api:1.0.0
```

**1.3 Deploy to Staging:**

```bash
# Using Docker Compose
docker-compose -f deployment/docker-compose.yml up -d

# Or using Kubernetes
kubectl apply -f deployment/k8s/
```

**1.4 Run Database Migrations:**

```bash
# Docker
docker-compose exec api alembic upgrade head

# Kubernetes
kubectl exec -it <api-pod> -- alembic upgrade head
```

**1.5 Verify Health:**

```bash
curl https://api-staging.example.com/health
curl https://api-staging.example.com/health/ready
```

### Step 2: Migrate Data (if using separate database)

**2.1 Backup Legacy Database:**

```bash
pg_dump -h legacy-db-host -U apgi_user apgi_db > legacy_backup_$(date +%Y%m%d).sql
```

**2.2 Create Standalone Database:**

```bash
psql -h standalone-db-host -U postgres -c "CREATE DATABASE apgi_api;"
psql -h standalone-db-host -U postgres -c "CREATE USER apgi_user WITH PASSWORD 'secure_password';"
psql -h standalone-db-host -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE apgi_api TO apgi_user;"
```

**2.3 Migrate Data:**

**Option A: Full Database Copy**

```bash
# Restore backup to new database
psql -h standalone-db-host -U apgi_user apgi_api < legacy_backup_20240115.sql

# Run migrations to update schema
alembic upgrade head
```

**Option B: Selective Data Migration**

```bash
# Export specific tables
pg_dump -h legacy-db-host -U apgi_user -t users -t sessions -t tasks apgi_db > data_export.sql

# Import to standalone database
psql -h standalone-db-host -U apgi_user apgi_api < data_export.sql

# Run migrations
alembic upgrade head
```

**2.4 Verify Data Integrity:**

```bash
# Compare record counts
psql -h legacy-db-host -U apgi_user apgi_db -c "SELECT COUNT(*) FROM users;"
psql -h standalone-db-host -U apgi_user apgi_api -c "SELECT COUNT(*) FROM users;"

# Verify sample records
psql -h standalone-db-host -U apgi_user apgi_api -c "SELECT * FROM users LIMIT 10;"
```

### Step 3: Deploy to Production

**3.1 Deploy Standalone API:**

```bash
# Using Docker Compose
docker-compose -f deployment/docker-compose.prod.yml up -d

# Or using Kubernetes
kubectl apply -f deployment/k8s/production/
```

**3.2 Verify Health:**

```bash
curl https://api.example.com/health
curl https://api.example.com/health/ready
```

**3.3 Run Smoke Tests:**
```bash
# Test authentication
curl -X POST https://api.example.com/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test_user","password":"test_password"}'

# Test session creation
curl -X POST https://api.example.com/v1/sessions \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"config":{"param":"value"}}'
```

### Step 4: Configure Traffic Routing

**4.1 Update Load Balancer:**

Configure load balancer to route traffic to both legacy and standalone APIs:

```nginx
# nginx configuration
upstream legacy_api {
    server legacy-api-1:8000;
    server legacy-api-2:8000;
}

upstream standalone_api {
    server standalone-api-1:8000;
    server standalone-api-2:8000;
    server standalone-api-3:8000;
}

# Split traffic: 90% legacy, 10% standalone
split_clients "${remote_addr}${http_user_agent}" $backend {
    10%     standalone;
    *       legacy;
}

server {
    listen 443 ssl;
    server_name api.example.com;

    location / {
        if ($backend = "standalone") {
            proxy_pass http://standalone_api;
        }
        if ($backend = "legacy") {
            proxy_pass http://legacy_api;
        }
    }
}
```

**4.2 Gradually Increase Traffic:**

Week 3, Day 1: 10% standalone
```nginx
split_clients "${remote_addr}${http_user_agent}" $backend {
    10%     standalone;
    *       legacy;
}
```

Week 3, Day 3: 50% standalone (if no issues)
```nginx
split_clients "${remote_addr}${http_user_agent}" $backend {
    50%     standalone;
    *       legacy;
}
```

Week 3, Day 5: 100% standalone (if no issues)
```nginx
upstream api {
    server standalone-api-1:8000;
    server standalone-api-2:8000;
    server standalone-api-3:8000;
}

server {
    listen 443 ssl;
    server_name api.example.com;

    location / {
        proxy_pass http://api;
    }
}
```

### Step 5: Monitor and Validate

**5.1 Monitor Key Metrics:**
- Request rate (requests/second)
- Response time (p50, p95, p99)
- Error rate (errors/second)
- Success rate (%)
- Database connection pool usage
- Redis connection count
- Celery queue depth

**5.2 Monitor Logs:**
```bash
# View API logs
docker-compose logs -f api

# Or Kubernetes
kubectl logs -f deployment/apgi-api

# Search for errors
kubectl logs deployment/apgi-api | grep ERROR
```

**5.3 Compare Metrics:**
Compare standalone API metrics with legacy API baseline:
- Response times should be similar or better
- Error rates should be similar or lower
- Success rates should be 99.9%+

**5.4 Alert Thresholds:**
- Error rate > 10 errors/minute → Investigate
- Response time p95 > 1000ms → Investigate
- Success rate < 99% → Rollback

## Data Migration

### Shared Database Approach

**Pros:**
- No data migration needed
- Instant cutover
- Easy rollback

**Cons:**
- Shared resource contention
- Coupled deployments
- Harder to scale independently

**Configuration:**
```bash
# Both APIs use same database
DATABASE_URL=postgresql://apgi_user:password@shared-db:5432/apgi_db
```

### Separate Database Approach

**Pros:**
- Independent scaling
- Isolated failures
- Better performance

**Cons:**
- Data migration required
- More complex rollback
- Potential data sync issues

**Migration Steps:**
1. Create new database
2. Copy data from legacy database
3. Run migrations on new database
4. Verify data integrity
5. Keep databases in sync during transition (optional)

### Data Synchronization (Optional)

For zero-downtime migration with separate databases:

**1. Set up replication:**
```bash
# Configure PostgreSQL logical replication
# On legacy database
CREATE PUBLICATION apgi_pub FOR ALL TABLES;

# On standalone database
CREATE SUBSCRIPTION apgi_sub CONNECTION 'host=legacy-db ...' PUBLICATION apgi_pub;
```

**2. Monitor replication lag:**
```sql
SELECT * FROM pg_stat_subscription;
```

**3. Cutover:**
- Stop writes to legacy database
- Wait for replication to catch up
- Switch traffic to standalone API
- Drop replication

## Client Migration

### No Changes Required

The standalone API maintains 100% backward compatibility. Existing clients work without modifications.

### Optional: Update Base URL

If deploying to a new domain:

**Before:**
```javascript
const API_BASE_URL = 'https://app.example.com/api';
```

**After:**
```javascript
const API_BASE_URL = 'https://api.example.com';
```

### Optional: Update CORS Configuration

If frontend domain changes, update CORS origins:

```bash
CORS_ORIGINS=https://new-frontend.example.com
```

## Testing Migration

### Pre-Migration Testing

**1. Integration Tests:**
```bash
cd standalone-api
pytest tests/integration/
```

**2. Smoke Tests:**
```bash
# Test authentication
./tests/smoke/test_auth.sh

# Test session management
./tests/smoke/test_sessions.sh

# Test async tasks
./tests/smoke/test_tasks.sh
```

**3. Load Tests:**
```bash
# Using Apache Bench
ab -n 10000 -c 100 https://api-staging.example.com/health

# Using k6
k6 run tests/load/api_load_test.js
```

### Post-Migration Testing

**1. Verify All Endpoints:**
```bash
# Run comprehensive API tests
pytest tests/integration/ --base-url=https://api.example.com
```

**2. Compare Responses:**
```bash
# Compare legacy vs standalone responses
./tests/compare_responses.sh
```

**3. Monitor for Errors:**
```bash
# Check error logs
kubectl logs deployment/apgi-api | grep ERROR | wc -l
```

## Rollback Procedures

### Immediate Rollback (Traffic Routing)

**Fastest rollback method - switch traffic back to legacy API:**

```nginx
# Update load balancer to route 100% to legacy
upstream api {
    server legacy-api-1:8000;
    server legacy-api-2:8000;
}

server {
    listen 443 ssl;
    server_name api.example.com;

    location / {
        proxy_pass http://api;
    }
}
```

**Reload nginx:**
```bash
nginx -s reload
```

**Verification:**
```bash
curl https://api.example.com/health
# Should hit legacy API
```

### Partial Rollback (Reduce Traffic)

**Reduce standalone API traffic if issues arise:**

```nginx
# Route only 10% to standalone
split_clients "${remote_addr}${http_user_agent}" $backend {
    10%     standalone;
    *       legacy;
}
```

### Database Rollback

**If using separate database and need to rollback:**

**1. Stop standalone API:**
```bash
docker-compose down
# Or
kubectl delete deployment apgi-api
```

**2. Restore legacy database (if modified):**
```bash
psql -h legacy-db-host -U apgi_user apgi_db < legacy_backup_20240115.sql
```

**3. Switch traffic to legacy API:**
```bash
# Update load balancer configuration
nginx -s reload
```

### Complete Rollback

**Full rollback to legacy API:**

**1. Route all traffic to legacy:**
```bash
# Update load balancer
nginx -s reload
```

**2. Stop standalone API:**
```bash
docker-compose -f deployment/docker-compose.prod.yml down
# Or
kubectl delete -f deployment/k8s/production/
```

**3. Verify legacy API:**
```bash
curl https://api.example.com/health
# Should return 200 OK from legacy API
```

**4. Restore data (if needed):**
```bash
psql -h legacy-db-host -U apgi_user apgi_db < legacy_backup_20240115.sql
```

## Post-Migration Validation

### Validation Checklist

**Functionality:**
- [ ] All endpoints return expected responses
- [ ] Authentication works correctly
- [ ] Session management works correctly
- [ ] Async tasks execute successfully
- [ ] Data export works correctly
- [ ] Health checks pass

**Performance:**
- [ ] Response times meet SLA (p95 < 500ms)
- [ ] Error rate < 0.1%
- [ ] Success rate > 99.9%
- [ ] Database queries are optimized
- [ ] Cache hit rate > 80%

**Monitoring:**
- [ ] Logs are being collected
- [ ] Metrics are being collected
- [ ] Alerts are configured
- [ ] Dashboards are created
- [ ] On-call rotation is updated

**Security:**
- [ ] HTTPS is enforced
- [ ] CORS is configured correctly
- [ ] Rate limiting is enabled
- [ ] Authentication is working
- [ ] Secrets are secured

**Operations:**
- [ ] Deployment process is documented
- [ ] Rollback process is documented
- [ ] Runbooks are updated
- [ ] Team is trained
- [ ] Support contacts are updated

### Monitoring Period

**Week 1-2 Post-Migration:**
- Monitor closely (24/7 on-call)
- Check metrics every hour
- Review logs daily
- Keep legacy API running

**Week 3-4 Post-Migration:**
- Monitor regularly (business hours)
- Check metrics daily
- Review logs weekly
- Prepare to decommission legacy API

**Week 5+ Post-Migration:**
- Normal monitoring
- Decommission legacy API
- Archive legacy code

### Success Criteria

Migration is successful when:
- ✅ All traffic routed to standalone API
- ✅ Error rate < 0.1% for 7 days
- ✅ Response times meet SLA for 7 days
- ✅ No critical incidents for 7 days
- ✅ All monitoring and alerting working
- ✅ Team comfortable with new deployment

## Troubleshooting

### Common Issues

**Issue: High error rate after migration**
- Check logs for specific errors
- Verify configuration is correct
- Check database connectivity
- Check Redis connectivity
- Rollback if error rate > 1%

**Issue: Slow response times**
- Check database connection pool
- Check Redis connection count
- Check Celery queue depth
- Scale up API instances
- Optimize slow queries

**Issue: Authentication failures**
- Verify JWT_SECRET_KEY matches
- Check token expiration times
- Verify CORS configuration
- Check clock synchronization

**Issue: Database connection errors**
- Verify DATABASE_URL is correct
- Check database is accessible
- Check connection pool settings
- Check database resource limits

### Getting Help

- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Review migration logs
- Contact DevOps team: devops@example.com
- Escalate to on-call engineer if critical

## Appendix

### Migration Timeline Template

```
Week 1: Preparation
- Day 1-2: Deploy to staging, run tests
- Day 3-4: Migrate data, verify integrity
- Day 5: Final staging tests, team training

Week 2: Production Deployment
- Day 1: Deploy standalone API to production
- Day 2-3: Verify health, run smoke tests
- Day 4-5: Configure traffic routing, prepare for migration

Week 3: Traffic Migration
- Day 1: Route 10% traffic, monitor closely
- Day 2: Monitor, fix issues if any
- Day 3: Route 50% traffic, monitor closely
- Day 4: Monitor, fix issues if any
- Day 5: Route 100% traffic, monitor closely

Week 4: Stabilization
- Day 1-7: Monitor, optimize, keep legacy API running

Week 5+: Decommissioning
- Verify stability for 7+ days
- Decommission legacy API
- Archive legacy code
```

### Rollback Decision Matrix

| Error Rate | Response Time | Action |
|------------|---------------|--------|
| < 0.1% | < 500ms | Continue |
| 0.1-1% | 500-1000ms | Investigate, reduce traffic |
| 1-5% | 1000-2000ms | Reduce traffic to 10% |
| > 5% | > 2000ms | Immediate rollback |

### Contact Information

- **DevOps Team:** devops@example.com
- **On-Call Engineer:** oncall@example.com
- **Slack Channel:** #api-migration
- **Incident Response:** incidents@example.com
