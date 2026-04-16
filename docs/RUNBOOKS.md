# APGI Incident Response Runbooks

This document contains runbooks for handling common security incidents
and operational issues.

## Table of Contents

1. [Incident Severity Levels](#incident-severity-levels)
2. [General Response Process](#general-response-process)
3. [Runbooks](#runbooks)
   - [RB-001: API Key Compromise](#rb-001-api-key-compromise)
   - [RB-002: Webhook Abuse](#rb-002-webhook-abuse)
   - [RB-003: Database Connection Issues](#rb-003-database-connection-issues)
   - [RB-004: Redis/Celery Failure](#rb-004-rediscelery-failure)
   - [RB-005: Rate Limit Bypass](#rb-005-rate-limit-bypass)
   - [RB-006: Data Breach Suspected](#rb-006-data-breach-suspected)
   - [RB-007: Capacity/Performance Event](#rb-007-capacityperformance-event)

---

## Incident Severity Levels

| Level | Description | Response Time | Examples |
| ----- | ---------- | ------------- | -------- |
| SEV-1 | Critical - Service down or data breach | 15m | DB corrupt, breach |
| SEV-2 | High - Major feature degraded | 1 hour | Celery stuck, auth fail |
| SEV-3 | Medium - Minor feature affected | 4 hours | Webhook endpoint fail |
| SEV-4 | Low - Cosmetic or monitoring issue | 24 hours | Metrics delay, alert |

---

## General Response Process

### 1. Detection

- Automated alerts from Prometheus/Grafana
- Manual report via <security@apgi.example.com>
- Customer support escalation

### 2. Triage (5 minutes)

- Determine severity level
- Identify affected components
- Create incident channel (Slack: #incidents-YYYY-MM-DD-XXX)
- Notify on-call engineer

### 3. Response

- Follow specific runbook below
- Document all actions in incident channel
- Update status page if SEV-1 or SEV-2

### 4. Resolution

- Verify fix is working
- Monitor for 30 minutes (SEV-1/2) or 2 hours (SEV-3/4)
- Close incident

### 5. Post-Incident

- Schedule postmortem within 48 hours for SEV-1/2
- Update runbook if needed
- Implement preventive measures

---

## Runbooks

### RB-001: API Key Compromise

**Severity:** SEV-1 (if confirmed) / SEV-2 (if suspected)

#### Detection

- Alert: `apgi_api_auth_attempts_total{result="invalid_key"}` spike
- Report: User reports unauthorized API usage
- Log: Suspicious activity from unusual IP

#### Immediate Response (5 minutes)

1. **Identify the compromised key**

   ```sql
   SELECT key_id, user_id, last_used_at, key_prefix
   FROM api_keys
   WHERE key_prefix = 'PREFIX_FROM_LOGS';
   ```

2. **Revoke the key immediately**

   ```python
   # From Python shell or admin script
   from app.services.auth_manager import AuthManager
   auth_manager = AuthManager()
   auth_manager.revoke_api_key("KEY_ID", reason="security_incident")
   ```

3. **Check key usage history**

   ```sql
   SELECT timestamp, action, ip_address, details
   FROM audit_logs
   WHERE user_id = 'USER_ID'
     AND timestamp > NOW() - INTERVAL '24 hours'
   ORDER BY timestamp DESC;
   ```

#### Investigation (30 minutes)

1. **Analyze impact**

   - Review all API calls made with the key
   - Check for data exfiltration attempts
   - Identify any data modification operations

2. **Check for related compromises**

   ```sql
   -- Check if user's other keys are affected
   SELECT * FROM api_keys
   WHERE user_id = 'USER_ID' AND is_active = true;

   -- Check for suspicious logins
   SELECT * FROM audit_logs
   WHERE user_id = 'USER_ID'
     AND action = 'login'
     AND timestamp > NOW() - INTERVAL '7 days';
   ```

#### Recovery (1 hour)

1. **User notification**

   - Email user about key revocation
   - Provide instructions for new key generation
   - Require password reset if account compromise suspected

2. **Issue new key if requested**

   ```python
   new_key = auth_manager.create_api_key(
       user_id="USER_ID",
       name="Replacement for revoked key",
       expires_days=90
   )
   ```

#### Post-Incident

- Review how key was compromised (git leak, phishing, etc.)
- Consider implementing additional restrictions (IP allowlist)
- Update key rotation policy if needed

---

### RB-002: Webhook Abuse

**Severity:** SEV-2 (if causing DOS) / SEV-3 (if attempted abuse)

#### Detection (Webhook Abuse)

- Alert: High webhook delivery failure rate
- Log: Webhook endpoint returning errors
- Metric: `apgi_api_webhook_retry_count` elevated

#### Immediate Response (10 minutes)

1. **Identify abusive webhooks**

   ```sql
   SELECT task_id, webhook_url, attempts, status
   FROM webhook_deliveries
   WHERE status IN ('pending', 'retrying')
     AND attempts > 5
     AND created_at > NOW() - INTERVAL '1 hour';
   ```

2. **Pause affected webhooks**

   ```python
   from app.services.webhook_manager import WebhookManager
   wm = WebhookManager()
   wm.pause_webhook_deliveries(task_id="TASK_ID")
   ```

3. **Check for SSRF attempts**

   - Review webhook URLs for internal IP ranges
   - Check for metadata service URLs (169.254.169.254)
   - Verify DNS resolution targets

#### Investigation (Webhook Abuse)

1. **Analyze attack pattern**

   ```sql
   -- Group by target domain
   SELECT
     substring(webhook_url from 'https?://([^/]+)') as domain,
     count(*) as count,
     sum(attempts) as total_attempts
   FROM webhook_deliveries
   WHERE created_at > NOW() - INTERVAL '24 hours'
   GROUP BY domain
   ORDER BY count DESC;
   ```

2. **Check for internal network access**

   ```bash
   # If internal IPs found, check if any requests succeeded
   grep "resolved_ip.*10\." /var/log/apgi/webhook.log
   grep "resolved_ip.*192\.168\." /var/log/apgi/webhook.log
   ```

#### Recovery (Webhook Abuse)

1. **Clean up malicious webhooks**

   ```sql
   -- Cancel all pending deliveries to malicious URLs
   UPDATE webhook_deliveries
   SET status = 'cancelled',
       error_message = 'Cancelled: abusive endpoint'
   WHERE webhook_url LIKE '%SUSPICIOUS_DOMAIN%'
     AND status IN ('pending', 'retrying');
   ```

2. **Add to blocklist**

   ```python
   # Add domain/IP to webhook blocklist
   from app.config import settings
   settings.WEBHOOK_DOMAIN_BLOCKLIST.append("malicious.domain.com")
   ```

#### Post-Incident (Webhook Abuse)

- Review webhook validation logic
- Consider stricter URL validation (domain whitelist)
- Document new blocklist entries

---

### RB-003: Database Connection Issues

**Severity:** SEV-1 (if service down) / SEV-2 (if degraded)

#### Detection (Database Issues)

- Alert: `apgi_api_database_connections_active` near limit
- Error: "FATAL: sorry, too many clients already"
- Latency: Query response time > 5s

#### Immediate Response (5 minutes) - Database Issues

1. **Check connection pool status**

   ```sql
   -- PostgreSQL
   SELECT count(*), state
   FROM pg_stat_activity
   GROUP BY state;
   ```

2. **Identify blocking queries**

   ```sql
   SELECT pid, usename, application_name, client_addr,
          state, query_start, query
   FROM pg_stat_activity
   WHERE state = 'active'
     AND query_start < NOW() - INTERVAL '5 minutes';
   ```

3. **Kill long-running queries if safe**

   ```sql
   -- WARNING: Only kill non-essential queries
   SELECT pg_terminate_backend(pid)
   FROM pg_stat_activity
   WHERE pid != pg_backend_pid()
     AND query LIKE '%VACUUM%'  -- Example safe target
     AND query_start < NOW() - INTERVAL '30 minutes';
   ```

#### Investigation (Database Issues)

1. **Check connection pool configuration**

   ```python
   from app.config import settings
   print(f"Pool size: {settings.db_pool_size}")
   print(f"Max overflow: {settings.db_max_overflow}")
   ```

2. **Review recent connection leaks**

   ```bash
   # Check for connections from old application versions
   SELECT application_name, client_addr, count(*)
   FROM pg_stat_activity
   GROUP BY application_name, client_addr;
   ```

#### Recovery (30 minutes)

1. **Restart application servers** (if connection leak suspected)

   ```bash
   # Rolling restart
   kubectl rollout restart deployment/apgi-api -n production
   ```

2. **Temporarily increase pool size**

   ```python
   # Emergency config update
   settings.db_pool_size = 50  # from 20
   settings.db_max_overflow = 20  # from 10
   ```

3. **Monitor recovery**

   - Watch `apgi_api_database_connections_active`
   - Verify query latency returns to normal

#### Post-Incident (Database Issues)

- Review connection pool sizing
- Check for connection leaks in code
- Update query timeout settings

---

### RB-004: Redis/Celery Failure

**Severity:** SEV-1 (if task processing stopped) / SEV-2 (if degraded)

#### Detection (Redis/Celery)

- Alert: `apgi_api_celery_active_workers` = 0
- Queue depth: `apgi_api_task_queue_length` > 1000
- Error: Redis connection timeout

#### Immediate Response (5 minutes) - Redis/Celery

1. **Check Redis connectivity**

   ```bash
   redis-cli -h $REDIS_HOST ping
   redis-cli -h $REDIS_HOST info replication
   ```

2. **Check Celery worker status**

   ```bash
   celery -A app.celery_app status
   celery -A app.celery_app inspect stats
   ```

3. **Check for task backlog**

   ```python
   from app.celery_app import celery_app
   inspector = celery_app.control.inspect()
   queues = inspector.active_queues()
   scheduled = inspector.scheduled()
   ```

#### Investigation (Redis/Celery)

1. **Check Redis memory usage**

   ```bash
   redis-cli info memory | grep used_memory_human
   redis-cli info memory | grep maxmemory_human
   ```

2. **Check for OOM kills**

   ```bash
   dmesg | grep -i "killed process" | tail -20
   kubectl get events -n production --field-selector reason=Killing
   ```

3. **Review Celery logs**

   ```bash
   kubectl logs -n production -l app=celery-worker --tail=100
   ```

#### Recovery (Redis/Celery)

1. **Restart Celery workers**

   ```bash
   kubectl rollout restart deployment/celery-worker -n production
   kubectl rollout restart deployment/celery-beat -n production
   ```

2. **Clear stuck tasks if needed**

   ```python
   # Only if tasks are known to be stuck/broken
   from app.celery_app import celery_app
   celery_app.control.purge()  # WARNING: Removes all pending tasks
   ```

3. **Scale workers if queue is deep**

   ```bash
   kubectl scale deployment celery-worker --replicas=10 -n production
   ```

#### Post-Incident (Redis/Celery)

- Review Redis memory configuration
- Check for task result backend cleanup
- Implement queue depth alerting

---

### RB-005: Rate Limit Bypass

**Severity:** SEV-2 (if ongoing attack) / SEV-3 (if attempted)

#### Detection (Rate Limit Bypass)

- Alert: Unusual traffic patterns bypassing rate limits
- Log: Same IP using multiple API keys
- Metric: Request rate exceeding limits without 429 responses

#### Immediate Response (10 minutes) - Rate Limit Bypass

1. **Identify bypass method**

   ```sql
   -- Check for IP rotating API keys
   SELECT ip_address, count(distinct api_key) as key_count
   FROM audit_logs
   WHERE timestamp > NOW() - INTERVAL '1 hour'
     AND action = 'api_request'
   GROUP BY ip_address
   HAVING count(distinct api_key) > 10;
   ```

2. **Check for distributed attacks**

   ```sql
   -- Same user agent, multiple IPs
   SELECT user_agent,
          count(distinct ip_address) as ip_count,
          count(*) as request_count
   FROM audit_logs
   WHERE timestamp > NOW() - INTERVAL '10 minutes'
   GROUP BY user_agent
   HAVING count(distinct ip_address) > 100;
   ```

#### Investigation (Rate Limit Bypass)

1. **Analyze traffic pattern**

   ```bash
   # Extract attack signature
   tail -10000 /var/log/apgi/access.log | \
     awk '{print $1, $6, $7}' | \
     sort | uniq -c | sort -rn | head -20
   ```

2. **Identify compromised credentials**

   ```sql
   -- Check if legitimate user is being impersonated
   SELECT user_id, username, count(*) as request_count
   FROM audit_logs al
   JOIN users u ON al.user_id = u.user_id
   WHERE al.timestamp > NOW() - INTERVAL '1 hour'
     AND al.ip_address IN ('IP1', 'IP2', 'IP3')
   GROUP BY user_id, username;
   ```

#### Recovery (Rate Limit Bypass)

1. **Emergency IP blocklist**

   ```python
   # Add to WAF/firewall rules
   from app.middleware.rate_limiting import RateLimitMiddleware
   RateLimitMiddleware.block_ips(['IP1', 'IP2', 'IP3'])
   ```

2. **Revoke suspicious API keys**

   ```python
   # Bulk revoke for affected users
   for user_id in affected_users:
       auth_manager.revoke_all_user_api_keys(user_id, reason="rate_limit_bypass")
   ```

3. **Enable stricter rate limiting**

   ```python
   # Reduce limits temporarily
   settings.RATE_LIMIT_REQUESTS_PER_MINUTE = 30  # from 60
   settings.RATE_LIMIT_BURST_SIZE = 10  # from 20
   ```

#### Post-Incident (Rate Limit Bypass)

- Implement IP-based rate limiting in addition to key-based
- Review rate limit algorithm (consider sliding window)
- Add CAPTCHA for suspicious patterns

---

### RB-006: Data Breach Suspected

**Severity:** SEV-1 (always)

#### Detection (Data Breach)

- Alert: Unusual data access patterns
- Report: User reports unauthorized data access
- Log: Bulk data export by unexpected user

#### Immediate Response (15 minutes)

1. **Freeze suspicious access**

   ```sql
   -- Disable affected user accounts temporarily
   UPDATE users
   SET is_active = false, locked_until = NOW() + INTERVAL '24 hours'
   WHERE user_id IN (SELECT user_id FROM suspicious_activity);
   ```

2. **Revoke all sessions/tokens**

   ```python
   from app.services.auth_manager import AuthManager
   auth_manager.revoke_all_user_sessions(user_id)
   auth_manager.revoke_all_user_api_keys(user_id)
   ```

3. **Preserve logs**

   ```bash
   # Create snapshot of current logs
   cp /var/log/apgi/access.log /var/log/apgi/incident-$(date +%Y%m%d-%H%M%S).log
   # Ensure audit logs are backed up
   pg_dump -t audit_logs > /backup/audit-$(date +%Y%m%d-%H%M%S).sql
   ```

#### Investigation (Data Breach)

1. **Determine scope of breach**

   ```sql
   -- What data was accessed?
   SELECT action, resource_type, resource_id, timestamp, details
   FROM audit_logs
   WHERE user_id = 'SUSPECT_USER'
     AND timestamp > NOW() - INTERVAL '7 days'
   ORDER BY timestamp;
   ```

2. **Identify affected users**

   ```sql
   -- If session data was accessed
   SELECT DISTINCT s.user_id, u.email
   FROM session_data sd
   JOIN sessions s ON sd.session_id = s.session_id
   JOIN users u ON s.user_id = u.user_id
   WHERE sd.session_id IN ('SESSION_ID_1', 'SESSION_ID_2');
   ```

3. **Check for data exfiltration**

   ```sql
   -- Large data exports
   SELECT user_id, action, details->>'rows_exported' as rows_exported
   FROM audit_logs
   WHERE action = 'data_export'
     AND timestamp > NOW() - INTERVAL '24 hours'
     AND (details->>'rows_exported')::int > 1000;
   ```

#### Recovery (Data Breach)

1. **Notify affected parties**

   - Internal: Security team, legal, management
   - External: Affected users (per GDPR/CCPA requirements)
   - Regulators: If required by jurisdiction

2. **Force password resets for affected users**

   ```python
   for user_id in affected_users:
       auth_manager.force_password_reset(user_id)
   ```

3. **Enable enhanced monitoring**

   ```python
   # Increase audit logging granularity
   settings.AUDIT_LOG_LEVEL = 'verbose'
   settings.AUDIT_LOG_ALL_READS = True
   ```

#### Post-Incident (Data Breach)

- Conduct full security audit
- Review access controls
- Update data classification
- Implement additional DLP controls
- File required breach notifications

---

### RB-007: Capacity/Performance Event

**Severity:** SEV-1 (if service down) / SEV-2 (if degraded)

#### Detection (Capacity/Performance)

- Alert: CPU > 80% for 5 minutes
- Alert: Memory > 90%
- Alert: Response time p95 > 2s
- Alert: Error rate > 1%

#### Immediate Response (10 minutes) - Capacity/Performance

1. **Check current capacity**

   ```bash
   kubectl top pods -n production
   kubectl top nodes
   ```

2. **Identify resource consumers**

   ```python
   # Check task queue depth
   from app.middleware.metrics import task_queue_length
   current_depth = task_queue_length._value.get()

   # Check active sessions
   from app.middleware.metrics import active_sessions
   current_sessions = active_sessions._value.get()
   ```

3. **Check for resource leaks**

   ```bash
   # Memory leak detection
   ps aux | grep python | awk '{print $2, $4, $11}' | sort -k2 -rn | head
   ```

#### Investigation (Capacity/Performance)

1. **Profile slow endpoints**

   ```python
   # Enable profiling for specific endpoint
   from app.middleware.profiling import ProfilingMiddleware
   # Check X-Request-Duration headers in logs
   ```

2. **Analyze database performance**

   ```sql
   -- Find slow queries
   SELECT query, mean_exec_time, calls
   FROM pg_stat_statements
   ORDER BY mean_exec_time DESC
   LIMIT 10;
   ```

3. **Check for traffic spikes**

   ```sql
   -- Requests per minute
   SELECT
     date_trunc('minute', timestamp) as minute,
     count(*) as requests
   FROM audit_logs
   WHERE timestamp > NOW() - INTERVAL '1 hour'
   GROUP BY minute
   ORDER BY minute;
   ```

#### Recovery (Capacity/Performance)

1. **Horizontal scaling**

   ```bash
   # Scale API servers
   kubectl scale deployment apgi-api --replicas=10 -n production

   # Scale Celery workers
   kubectl scale deployment celery-worker --replicas=20 -n production
   ```

2. **Enable circuit breakers**

   ```python
   # Temporarily disable non-critical features
   settings.ENABLE_PROFILING = False
   settings.ENABLE_DETAILED_LOGGING = False
   ```

3. **Implement rate limiting** (if traffic spike)

   ```python
   # Emergency rate limiting
   settings.RATE_LIMIT_REQUESTS_PER_MINUTE = 30
   settings.RATE_LIMIT_BLOCK_DURATION = 300  # 5 minutes
   ```

4. **Database optimization** (if DB bottleneck)

   ```sql
   -- Analyze tables for query planner
   ANALYZE sessions;
   ANALYZE tasks;
   ANALYZE session_data;
   ```

#### Post-Incident (Capacity/Performance)

- Review auto-scaling policies
- Optimize slow queries
- Add caching for hot paths
- Update capacity planning models

---

## Emergency Contacts

| Role | Contact | Escalation Time |
| ---- | ------- | --------------- |
| On-call Engineer | PagerDuty | Immediate |
| Security Team | <security@apgi.example.com> | 15 minutes |
| Engineering Manager | <eng-manager@apgi.example.com> | 1 hour |
| CTO | <cto@apgi.example.com> | 4 hours |

---

## Useful Commands Reference

```bash
# Check service health
curl https://api.apgi.example.com/health

# View recent error logs
kubectl logs -n production -l app=apgi-api --tail=100 | grep ERROR

# Check database connections
psql $DATABASE_URL -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# Redis connectivity test
redis-cli -h $REDIS_HOST -p $REDIS_PORT ping

# Celery queue depth
celery -A app.celery_app inspect active

# Force password reset for user
python -c "from app.services.auth_manager import AuthManager; AuthManager().force_password_reset('USER_ID')"
```

---

*Document Version: 1.0*
*Last Updated: 2026-04-16*
*Next Review: 2026-07-16*
