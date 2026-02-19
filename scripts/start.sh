#!/bin/bash
# Start script for APGI Standalone API development environment
# This script checks dependencies, starts docker-compose, runs migrations, and displays URLs

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

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}APGI Standalone API - Development Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

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

# Check dependencies
echo -e "${BLUE}Checking dependencies...${NC}"
echo ""

MISSING_DEPS=0

if command_exists docker; then
    print_status "Docker is installed"
else
    print_error "Docker is not installed"
    MISSING_DEPS=1
fi

if command_exists docker-compose || docker compose version >/dev/null 2>&1; then
    print_status "Docker Compose is installed"
    # Determine which command to use
    if docker compose version >/dev/null 2>&1; then
        DOCKER_COMPOSE_CMD="docker compose"
    else
        DOCKER_COMPOSE_CMD="docker-compose"
    fi
else
    print_error "Docker Compose is not installed"
    MISSING_DEPS=1
fi

if [ $MISSING_DEPS -eq 1 ]; then
    echo ""
    print_error "Missing required dependencies. Please install them and try again."
    exit 1
fi

echo ""

# Check if Docker daemon is running
if ! docker info >/dev/null 2>&1; then
    print_error "Docker daemon is not running. Please start Docker and try again."
    exit 1
fi

print_status "Docker daemon is running"
echo ""

# Navigate to deployment directory
cd "$PROJECT_ROOT/deployment"

# Check if .env.development exists
if [ ! -f "$PROJECT_ROOT/.env.development" ]; then
    print_warning ".env.development not found. Creating from .env.example..."
    if [ -f "$PROJECT_ROOT/.env.example" ]; then
        cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env.development"
        print_status "Created .env.development"
    else
        print_error ".env.example not found. Cannot create .env.development"
        exit 1
    fi
fi

echo ""

# Start docker-compose services
echo -e "${BLUE}Starting Docker services...${NC}"
echo ""

$DOCKER_COMPOSE_CMD up -d

echo ""
print_status "Docker services started"
echo ""

# Wait for services to be healthy
echo -e "${BLUE}Waiting for services to be ready...${NC}"
echo ""

MAX_WAIT=60
WAIT_COUNT=0

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    POSTGRES_HEALTHY=$($DOCKER_COMPOSE_CMD ps postgres | grep -c "healthy" || echo "0")
    REDIS_HEALTHY=$($DOCKER_COMPOSE_CMD ps redis | grep -c "healthy" || echo "0")
    
    if [ "$POSTGRES_HEALTHY" -gt 0 ] && [ "$REDIS_HEALTHY" -gt 0 ]; then
        break
    fi
    
    echo -n "."
    sleep 2
    WAIT_COUNT=$((WAIT_COUNT + 2))
done

echo ""

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    print_warning "Services did not become healthy within ${MAX_WAIT}s. Continuing anyway..."
else
    print_status "PostgreSQL is healthy"
    print_status "Redis is healthy"
fi

echo ""

# Run database migrations
echo -e "${BLUE}Running database migrations...${NC}"
echo ""

# Execute migrations inside the API container
if $DOCKER_COMPOSE_CMD exec -T api alembic upgrade head 2>/dev/null; then
    print_status "Database migrations completed successfully"
else
    print_warning "Failed to run migrations (container may still be starting). You can run them manually with:"
    print_info "  cd $PROJECT_ROOT/deployment && $DOCKER_COMPOSE_CMD exec api alembic upgrade head"
fi

echo ""

# Display service URLs
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Services are ready!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}API URL:${NC}          http://localhost:8000"
echo -e "${BLUE}API Docs:${NC}         http://localhost:8000/docs"
echo -e "${BLUE}API ReDoc:${NC}        http://localhost:8000/redoc"
echo -e "${BLUE}Health Check:${NC}     http://localhost:8000/health"
echo -e "${BLUE}Metrics:${NC}          http://localhost:8000/metrics"
echo ""
echo -e "${BLUE}PostgreSQL:${NC}       localhost:5432"
echo -e "${BLUE}  Database:${NC}       apgi_api_dev"
echo -e "${BLUE}  User:${NC}           apgi_dev"
echo -e "${BLUE}  Password:${NC}       dev_password"
echo ""
echo -e "${BLUE}Redis:${NC}            localhost:6379"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo -e "  View logs:        cd $PROJECT_ROOT/deployment && $DOCKER_COMPOSE_CMD logs -f"
echo -e "  View API logs:    cd $PROJECT_ROOT/deployment && $DOCKER_COMPOSE_CMD logs -f api"
echo -e "  Stop services:    cd $PROJECT_ROOT/deployment && $DOCKER_COMPOSE_CMD down"
echo -e "  Restart API:      cd $PROJECT_ROOT/deployment && $DOCKER_COMPOSE_CMD restart api"
echo -e "  Run migrations:   cd $PROJECT_ROOT/deployment && $DOCKER_COMPOSE_CMD exec api alembic upgrade head"
echo ""
