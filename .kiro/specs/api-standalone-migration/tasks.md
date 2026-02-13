# Implementation Plan: API Migration to Standalone Application

## Overview

This implementation plan breaks down the migration of the APGI REST API into a standalone application into discrete, incremental tasks. Each task builds on previous work and includes testing to validate functionality early. The migration will be performed in phases to ensure the standalone API maintains full compatibility with the legacy API while enabling independent deployment.

## Tasks

- [x] 1. Create standalone application directory structure
  - Create `standalone-api/` directory at project root
  - Create subdirectories: app/, tests/, deployment/, docs/, scripts/
  - Create app subdirectories: database/, middleware/, models/, routes/, services/, tasks/, utils/, alembic/
  - Create test subdirectories: unit/, integration/, property/
  - _Requirements: 1.1, 1.4_

- [x] 2. Set up configuration management system
  - [x] 2.1 Copy and adapt config.py from legacy API
    - Copy api/config.py to standalone-api/app/config.py
    - Update import paths to be self-contained
    - Add environment detection (ENVIRONMENT variable)
    - Add environment-specific validation (development vs production)
    - _Requirements: 2.1, 2.2, 2.3, 2.6, 13.1, 13.2, 13.3_
  
  - [x] 2.2 Write property test for configuration environment variable override
    - **Property 1: Configuration Environment Variable Override**
    - **Validates: Requirements 2.2**
  
  - [x] 2.3 Write property test for configuration validation error logging
    - **Property 2: Configuration Validation Error Logging**
    - **Validates: Requirements 2.5**
  
  - [x] 2.4 Create environment configuration files
    - Create .env.example with all configuration variables documented
    - Create .env.development with development defaults
    - Create .env.production template with production placeholders
    - _Requirements: 2.1, 13.4_

- [x] 3. Set up database layer
  - [x] 3.1 Copy and adapt database models and connection management
    - Copy api/database/ to standalone-api/app/database/
    - Update import paths to be self-contained
    - Ensure connection pooling configuration is present
    - _Requirements: 3.4, 3.5_
  
  - [x] 3.2 Initialize Alembic for database migrations
    - Run `alembic init app/alembic` in standalone-api directory
    - Configure alembic.ini with standalone database URL
    - Update alembic/env.py to import standalone models
    - Create initial migration from existing models
    - _Requirements: 3.1, 3.2, 3.3_
  
  - [x] 3.3 Write property test for database migration round-trip
    - **Property 3: Database Migration Round-Trip**
    - **Validates: Requirements 3.6**
  
  - [-] 3.4 Write unit tests for database connection and initialization
    - Test database initialization creates all tables
    - Test connection pooling configuration
    - Test database health check on startup
    - _Requirements: 3.5_

- [x] 4. Implement authentication and authorization
  - [x] 4.1 Copy and adapt authentication services
    - Copy api/services/auth_manager.py to standalone-api/app/services/
    - Copy api/services/authorization.py to standalone-api/app/services/
    - Update import paths to be self-contained
    - Ensure JWT secret key validation is present
    - _Requirements: 8.1, 8.2, 8.3, 8.7_
  
  - [~] 4.2 Write property test for JWT token validation on protected routes
    - **Property 5: JWT Token Validation on Protected Routes**
    - **Validates: Requirements 8.4**
  
  - [~] 4.3 Write property test for password hashing with bcrypt
    - **Property 6: Password Hashing with Bcrypt**
    - **Validates: Requirements 8.7**
  
  - [~] 4.4 Write unit tests for JWT token generation and verification
    - Test access token creation and verification
    - Test refresh token creation and verification
    - Test token expiration handling
    - Test invalid token rejection
    - _Requirements: 8.2, 8.3, 8.4_

- [x] 6. Implement middleware stack
  - [x] 6.1 Copy and adapt authentication middleware
    - Copy api/middleware/authentication.py to standalone-api/app/middleware/
    - Update import paths to be self-contained
    - Ensure public path exclusions are correct
    - _Requirements: 8.1, 8.4_
  
  - [x] 6.2 Copy and adapt CORS middleware configuration
    - Copy CORS configuration from api/main.py
    - Add CORS configuration to standalone app creation
    - Ensure environment variable configuration works
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_
  
  - [~] 6.3 Write property test for CORS headers on all responses
    - **Property 4: CORS Headers on All Responses**
    - **Validates: Requirements 7.3, 7.4**
  
  - [x] 6.4 Copy and adapt remaining middleware components
    - Copy api/middleware/csrf.py to standalone-api/app/middleware/
    - Copy api/middleware/rate_limiting.py to standalone-api/app/middleware/
    - Copy api/middleware/logging.py to standalone-api/app/middleware/
    - Copy api/middleware/metrics.py to standalone-api/app/middleware/
    - Copy api/middleware/alerting.py to standalone-api/app/middleware/
    - Copy api/middleware/deprecation.py to standalone-api/app/middleware/
    - Copy api/middleware/request_size_limit.py to standalone-api/app/middleware/
    - Copy api/middleware/schema_validation.py to standalone-api/app/middleware/
    - Update all import paths to be self-contained
    - _Requirements: 8.5, 8.6, 10.2, 10.4, 16.3, 20.1, 20.2_
  
  - [~] 6.5 Write property tests for logging middleware
    - **Property 7: Structured JSON Logging Format**
    - **Property 8: Request Logging Completeness**
    - **Property 9: Request ID Propagation**
    - **Property 10: Error Logging with Context**
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.7**
  
  - [~] 6.6 Write property test for request size limiting
    - **Property 30: Request Size Limiting**
    - **Validates: Requirements 20.2**
  
  - [~] 6.7 Write property test for response compression
    - **Property 29: Response Compression for Large Responses**
    - **Validates: Requirements 20.1**

- [x] 7. Implement session management service
  - [x] 7.1 Copy and adapt session manager
    - Copy api/services/session_manager.py to standalone-api/app/services/
    - Update import paths to be self-contained
    - Ensure Redis and PostgreSQL integration works
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7_
  
  - [~] 7.2 Write property test for session concurrent modification prevention
    - **Property 22: Session Concurrent Modification Prevention**
    - **Validates: Requirements 18.8**
  
  - [~] 7.3 Write unit tests for session lifecycle
    - Test session creation
    - Test session state transitions (created → running → paused → stopped)
    - Test invalid state transition rejection
    - Test session deletion
    - Test session expiration
    - _Requirements: 18.3, 18.4, 18.5, 18.6, 18.7_

- [x] 8. Implement Celery task queue
  - [x] 8.1 Copy and adapt Celery configuration
    - Copy api/celery_app.py to standalone-api/app/celery_app.py
    - Copy api/tasks/ to standalone-api/app/tasks/
    - Update import paths to be self-contained
    - Ensure Redis broker and backend configuration works
    - _Requirements: 15.1, 15.2, 15.3, 15.6_
  
  - [~] 8.2 Write property test for task status retrieval
    - **Property 14: Task Status Retrieval**
    - **Validates: Requirements 15.4**
  
  - [~] 8.3 Write property test for task result retrieval
    - **Property 15: Task Result Retrieval**
    - **Validates: Requirements 15.5**
  
  - [~] 8.4 Write property test for task serialization round-trip
    - **Property 16: Task Serialization Round-Trip**
    - **Validates: Requirements 15.8**
  
  - [~] 8.5 Write unit tests for task execution
    - Test task submission
    - Test task status checking
    - Test task result retrieval
    - Test task timeout handling
    - _Requirements: 15.4, 15.5, 15.6_

- [x] 10. Implement route handlers
  - [x] 10.1 Copy and adapt authentication routes
    - Copy api/routes/auth.py to standalone-api/app/routes/
    - Update import paths to be self-contained
    - _Requirements: 11.1, 11.2, 11.3, 11.4_
  
  - [x] 10.2 Copy and adapt user management routes
    - Copy api/routes/users.py to standalone-api/app/routes/
    - Update import paths to be self-contained
    - _Requirements: 11.1, 11.2, 11.3, 11.4_
  
  - [x] 10.3 Copy and adapt session management routes
    - Copy api/routes/sessions.py to standalone-api/app/routes/
    - Update import paths to be self-contained
    - _Requirements: 11.1, 11.2, 11.3, 11.4_
  
  - [x] 10.4 Copy and adapt state query routes
    - Copy api/routes/state.py to standalone-api/app/routes/
    - Update import paths to be self-contained
    - _Requirements: 11.1, 11.2, 11.3, 11.4_
  
  - [x] 10.5 Copy and adapt task routes
    - Copy api/routes/tasks.py to standalone-api/app/routes/
    - Update import paths to be self-contained
    - _Requirements: 11.1, 11.2, 11.3, 11.4_
  
  - [x] 10.6 Copy and adapt export routes
    - Copy api/routes/export.py to standalone-api/app/routes/
    - Update import paths to be self-contained
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 17.1, 17.2_
  
  - [~] 10.7 Write property tests for export functionality
    - **Property 19: Export Authorization**
    - **Property 20: Export Metadata Completeness**
    - **Property 21: Export Content-Type Headers**
    - **Validates: Requirements 17.3, 17.4, 17.6**
  
  - [x] 10.8 Copy and adapt health check routes
    - Copy api/routes/health.py to standalone-api/app/routes/
    - Update import paths to be self-contained
    - Ensure /health, /health/ready, and /health/live endpoints exist
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_
  
  - [x] 10.9 Copy and adapt metrics routes
    - Copy api/routes/metrics.py to standalone-api/app/routes/
    - Update import paths to be self-contained
    - _Requirements: 10.4, 10.5_
  
  - [x] 10.10 Copy and adapt version routes
    - Copy api/routes/version.py to standalone-api/app/routes/
    - Update import paths to be self-contained
    - _Requirements: 16.1, 16.2, 16.5_
  
  - [~] 10.11 Write property tests for deprecation handling
    - **Property 17: Deprecation Headers on Deprecated Endpoints**
    - **Property 18: Deprecated Endpoint Logging**
    - **Validates: Requirements 16.3, 16.4, 16.6**

- [x] 11. Implement error handling
  - [x] 11.1 Copy and adapt exception definitions and handlers
    - Copy api/exceptions.py to standalone-api/app/exceptions.py
    - Copy api/exception_handlers.py to standalone-api/app/exception_handlers.py
    - Update import paths to be self-contained
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7_
  
  - [~] 11.2 Write property tests for error responses
    - **Property 23: Request Validation Error Response**
    - **Property 24: Authentication Failure Response**
    - **Property 25: Authorization Failure Response**
    - **Property 26: Not Found Response**
    - **Property 27: Server Error Response and Logging**
    - **Property 28: Sensitive Information Exclusion from Errors**
    - **Validates: Requirements 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7**

- [x] 12. Create main application entry point
  - [x] 12.1 Copy and adapt main.py
    - Copy api/main.py to standalone-api/app/main.py
    - Update all import paths to use standalone app structure
    - Ensure middleware stack is configured in correct order
    - Ensure all routes are registered
    - Ensure lifespan events handle startup and shutdown
    - _Requirements: 1.3, 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7_
  
  - [~] 12.2 Write unit tests for application startup and shutdown
    - Test application starts successfully with valid configuration
    - Test application refuses to start with invalid production configuration
    - Test graceful shutdown closes database connections
    - Test graceful shutdown closes Redis connections
    - Test graceful shutdown waits for in-flight requests
    - _Requirements: 1.3, 2.3, 13.6, 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7_

- [x] 13. Create dependency management files
  - [x] 13.1 Create requirements.txt for standalone API
    - Extract API-specific dependencies from main requirements.txt
    - Include: FastAPI, uvicorn, SQLAlchemy, alembic, psycopg2-binary, redis, celery, pyjwt, bcrypt, pydantic, prometheus-client, python-dotenv
    - Exclude: GUI packages (matplotlib, seaborn, Pillow), ML packages (torch, transformers), JAX packages
    - Specify minimum version constraints for critical dependencies
    - _Requirements: 4.1, 4.3, 4.4, 4.5_
  
  - [x] 13.2 Create requirements-dev.txt for development dependencies
    - Include: pytest, pytest-asyncio, pytest-cov, hypothesis, black, flake8, mypy, isort
    - _Requirements: 4.1_
  
  - [x] 13.3 Create pyproject.toml for package metadata
    - Define package name, version, description, authors
    - Define entry points for CLI commands
    - Define build system requirements
    - _Requirements: 4.2_
  
  - [x] 13.4 Create dependency checker utility
    - Copy api/utils/dependency_checker.py if it exists, or create new
    - Validate all required packages are installed on startup
    - Provide clear error messages for missing dependencies
    - _Requirements: 4.6_

- [x] 14. Create Docker deployment configuration
  - [x] 14.1 Create production Dockerfile
    - Use multi-stage build (builder + runtime)
    - Install only standalone requirements.txt dependencies
    - Run as non-root user (create apgi user with UID 1000)
    - Expose port 8000
    - Add health check using /health endpoint
    - Set CMD to run uvicorn
    - _Requirements: 5.1, 5.2, 5.3, 5.5, 5.6, 5.7_
  
  - [x] 14.2 Create development Dockerfile
    - Similar to production but with hot-reload enabled
    - Install both requirements.txt and requirements-dev.txt
    - Mount source code as volume for development
    - _Requirements: 5.1, 5.3_
  
  - [x] 14.3 Create docker-compose.yml for local development
    - Define services: postgres, redis, api, celery_worker
    - Configure health checks for postgres and redis
    - Configure depends_on for correct startup order
    - Mount configuration files as volumes
    - Configure persistent volumes for postgres and redis data
    - Expose ports: API (8000), PostgreSQL (5432), Redis (6379)
    - _Requirements: 5.4, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_
  
  - [x] 14.4 Create docker-compose.prod.yml for production-like testing
    - Similar to development but uses production Dockerfile
    - No volume mounts for source code
    - Production environment variables
    - _Requirements: 5.4, 6.1_

- [ ] 15. Create deployment validation tests
  - [~] 15.1 Write smoke tests for deployed application
    - Test health endpoints respond correctly
    - Test authentication flow works end-to-end
    - Test session creation and management works
    - Test task submission and retrieval works
    - _Requirements: 9.1, 9.2, 9.3_
  
  - [~] 15.2 Write load tests for performance validation
    - Test API handles expected load (requests per second)
    - Test response times under load
    - Test graceful degradation under overload
    - _Requirements: 20.1, 20.2, 20.6_

- [x] 16. Create documentation
  - [x] 16.1 Create main README.md
    - Overview of standalone API
    - Quick start guide for local development
    - Link to detailed documentation
    - _Requirements: 12.1_
  
  - [x] 16.2 Create DEPLOYMENT.md
    - Step-by-step production deployment instructions
    - Docker deployment guide
    - Kubernetes deployment guide
    - Environment variable configuration
    - Database migration instructions
    - Celery worker setup instructions
    - _Requirements: 12.3, 12.4, 12.5, 12.6_
  
  - [x] 16.3 Create CONFIGURATION.md
    - Document all environment variables with descriptions and examples
    - Document configuration validation rules
    - Document environment-specific settings (development vs production)
    - _Requirements: 12.2_
  
  - [x] 16.4 Create MIGRATION.md
    - Document differences from legacy API (if any)
    - Migration guide for existing deployments
    - Rollback procedures
    - _Requirements: 11.6_
  
  - [x] 16.5 Create troubleshooting guide
    - Common issues and solutions
    - Debugging tips
    - Log analysis guidance
    - _Requirements: 12.7_

- [x] 17. Create utility scripts
  - [x] 17.1 Create start.sh for development
    - Check dependencies
    - Start docker-compose
    - Run database migrations
    - Display API URL and docs URL
    - _Requirements: 12.3_
  
  - [x] 17.2 Create migrate.sh for database migrations
    - Run alembic upgrade head
    - Handle errors gracefully
    - _Requirements: 12.5_
  
  - [x] 17.3 Create health_check.sh for monitoring
    - Check /health/ready endpoint
    - Exit with appropriate code for monitoring systems
    - _Requirements: 9.1, 9.2_


- [~] 18. Final checkpoint - Complete system validation
  - Ensure all tests pass, ask the user if questions arise.
