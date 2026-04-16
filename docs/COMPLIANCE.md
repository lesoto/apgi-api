# APGI Compliance Control Matrix

This document maps APGI API implementation to industry security frameworks and compliance standards, specifically:

- **OWASP ASVS (Application Security Verification Standard)** v4.0
- **SOC 2 Trust Service Criteria**
- **GDPR** data lifecycle requirements

## Table of Contents

1. [OWASP ASVS Mappings](#owasp-asvs-mappings)
2. [SOC 2 Trust Service Criteria](#soc-2-trust-service-criteria)
3. [Evidence Links](#evidence-links)
4. [Implementation Status](#implementation-status)

---

## OWASP ASVS Mappings

### V1: Architecture, Design and Threat Modeling

| ASVS ID | Requirement | Implementation | Evidence |
| -------- | ------------ | ---------------- | ---------- |
| 1.1.1 | Secure SDLC | GitHub Actions CI/CD with security gates | `.github/workflows/ci.yml` |
| 1.1.2 | Security requirements | This compliance matrix document | `docs/COMPLIANCE.md` |
| 1.1.3 | Compliance scope | Explicit framework mappings in this doc | `docs/COMPLIANCE.md` |

### V2: Authentication

| ASVS ID | Requirement | Implementation | Evidence |
| -------- | ------------ | ---------------- | ---------- |
| 2.1.1 | Password strength | Password policy enforcement | `app/models/schemas.py` |
| 2.1.2 | Password change | Password change endpoint with validation | `app/routers/auth.py` |
| 2.1.3 | Password storage | bcrypt hashing with salt | `app/services/auth_manager.py` |
| 2.2.1 | MFA availability | TOTP-based MFA implementation | `app/models/schemas.py` |
| 2.2.2 | MFA enforcement | Per-user MFA enablement | `app/services/auth_manager.py` |
| 2.3.1 | Session management | JWT with configurable expiration | `app/config.py` |
| 2.3.2 | Session invalidation | Token revocation with denylist | `app/database/models.py` |
| 2.3.3 | Session timeout | Configurable token TTL | `app/config.py` |
| 2.4.1 | JWT signature | RS256/HS256 with strong keys | `app/middleware/authentication.py` |
| 2.4.2 | JWT validation | Signature + claims validation | `app/middleware/authentication.py` |
| 2.4.3 | JWT content | Minimal claims, no sensitive data | `app/middleware/authentication.py` |
| 2.5.1 | API key generation | Cryptographically random keys | `app/services/auth_manager.py` |
| 2.5.2 | API key storage | HMAC-SHA256 hashed | `app/database/models.py` |
| 2.5.3 | API key revocation | Soft delete with immediate effect | `app/routers/auth.py` |

### V3: Session Management

| ASVS ID | Requirement | Implementation | Evidence |
| -------- | ------------ | ---------------- | ---------- |
| 3.1.1 | Session identifier | UUID-based session IDs | `app/database/models.py` |
| 3.1.2 | Session uniqueness | Unique constraint enforcement | `app/database/models.py` |
| 3.2.1 | Session binding | User-session binding with validation | `app/services/session_manager.py` |
| 3.2.2 | Session integrity | Session state validation | `app/middleware/authentication.py` |
| 3.3.1 | Session timeout | Configurable TTL with cleanup | `app/config.py` |
| 3.3.2 | Idle timeout | Activity-based timeout tracking | `app/database/models.py` |
| 3.3.3 | Absolute timeout | Max session duration enforced | `app/config.py` |
| 3.4.1 | Concurrent sessions | Per-user session limits | `app/services/session_manager.py` |
| 3.4.2 | Session termination | Explicit logout endpoint | `app/routers/auth.py` |
| 3.5.1 | Session fixation | New session ID on auth | `app/services/auth_manager.py` |
| 3.5.2 | Session re-gen | Regenerate on privilege change | `app/services/auth_manager.py` |

### V4: Access Control

| ASVS ID | Requirement | Implementation | Evidence |
| -------- | ------------ | ---------------- | ---------- |
| 4.1.1 | Access control model | RBAC with roles in JWT | `app/database/models.py` |
| 4.1.2 | Resource access | Resource-level authorization | `app/services/authorization.py` |
| 4.1.3 | Access validation | Ownership verification on access | `app/services/task_execution/` |
| 4.1.4 | Deny by default | 403 for unauthorized access | `app/middleware/authentication.py` |
| 4.2.1 | Privilege escalation | Role-based restrictions | `app/services/authorization.py` |
| 4.2.2 | Administrative access | Admin role separation | `app/database/models.py` |

### V5: Validation, Sanitization and Encoding

| ASVS ID | Requirement | Implementation | Evidence |
| -------- | ------------ | ---------------- | ---------- |
| 5.1.1 | Input validation | Pydantic schema validation | `app/models/schemas.py` |
| 5.1.2 | Output encoding | JSON serialization with escaping | `app/main.py` |
| 5.1.3 | Canonicalization | URL normalization | `app/middleware/security_validation.py` |
| 5.2.1 | SQL injection | SQLAlchemy ORM parameterized queries | `app/database/connection.py` |
| 5.2.2 | NoSQL injection | MongoDB not used (PostgreSQL only) | N/A |
| 5.2.3 | OS command injection | No shell command execution | N/A |
| 5.2.4 | Path traversal | Input path validation | `app/middleware/security_validation.py` |
| 5.2.5 | SSRF prevention | URL whitelist for webhooks | `app/middleware/security_validation.py` |
| 5.2.6 | XML external entity | No XML parsing | N/A |
| 5.2.7 | XML injection | No XML endpoints | N/A |
| 5.2.8 | XPath injection | No XPath usage | N/A |

### V6: Stored Cryptography

| ASVS ID | Requirement | Implementation | Evidence |
| -------- | ------------ | ---------------- | ---------- |
| 6.1.1 | Data classification | PII identification in schema | `app/database/models.py` |
| 6.1.2 | Key generation | Cryptographically random keys | `app/config.py` |
| 6.1.3 | Key exchange | N/A (no key exchange protocol) | N/A |
| 6.2.1 | Algorithm selection | AES-256-GCM, bcrypt, SHA-256 | `app/middleware/` |
| 6.2.2 | Algorithm agility | Configurable algorithms | `app/config.py` |
| 6.2.3 | Deprecated algorithms | No MD5, SHA-1, or DES | Verified in code |
| 6.3.1 | Random values | Secrets module for tokens | `app/services/auth_manager.py` |
| 6.3.2 | Random GUIDs | UUID4 for identifiers | `app/database/models.py` |
| 6.4.1 | Secret management | Environment variable based | `app/config.py` |
| 6.4.2 | Key protection | Secret key rotation support | `app/config.py` |

### V7: Error Handling and Logging

| ASVS ID | Requirement | Implementation | Evidence |
| -------- | ------------ | ---------------- | ---------- |
| 7.1.1 | Error handling | Structured exception handling | `app/middleware/error_handler.py` |
| 7.1.2 | Error details | No stack traces in production | `app/main.py` |
| 7.1.3 | Exception handling | Global exception handlers | `app/middleware/error_handler.py` |
| 7.2.1 | Audit logging | Comprehensive audit trail | `app/database/models.py` |
| 7.2.2 | Audit events | User actions logged | `app/middleware/logging.py` |
| 7.2.3 | Log content | Structured JSON logs | `app/middleware/logging.py` |
| 7.3.1 | Log protection | Write-once log storage | `deployment/` |
| 7.3.2 | Log integrity | Log signing (optional) | Not implemented |
| 7.3.3 | Log retention | Configurable retention | `app/config.py` |

### V8: Data Protection

| ASVS ID | Requirement | Implementation | Evidence |
| -------- | ------------ | ---------------- | ---------- |
| 8.1.1 | Sensitive data | PII identification | `app/database/models.py` |
| 8.1.2 | Data retention | Retention policy config | `app/config.py` |
| 8.1.3 | Sensitive data cleanup | Data deletion workflows | `app/services/` |
| 8.2.1 | Client-side data | No sensitive data in client storage | Verified |
| 8.2.2 | Session storage | Server-side session storage | `app/database/models.py` |
| 8.2.3 | Sensitive data transmission | TLS 1.3 enforcement | `app/middleware/security_headers.py` |
| 8.3.1 | Sensitive data in memory | Secure memory handling | `app/services/` |
| 8.3.2 | Sensitive data in error logs | Log filtering for PII | `app/middleware/logging.py` |

### V9: Communication

| ASVS ID | Requirement | Implementation | Evidence |
| -------- | ------------ | ---------------- | ---------- |
| 9.1.1 | HTTPS enforcement | TLS redirect middleware | `app/middleware/security_headers.py` |
| 9.1.2 | HSTS | Strict-Transport-Security header | `app/middleware/security_headers.py` |
| 9.1.3 | TLS configuration | TLS 1.2+ only | Deployment config |
| 9.2.1 | Certificate validation | Server certificate validation | Deployment config |
| 9.2.2 | Cipher configuration | Strong cipher suites | Deployment config |

### V10: Malicious Code

| ASVS ID | Requirement | Implementation | Evidence |
| -------- | ------------ | ---------------- | ---------- |
| 10.1.1 | Dependency verification | Lock file usage | `requirements.txt` |
| 10.1.2 | Dependency scanning | Safety/Bandit in CI | `.github/workflows/ci.yml` |
| 10.2.1 | Unintended code execution | Input sanitization | `app/middleware/` |
| 10.2.2 | Deserialization | JSON only, no pickle | Verified |
| 10.3.1 | Integer overflow | Input validation | `app/models/schemas.py` |
| 10.3.2 | Out of bounds | Array bounds checking | `app/models/schemas.py` |

### V11: Business Logic

| ASVS ID | Requirement | Implementation | Evidence |
| -------- | ------------ | ---------------- | ---------- |
| 11.1.1 | Business logic security | Rate limiting | `app/middleware/rate_limiting.py` |
| 11.1.2 | Anti-automation | Rate limiting + CAPTCHA ready | `app/middleware/rate_limiting.py` |
| 11.1.3 | Flow integrity | Request ordering validation | `app/middleware/` |
| 11.1.4 | Time validation | Timestamp validation | `app/middleware/` |
| 11.1.5 | Number limits | Input range validation | `app/models/schemas.py` |

### V12: File and Resources

| ASVS ID | Requirement | Implementation | Evidence |
| -------- | ------------ | ---------------- | ---------- |
| 12.1.1 | File upload | No file upload endpoints | N/A |
| 12.2.1 | File download | No file download endpoints | N/A |
| 12.3.1 | File execution | No file execution | N/A |
| 12.4.1 | Storage exhaustion | Request size limits | `app/middleware/request_size_limit.py` |
| 12.4.2 | Resource management | Connection pooling | `app/database/connection.py` |
| 12.5.1 | Resource locking | Optimistic locking | `app/database/models.py` |

### V13: API and Web Service

| ASVS ID | Requirement | Implementation | Evidence |
| -------- | ------------ | ---------------- | ---------- |
| 13.1.1 | API security | REST API security guidelines | `docs/REST-API.md` |
| 13.1.2 | API documentation | OpenAPI specification | `API.html` |
| 13.1.3 | API validation | Request/response validation | `app/middleware/schema_validation.py` |
| 13.2.1 | JSON parsing | Secure JSON parsing | `app/main.py` |
| 13.2.2 | Content types | Content-Type validation | `app/middleware/schema_validation.py` |
| 13.2.3 | CSRF protection | State-changing POST validation | `app/middleware/csrf.py` |
| 13.2.4 | CORS | Strict CORS policy | `app/middleware/cors_config.py` |
| 13.2.5 | API versioning | Versioned API endpoints | `app/middleware/api_versioning.py` |
| 13.3.1 | API authentication | Token-based auth | `app/middleware/authentication.py` |
| 13.3.2 | API authorization | RBAC enforcement | `app/services/authorization.py` |

### V14: Configuration

| ASVS ID | Requirement | Implementation | Evidence |
| -------- | ------------ | ---------------- | ---------- |
| 14.1.1 | Build process | Automated CI/CD | `.github/workflows/ci.yml` |
| 14.1.2 | Dependency management | Pinned dependencies | `requirements.txt` |
| 14.1.3 | Security headers | Security headers middleware | `app/middleware/security_headers.py` |
| 14.1.4 | Error handling | Production error handling | `app/main.py` |
| 14.2.1 | Configuration secrets | Environment-based secrets | `app/config.py` |
| 14.2.2 | Secret rotation | Configurable secret rotation | `app/config.py` |
| 14.3.1 | Dependency scanning | Automated in CI | `.github/workflows/ci.yml` |
| 14.3.2 | Security patches | Automated updates | `.github/dependabot.yml` |

---

## SOC 2 Trust Service Criteria

### Common Criteria (CC)

| CC ID | Criteria | Implementation | Evidence |
| :----- | :-------- | :--------------- | :-------- |
| CC6.1 | Logical access security | Authentication & authorization controls | `app/middleware/authentication.py` |
| CC6.2 | Access removal | Account deactivation | `app/models/schemas.py` |
| CC6.3 | Access changes | Role modification logging | `app/database/models.py` |
| CC6.4 | Segregation of duties | Admin/user role separation | `app/database/models.py` |
| CC6.5 | Least privilege | RBAC with minimal permissions | `app/services/authorization.py` |
| CC6.6 | Access review | Audit logs for access review | `app/database/models.py` |
| CC6.7 | Credentials management | Secure credential storage | `app/services/auth_manager.py` |
| CC6.8 | Incident detection | Monitoring and alerting | `app/middleware/alerting.py` |
| CC7.1 | System operations | Infrastructure monitoring | `deployment/` |
| CC7.2 | System monitoring | Metrics collection | `app/middleware/metrics.py` |
| CC7.3 | System evaluation | Regular security assessments | This document |
| CC7.4 | Change management | Version control + CI/CD | `.github/workflows/ci.yml` |
| CC7.5 | Vulnerability management | Automated scanning | `.github/workflows/ci.yml` |
| CC8.1 | Change authorization | PR review requirements | Branch protection rules |

### Security (SE)

| SE ID | Criteria | Implementation | Evidence |
| :----- | :-------- | :--------------- | :-------- |
| SE1.1 | Security policies | Documented security controls | `docs/COMPLIANCE.md` |
| SE2.1 | Risk assessment | Threat modeling | `docs/THEORY.md` |
| SE3.1 | Security monitoring | Continuous monitoring | `app/middleware/metrics.py` |

### Availability (AV)

| AV ID | Criteria | Implementation | Evidence |
| :----- | :-------- | :--------------- | :-------- |
| AV1.1 | Availability monitoring | Health checks | `app/services/health_check.py` |
| AV1.2 | Capacity planning | Resource monitoring | `app/middleware/metrics.py` |
| AV1.3 | Incident response | Incident procedures | `docs/RUNBOOKS.md` |

### Confidentiality (CF)

| CF ID | Criteria | Implementation | Evidence |
| :----- | :-------- | :--------------- | :-------- |
| CF1.1 | Data classification | Data categorization | `app/database/models.py` |
| CF1.2 | Data access | Access controls | `app/services/authorization.py` |
| CF1.3 | Data transmission | Encryption in transit | `app/middleware/security_headers.py` |
| CF1.4 | Data storage | Encryption at rest | Database encryption |

### Privacy (PI)

| PI ID | Criteria | Implementation | Evidence |
| :----- | :-------- | :--------------- | :-------- |
| PI1.1 | Notice | Privacy notice | `docs/PRIVACY.md` |
| PI1.2 | Choice and consent | Consent management | `app/models/schemas.py` |
| PI1.3 | Collection | Data minimization | `app/database/models.py` |
| PI1.4 | Use and retention | Retention policies | `app/config.py` |
| PI1.5 | Access | Data subject access | `app/routers/users.py` |
| PI1.6 | Disclosure | Third-party disclosure controls | Webhook validation |
| PI1.7 | Security | Privacy security controls | All security controls |
| PI1.8 | Quality | Data accuracy | Validation middleware |
| PI1.9 | Monitoring | Privacy monitoring | Audit logging |
| PI1.10 | Enforcement | Privacy policy enforcement | `docs/PRIVACY.md` |

---

## Evidence Links

### Code Evidence

| Control | File Path | Line Numbers |
| :-------- | :--------- | :------------ |
| JWT Authentication | `app/middleware/authentication.py` | 1-500 |
| RBAC Implementation | `app/services/authorization.py` | 1-600 |
| Password Hashing | `app/services/auth_manager.py` | 1-650 |
| Session Management | `app/database/models.py` | 190-275 |
| API Key Storage | `app/database/models.py` | 488-540 |
| Audit Logging | `app/database/models.py` | 599-647 |
| Rate Limiting | `app/middleware/rate_limiting.py` | 1-350 |
| Input Validation | `app/middleware/schema_validation.py` | 1-450 |
| SQL Injection Prevention | `app/database/connection.py` | 1-200 |
| Security Headers | `app/middleware/security_headers.py` | 1-150 |
| Request Size Limits | `app/middleware/request_size_limit.py` | 1-180 |
| CORS Configuration | `app/middleware/cors_config.py` | 1-80 |
| CSRF Protection | `app/middleware/csrf.py` | 1-220 |
| Error Handling | `app/middleware/error_handler.py` | 1-300 |
| Metrics Collection | `app/middleware/metrics.py` | 1-618 |
| Alerting | `app/middleware/alerting.py` | 1-950 |

### Test Evidence

| Control | Test File | Test Cases |
| :-------- | :--------- | :---------- |
| Authentication | `tests/unit/test_auth.py` | 50+ test cases |
| Authorization | `tests/unit/test_authorization.py` | 40+ test cases |
| Input Validation | `tests/unit/test_validation.py` | 60+ test cases |
| Rate Limiting | `tests/integration/test_rate_limiting.py` | 20+ test cases |
| Security Headers | `tests/unit/test_security_headers.py` | 15+ test cases |
| Session Management | `tests/unit/test_session.py` | 30+ test cases |

### Documentation Evidence

| Document | Purpose |
| :------- | :------ |
| `docs/REST-API.md` | API security guidelines |
| `docs/DEPLOYMENT.md` | Security deployment practices |
| `docs/CONFIGURATION.md` | Security configuration |
| `docs/TESTING-COVERAGE.md` | Test coverage evidence |
| `docs/TROUBLESHOOTING.md` | Security incident guidance |

---

## Implementation Status

### Fully Implemented Controls

The following controls are fully implemented and tested:

- ✅ **Authentication Controls**: JWT, MFA, API keys, password policies
- ✅ **Access Controls**: RBAC, session management, resource authorization
- ✅ **Cryptographic Controls**: Password hashing, JWT signing, API key hashing
- ✅ **Input Validation**: Schema validation, size limits, SQL injection prevention
- ✅ **Logging & Monitoring**: Audit logs, metrics, alerting
- ✅ **Network Security**: TLS, CORS, security headers
- ✅ **Error Handling**: Structured errors, no information leakage

### In Progress Controls

The following controls are partially implemented and scheduled for completion:

- 🔄 **Data Retention**: Automated retention policy enforcement
- 🔄 **PII Handling**: Enhanced PII detection and classification
- 🔄 **Data Deletion**: Automated deletion workflows
- 🔄 **Log Signing**: Cryptographic log integrity verification

### Roadmap

| Quarter | Planned Controls |
| :------- | :--------------- |
| Q2 2026 | Complete privacy/data lifecycle controls |
| Q3 2026 | Implement log signing and integrity verification |
| Q4 2026 | Advanced threat detection and response automation |
| Q1 2027 | ISO 27001 alignment and certification preparation |

---

## Compliance Verification

### Automated Verification

The following compliance checks are automated in CI/CD:

1. **Static Analysis**: Bandit security scan on every PR
2. **Dependency Scanning**: Safety check for known vulnerabilities
3. **Secret Detection**: Automated secret scanning in commits
4. **Type Safety**: mypy --strict for type correctness
5. **Test Coverage**: 100% coverage requirement

### Manual Verification

Annual manual verification includes:

1. **Penetration Testing**: Third-party security assessment
2. **Code Review**: Security-focused code review
3. **Architecture Review**: Threat modeling updates
4. **Policy Review**: Compliance policy updates

### Audit Trail

All compliance activities are logged:

- CI/CD pipeline results (GitHub Actions)
- Security scan results (Bandit, Safety)
- Code review approvals
- Deployment approvals
- Incident response activities

---

## Contact

For compliance-related questions or to report security concerns:

- **Security Team**: <security@apgi.example.com>
- **Compliance Officer**: <compliance@apgi.example.com>
- **Incident Response**: <incident@apgi.example.com>

---

*Document Version: 1.0*
*Last Updated: 2026-04-16*
*Next Review: 2026-07-16*
