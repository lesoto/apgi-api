#!/bin/bash
# Health check script for APGI Standalone API
# This script checks the /health/ready endpoint and exits with appropriate codes for monitoring systems
# Exit codes: 0 = healthy, 1 = unhealthy, 2 = connection error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
API_URL="${API_URL:-http://localhost:8000}"
HEALTH_ENDPOINT="${HEALTH_ENDPOINT:-/health/ready}"
TIMEOUT="${TIMEOUT:-10}"
VERBOSE="${VERBOSE:-false}"
QUIET="${QUIET:-false}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--url)
            API_URL="$2"
            shift 2
            ;;
        -e|--endpoint)
            HEALTH_ENDPOINT="$2"
            shift 2
            ;;
        -t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE="true"
            shift
            ;;
        -q|--quiet)
            QUIET="true"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Health check script for APGI Standalone API"
            echo ""
            echo "Options:"
            echo "  -u, --url URL          API base URL (default: http://localhost:8000)"
            echo "  -e, --endpoint PATH    Health endpoint path (default: /health/ready)"
            echo "  -t, --timeout SECONDS  Request timeout in seconds (default: 10)"
            echo "  -v, --verbose          Enable verbose output"
            echo "  -q, --quiet            Suppress all output (only exit codes)"
            echo "  -h, --help             Show this help message"
            echo ""
            echo "Environment variables:"
            echo "  API_URL                API base URL"
            echo "  HEALTH_ENDPOINT        Health endpoint path"
            echo "  TIMEOUT                Request timeout"
            echo "  VERBOSE                Enable verbose output (true/false)"
            echo "  QUIET                  Suppress output (true/false)"
            echo ""
            echo "Exit codes:"
            echo "  0 - Service is healthy"
            echo "  1 - Service is unhealthy"
            echo "  2 - Connection error or timeout"
            echo ""
            echo "Examples:"
            echo "  $0"
            echo "  $0 --url http://api.example.com:8000"
            echo "  $0 --endpoint /health/live --timeout 5"
            echo "  $0 --quiet  # For use in monitoring scripts"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 2
            ;;
    esac
done

# Function to print messages (respects quiet mode)
print_status() {
    if [ "$QUIET" != "true" ]; then
        echo -e "${GREEN}✓${NC} $1"
    fi
}

print_error() {
    if [ "$QUIET" != "true" ]; then
        echo -e "${RED}✗${NC} $1" >&2
    fi
}

print_warning() {
    if [ "$QUIET" != "true" ]; then
        echo -e "${YELLOW}⚠${NC} $1" >&2
    fi
}

print_info() {
    if [ "$QUIET" != "true" ] && [ "$VERBOSE" = "true" ]; then
        echo -e "${BLUE}ℹ${NC} $1"
    fi
}

# Construct full URL
FULL_URL="${API_URL}${HEALTH_ENDPOINT}"

print_info "Checking health endpoint: $FULL_URL"
print_info "Timeout: ${TIMEOUT}s"

# Check if curl is available
if ! command -v curl >/dev/null 2>&1; then
    print_error "curl is not installed. Please install curl to use this script."
    exit 2
fi

# Perform health check
HTTP_CODE=$(curl -s -o /tmp/health_response_$$.json -w "%{http_code}" --max-time "$TIMEOUT" "$FULL_URL" 2>/dev/null)
CURL_EXIT_CODE=$?

# Check for connection errors
if [ $CURL_EXIT_CODE -ne 0 ]; then
    case $CURL_EXIT_CODE in
        6)
            print_error "Could not resolve host: $API_URL"
            ;;
        7)
            print_error "Failed to connect to $API_URL"
            ;;
        28)
            print_error "Connection timeout after ${TIMEOUT}s"
            ;;
        *)
            print_error "Connection error (curl exit code: $CURL_EXIT_CODE)"
            ;;
    esac
    rm -f /tmp/health_response_$$.json
    exit 2
fi

# Parse response
if [ -f /tmp/health_response_$$.json ]; then
    RESPONSE=$(cat /tmp/health_response_$$.json)
    rm -f /tmp/health_response_$$.json
else
    RESPONSE=""
fi

print_info "HTTP Status Code: $HTTP_CODE"

# Check HTTP status code
if [ "$HTTP_CODE" = "200" ]; then
    print_status "Service is healthy"
    
    # Parse and display additional information if verbose
    if [ "$VERBOSE" = "true" ] && [ -n "$RESPONSE" ]; then
        # Try to extract status from JSON response
        if command -v jq >/dev/null 2>&1; then
            print_info "Response details:"
            echo "$RESPONSE" | jq '.' 2>/dev/null || echo "$RESPONSE"
        else
            print_info "Response: $RESPONSE"
        fi
    fi
    
    exit 0
elif [ "$HTTP_CODE" = "503" ]; then
    print_error "Service is unhealthy (503 Service Unavailable)"
    
    # Try to show dependency status if available
    if [ "$VERBOSE" = "true" ] && [ -n "$RESPONSE" ]; then
        if command -v jq >/dev/null 2>&1; then
            DEPENDENCIES=$(echo "$RESPONSE" | jq -r '.dependencies // empty' 2>/dev/null)
            if [ -n "$DEPENDENCIES" ]; then
                print_info "Dependency status:"
                echo "$DEPENDENCIES" | jq '.'
            fi
        fi
    fi
    
    exit 1
elif [ "$HTTP_CODE" = "000" ]; then
    print_error "No response from service"
    exit 2
else
    print_error "Unexpected HTTP status code: $HTTP_CODE"
    
    if [ "$VERBOSE" = "true" ] && [ -n "$RESPONSE" ]; then
        print_info "Response: $RESPONSE"
    fi
    
    exit 1
fi
