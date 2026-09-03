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

### PII Encryption Key Rotation

`PII_ENCRYPTION_KEY` (app/database/encryption.py) is a Fernet key. Fernet
does not support re-keying in place: rotating it means decrypting every
`EncryptedString` column value with the old key and re-encrypting with the
new one before cutover, or the old ciphertext becomes unreadable the moment
the new key is deployed.

1. Generate a new key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
2. Run a one-off migration script that reads every `Participant` row with
   the old key active, decrypts `encrypted_contact_email` /
   `encrypted_demographics`, and re-writes them — this requires briefly
   holding both keys in the same process (old key to decrypt, new key to
   encrypt); never persist the old key value anywhere after this step.
3. Deploy the new `PII_ENCRYPTION_KEY` and restart API instances.
4. Rotate `AUDIT_SIGNING_KEY` (app/services/audit_signing.py) independently —
   it only affects newly-written audit entries going forward; existing
   entries stay verifiable against the key that was active when they were
   written, so record the rotation date if you need to verify old entries
   later.

### Audit Signing Key Rotation

See step 4 above — signing key rotation, unlike the encryption key, does not
require re-processing historical rows.

## Backup & Restore

Cloud SQL backup configuration and the restore-drill procedure live in
[`deployment/terraform/gcp/README.md`](../deployment/terraform/gcp/README.md#backup-configuration-and-restore-drill)
alongside the Terraform that provisions them, so the procedure and the
infrastructure it exercises stay in sync.

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
