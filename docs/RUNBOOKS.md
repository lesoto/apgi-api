# APGI API Production Runbooks

## Key Rotation

### JWT Secret Key Rotation

1. Generate a new 32+ character random string.
2. Update `JWT_SECRET_KEY` in production environment.
3. Perform a rolling restart of all API instances.
4. *Note*: This will invalidate all existing sessions. Users must re-login.

### Stripe Key Rotation

1. Update `STRIPE_SECRET_KEY` and `STRIPE_PUBLISHABLE_KEY`.
2. Update `STRIPE_WEBHOOK_SECRET` from the Stripe dashboard.
3. Restart API instances.

## Incident Handling

### High Latency (P99 > 1s)

1. Check `apgi_api_database_query_duration_seconds` for slow SQL.
2. Monitor `apgi_api_redis_connections_active` for connection exhaustion.
3. Verify if `PROFILING_ENABLED` is accidentally set to `true` in production.

### Database Connection Exhaustion

1. Increase `POOL_SIZE` and `MAX_OVERFLOW` in config.
2. Identify "leaky" sessions that don't close connections (search for `DB Pool Status` warnings in logs).

## Performance Tuning

- **Memory Usage**: If `apgi_api_memory_usage_bytes` exceeds 80% of container limit, reduce `POOL_SIZE` or check for memory leaks in task execution.
- **Rate Limiting**: Adjust `RATE_LIMIT_PER_MINUTE` if legitimate users are receiving 429 errors.
