#!/bin/bash

# APGI API Database Seeding Script
# Seeds the database with test data for development and testing

set -e  # Exit on any error

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKER_COMPOSE_FILE="$PROJECT_ROOT/deployment/docker-compose.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Help function
show_help() {
    cat << EOF
APGI API Database Seeding Script

Usage: $0 [OPTIONS] [COMMAND]

Commands:
    users          Seed user accounts
    sessions       Seed session data
    tasks          Seed task data
    all            Seed all data types (default)

Options:
    -e, --env ENV      Environment (development, staging, test) [default: development]
    -m, --mode MODE    Execution mode (docker, local) [default: auto]
    -f, --force        Force reseeding (drop existing data)
    -h, --help         Show this help message

Examples:
    $0 users                    # Seed users in development
    $0 all --env test           # Seed all data for test environment
    $0 sessions --mode docker   # Seed sessions using Docker
    $0 all --force              # Force reseed all data

Environment Variables:
    SEED_USERS_COUNT    Number of users to create [default: 10]
    SEED_SESSIONS_COUNT Number of sessions per user [default: 5]
    SEED_TASKS_COUNT    Number of tasks per session [default: 3]

EOF
}

# Default values
ENVIRONMENT="development"
MODE="auto"
FORCE=false
COMMAND="all"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -m|--mode)
            MODE="$2"
            shift 2
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        users|sessions|tasks|all)
            COMMAND="$1"
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate environment
case $ENVIRONMENT in
    development|staging|test)
        ;;
    *)
        log_error "Invalid environment: $ENVIRONMENT. Must be development, staging, or test."
        exit 1
        ;;
esac

# Check if Docker is running and should be used
check_docker_mode() {
    if [[ "$MODE" == "docker" ]]; then
        return 0
    elif [[ "$MODE" == "local" ]]; then
        return 1
    else
        # Auto mode - check if Docker is running and compose file exists
        if command -v docker &> /dev/null && docker info &> /dev/null; then
            if [[ -f "$DOCKER_COMPOSE_FILE" ]]; then
                return 0
            fi
        fi
        return 1
    fi
}

# Execute Python seeding script
run_seeder() {
    local script_name="$1"
    local docker_mode="$2"

    log_info "Running seeder: $script_name"

    if [[ "$docker_mode" == "true" ]]; then
        # Run in Docker container
        cd "$PROJECT_ROOT"
        docker-compose -f "$DOCKER_COMPOSE_FILE" exec -T api python3 -m scripts.seeders."$script_name" \
            --env "$ENVIRONMENT" $([[ "$FORCE" == "true" ]] && echo "--force")
    else
        # Run locally
        cd "$PROJECT_ROOT"
        python -m scripts.seeders."$script_name" \
            --env "$ENVIRONMENT" $([[ "$FORCE" == "true" ]] && echo "--force")
    fi
}

# Main execution
main() {
    log_info "Starting database seeding for environment: $ENVIRONMENT"

    # Check Docker mode
    if check_docker_mode; then
        DOCKER_MODE=true
        log_info "Using Docker execution mode"
    else
        DOCKER_MODE=false
        log_info "Using local execution mode"
    fi

    # Execute seeding based on command
    case $COMMAND in
        users)
            run_seeder "seed_users" "$DOCKER_MODE"
            ;;
        sessions)
            run_seeder "seed_sessions" "$DOCKER_MODE"
            ;;
        tasks)
            run_seeder "seed_tasks" "$DOCKER_MODE"
            ;;
        all)
            log_info "Seeding all data types..."
            run_seeder "seed_users" "$DOCKER_MODE"
            run_seeder "seed_sessions" "$DOCKER_MODE"
            run_seeder "seed_tasks" "$DOCKER_MODE"
            ;;
    esac

    log_success "Database seeding completed successfully!"
}

# Run main function
main "$@"
