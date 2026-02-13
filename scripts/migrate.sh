#!/bin/bash
# Database migration script for APGI Standalone API
# This script runs Alembic migrations with error handling

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Function to print status messages
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Parse command line arguments
MIGRATION_TARGET="${1:-head}"
USE_DOCKER="${2:-auto}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}APGI Standalone API - Database Migration${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to run migrations locally
run_local_migration() {
    print_info "Running migrations locally..."
    
    # Check if alembic is available
    if ! command -v alembic >/dev/null 2>&1; then
        print_error "Alembic is not installed or not in PATH"
        print_info "Install with: pip install alembic"
        return 1
    fi
    
    # Navigate to project root
    cd "$PROJECT_ROOT"
    
    # Check if alembic.ini exists
    if [ ! -f "alembic.ini" ]; then
        print_error "alembic.ini not found in $PROJECT_ROOT"
        return 1
    fi
    
    # Run migration
    print_info "Executing: alembic upgrade $MIGRATION_TARGET"
    if alembic upgrade "$MIGRATION_TARGET"; then
        print_status "Migration completed successfully"
        return 0
    else
        print_error "Migration failed"
        return 1
    fi
}

# Function to run migrations in Docker
run_docker_migration() {
    print_info "Running migrations in Docker container..."
    
    # Check if docker-compose is available
    DOCKER_COMPOSE_CMD=""
    if docker compose version >/dev/null 2>&1; then
        DOCKER_COMPOSE_CMD="docker compose"
    elif command -v docker-compose >/dev/null 2>&1; then
        DOCKER_COMPOSE_CMD="docker-compose"
    else
        print_error "Docker Compose is not installed"
        return 1
    fi
    
    # Navigate to deployment directory
    cd "$PROJECT_ROOT/deployment"
    
    # Check if docker-compose.yml exists
    if [ ! -f "docker-compose.yml" ]; then
        print_error "docker-compose.yml not found in $PROJECT_ROOT/deployment"
        return 1
    fi
    
    # Check if API container is running
    if ! $DOCKER_COMPOSE_CMD ps api | grep -q "Up"; then
        print_warning "API container is not running"
        print_info "Starting services..."
        $DOCKER_COMPOSE_CMD up -d
        
        # Wait for services to be ready
        print_info "Waiting for services to be ready..."
        sleep 10
    fi
    
    # Run migration in container
    print_info "Executing: $DOCKER_COMPOSE_CMD exec api alembic upgrade $MIGRATION_TARGET"
    if $DOCKER_COMPOSE_CMD exec -T api alembic upgrade "$MIGRATION_TARGET"; then
        print_status "Migration completed successfully"
        return 0
    else
        print_error "Migration failed"
        print_info "Check logs with: cd $PROJECT_ROOT/deployment && $DOCKER_COMPOSE_CMD logs api"
        return 1
    fi
}

# Determine whether to use Docker or local execution
if [ "$USE_DOCKER" = "auto" ]; then
    # Auto-detect: prefer Docker if available and running
    if docker info >/dev/null 2>&1; then
        cd "$PROJECT_ROOT/deployment" 2>/dev/null || true
        if [ -f "docker-compose.yml" ]; then
            DOCKER_COMPOSE_CMD=""
            if docker compose version >/dev/null 2>&1; then
                DOCKER_COMPOSE_CMD="docker compose"
            elif command -v docker-compose >/dev/null 2>&1; then
                DOCKER_COMPOSE_CMD="docker-compose"
            fi
            
            if [ -n "$DOCKER_COMPOSE_CMD" ] && $DOCKER_COMPOSE_CMD ps api 2>/dev/null | grep -q "Up"; then
                print_info "Detected running Docker environment"
                USE_DOCKER="yes"
            else
                print_info "Docker available but API container not running"
                USE_DOCKER="local"
            fi
        else
            USE_DOCKER="local"
        fi
    else
        USE_DOCKER="local"
    fi
fi

# Execute migration
if [ "$USE_DOCKER" = "yes" ] || [ "$USE_DOCKER" = "docker" ]; then
    if run_docker_migration; then
        exit 0
    else
        exit 1
    fi
else
    if run_local_migration; then
        exit 0
    else
        # If local migration fails, suggest Docker alternative
        echo ""
        print_info "Tip: You can also run migrations in Docker with:"
        print_info "  $0 $MIGRATION_TARGET docker"
        exit 1
    fi
fi
