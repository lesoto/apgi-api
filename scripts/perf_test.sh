#!/bin/bash

# APGI API Performance Testing Script
# Runs performance tests against the API to measure response times and throughput

set -e  # Exit on any error

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

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
APGI API Performance Testing Script

Usage: $0 [OPTIONS] [TEST_TYPE]

Test Types:
    load         Run load testing with concurrent requests
    stress       Run stress testing to find breaking points
    spike        Run spike testing with sudden traffic bursts
    soak         Run soak testing for extended periods
    all          Run all test types (default)

Options:
    -u, --url URL         API base URL [default: http://localhost:8000]
    -d, --duration SEC    Test duration in seconds [default: 60]
    -c, --concurrency N   Number of concurrent users [default: 10]
    -r, --rate N          Request rate per second [default: 20]
    -t, --timeout SEC     Request timeout [default: 10]
    -o, --output FILE     Output file for results [default: perf_results.json]
    -v, --verbose         Enable verbose output
    -h, --help           Show this help message

Examples:
    $0 load                           # Run load test for 60 seconds
    $0 stress --concurrency 50        # Run stress test with 50 concurrent users
    $0 spike --duration 30            # Run spike test for 30 seconds
    $0 all --url http://api.example.com --output results.json

Requirements:
    - curl or wget
    - jq (for JSON processing)
    - bc (for calculations)

Environment Variables:
    API_URL          API base URL
    TEST_DURATION    Test duration in seconds
    CONCURRENCY      Number of concurrent users
    REQUEST_RATE     Request rate per second
    REQUEST_TIMEOUT  Request timeout in seconds
    OUTPUT_FILE      Output file for results

EOF
}

# Default values
API_URL="${API_URL:-http://localhost:8000}"
TEST_DURATION="${TEST_DURATION:-60}"
CONCURRENCY="${CONCURRENCY:-10}"
REQUEST_RATE="${REQUEST_RATE:-20}"
REQUEST_TIMEOUT="${REQUEST_TIMEOUT:-10}"
OUTPUT_FILE="${OUTPUT_FILE:-perf_results.json}"
VERBOSE=false
TEST_TYPE="all"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--url)
            API_URL="$2"
            shift 2
            ;;
        -d|--duration)
            TEST_DURATION="$2"
            shift 2
            ;;
        -c|--concurrency)
            CONCURRENCY="$2"
            shift 2
            ;;
        -r|--rate)
            REQUEST_RATE="$2"
            shift 2
            ;;
        -t|--timeout)
            REQUEST_TIMEOUT="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        load|stress|spike|soak|all)
            TEST_TYPE="$1"
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Check dependencies
check_dependencies() {
    local missing_deps=()

    if ! command -v curl &> /dev/null && ! command -v wget &> /dev/null; then
        missing_deps+=("curl or wget")
    fi

    if ! command -v jq &> /dev/null; then
        missing_deps+=("jq")
    fi

    if ! command -v bc &> /dev/null; then
        missing_deps+=("bc")
    fi

    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "Missing required dependencies: ${missing_deps[*]}"
        log_info "Please install missing dependencies and try again."
        exit 1
    fi
}

# Check API availability
check_api_availability() {
    log_info "Checking API availability at $API_URL"

    if command -v curl &> /dev/null; then
        if ! curl -s --max-time 5 "$API_URL/health" > /dev/null; then
            log_error "API is not available at $API_URL"
            exit 1
        fi
    elif command -v wget &> /dev/null; then
        if ! wget -q --timeout=5 -O /dev/null "$API_URL/health" 2>/dev/null; then
            log_error "API is not available at $API_URL"
            exit 1
        fi
    fi

    log_success "API is available"
}

# Make HTTP request and measure response time
make_request() {
    local endpoint="$1"
    local method="${2:-GET}"
    local data="$3"

    local start_time=$(date +%s.%N)

    if command -v curl &> /dev/null; then
        if [[ "$method" == "POST" ]] && [[ -n "$data" ]]; then
            response=$(curl -s -w "@$SCRIPT_DIR/curl-format.txt" -X "$method" \
                -H "Content-Type: application/json" \
                -d "$data" \
                --max-time "$REQUEST_TIMEOUT" \
                "$API_URL$endpoint" 2>/dev/null)
        else
            response=$(curl -s -w "@$SCRIPT_DIR/curl-format.txt" -X "$method" \
                --max-time "$REQUEST_TIMEOUT" \
                "$API_URL$endpoint" 2>/dev/null)
        fi
    else
        # Fallback to wget (limited functionality)
        local wget_start=$(date +%s.%N)
        if wget -q --timeout="$REQUEST_TIMEOUT" -O /dev/null "$API_URL$endpoint" 2>/dev/null; then
            local wget_end=$(date +%s.%N)
            response="http_code: 200
total_time: $(echo "$wget_end - $wget_start" | bc)"
        else
            response="http_code: 000
total_time: 0.000000"
        fi
    fi

    local end_time=$(date +%s.%N)
    local total_time=$(echo "$end_time - $start_time" | bc)

    # Extract HTTP code and response time from curl format
    local http_code=$(echo "$response" | grep "http_code:" | cut -d' ' -f2)
    local response_time=$(echo "$response" | grep "total_time:" | cut -d' ' -f2)

    if [[ -z "$response_time" ]]; then
        response_time="$total_time"
    fi

    echo "{\"http_code\": \"$http_code\", \"response_time\": $response_time, \"total_time\": $total_time}"
}

# Run load test
run_load_test() {
    log_info "Running load test (duration: ${TEST_DURATION}s, concurrency: $CONCURRENCY)"

    local results_file=$(mktemp)
    local pids=()
    local start_time=$(date +%s)

    # Start concurrent workers
    for ((i = 0; i < CONCURRENCY; i++)); do
        (
            while true; do
                current_time=$(date +%s)
                if (( current_time - start_time >= TEST_DURATION )); then
                    break
                fi

                result=$(make_request "/health")
                echo "$result" >> "$results_file"

                # Small delay to avoid overwhelming the API
                sleep 0.1
            done
        ) &
        pids+=($!)
    done

    # Wait for all workers to complete
    for pid in "${pids[@]}"; do
        wait "$pid"
    done

    # Analyze results
    analyze_results "$results_file" "load_test"
    rm -f "$results_file"
}

# Run stress test
run_stress_test() {
    log_info "Running stress test (duration: ${TEST_DURATION}s, max concurrency: $CONCURRENCY)"

    local results_file=$(mktemp)
    local max_concurrency=$CONCURRENCY
    local step_duration=$((TEST_DURATION / 5))

    for ((concurrency = 1; concurrency <= max_concurrency; concurrency++)); do
        log_info "Testing with concurrency: $concurrency"

        local pids=()
        local step_start=$(date +%s)

        # Start workers for this concurrency level
        for ((i = 0; i < concurrency; i++)); do
            (
                while true; do
                    current_time=$(date +%s)
                    if (( current_time - step_start >= step_duration )); then
                        break
                    fi

                    result=$(make_request "/health")
                    echo "$result" >> "$results_file"
                    sleep 0.05
                done
            ) &
            pids+=($!)
        done

        # Wait for this concurrency level to complete
        for pid in "${pids[@]}"; do
            wait "$pid"
        done
    done

    analyze_results "$results_file" "stress_test"
    rm -f "$results_file"
}

# Run spike test
run_spike_test() {
    log_info "Running spike test (duration: ${TEST_DURATION}s, spike concurrency: $CONCURRENCY)"

    local results_file=$(mktemp)
    local pids=()
    local start_time=$(date +%s)

    # Sudden spike of requests
    for ((i = 0; i < CONCURRENCY; i++)); do
        (
            for ((j = 0; j < 10; j++)); do
                result=$(make_request "/health")
                echo "$result" >> "$results_file"
            done
        ) &
        pids+=($!)
    done

    # Wait for all spike requests to complete
    for pid in "${pids[@]}"; do
        wait "$pid"
    done

    analyze_results "$results_file" "spike_test"
    rm -f "$results_file"
}

# Run soak test
run_soak_test() {
    log_info "Running soak test (duration: ${TEST_DURATION}s, concurrency: $CONCURRENCY)"

    local results_file=$(mktemp)
    local pids=()
    local start_time=$(date +%s)

    # Long-running test with moderate load
    for ((i = 0; i < CONCURRENCY; i++)); do
        (
            while true; do
                current_time=$(date +%s)
                if (( current_time - start_time >= TEST_DURATION )); then
                    break
                fi

                result=$(make_request "/health")
                echo "$result" >> "$results_file"

                # Random delay between requests
                sleep "$(echo "scale=2; $RANDOM/32767*0.5" | bc)"
            done
        ) &
        pids+=($!)
    done

    # Wait for all workers to complete
    for pid in "${pids[@]}"; do
        wait "$pid"
    done

    analyze_results "$results_file" "soak_test"
    rm -f "$results_file"
}

# Analyze test results
analyze_results() {
    local results_file="$1"
    local test_name="$2"

    if [[ ! -s "$results_file" ]]; then
        log_error "No results to analyze for $test_name"
        return
    fi

    log_info "Analyzing results for $test_name"

    # Calculate statistics
    local total_requests=$(wc -l < "$results_file")
    local success_count=$(grep -c '"http_code": "200"' "$results_file" || echo "0")
    local error_count=$((total_requests - success_count))

    # Extract response times and calculate statistics
    local response_times=$(grep -o '"response_time": [0-9.]*' "$results_file" | cut -d' ' -f2)
    local avg_response_time=$(echo "$response_times" | awk '{sum+=$1} END {print sum/NR}')
    local min_response_time=$(echo "$response_times" | sort -n | head -1)
    local max_response_time=$(echo "$response_times" | sort -n | tail -1)

    # Calculate percentiles
    local sorted_times=$(echo "$response_times" | sort -n)
    local p50=$(echo "$sorted_times" | awk 'NR==int(0.5*NR) {print}')
    local p95=$(echo "$sorted_times" | awk 'NR==int(0.95*NR) {print}')
    local p99=$(echo "$sorted_times" | awk 'NR==int(0.99*NR) {print}')

    # Create results JSON
    local results=$(cat << EOF
{
    "test_name": "$test_name",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "config": {
        "api_url": "$API_URL",
        "duration": $TEST_DURATION,
        "concurrency": $CONCURRENCY,
        "request_rate": $REQUEST_RATE
    },
    "results": {
        "total_requests": $total_requests,
        "successful_requests": $success_count,
        "error_requests": $error_count,
        "success_rate": $(echo "scale=4; $success_count / $total_requests * 100" | bc 2>/dev/null || echo "0"),
        "response_times": {
            "avg": ${avg_response_time:-0},
            "min": ${min_response_time:-0},
            "max": ${max_response_time:-0},
            "p50": ${p50:-0},
            "p95": ${p95:-0},
            "p99": ${p99:-0}
        }
    }
}
EOF
)

    # Save results to file
    echo "$results" | jq . > "$OUTPUT_FILE" 2>/dev/null || echo "$results" > "$OUTPUT_FILE"

    # Display results
    log_success "Test completed: $test_name"
    echo "Results saved to: $OUTPUT_FILE"
    echo "Total requests: $total_requests"
    echo "Success rate: $(echo "scale=2; $success_count / $total_requests * 100" | bc 2>/dev/null || echo "0")%"
    echo "Avg response time: ${avg_response_time:-0}s"
    echo "95th percentile: ${p95:-0}s"
}

# Create curl format file if it doesn't exist
create_curl_format() {
    cat > "$SCRIPT_DIR/curl-format.txt" << 'EOF'
http_code: %{http_code}
total_time: %{time_total}
EOF
}

# Main execution
main() {
    log_info "Starting APGI API performance testing"

    # Check dependencies
    check_dependencies

    # Create curl format file
    create_curl_format

    # Check API availability
    check_api_availability

    # Run tests based on type
    case $TEST_TYPE in
        load)
            run_load_test
            ;;
        stress)
            run_stress_test
            ;;
        spike)
            run_spike_test
            ;;
        soak)
            run_soak_test
            ;;
        all)
            log_info "Running all performance tests..."
            run_load_test
            run_stress_test
            run_spike_test
            run_soak_test
            ;;
    esac

    log_success "Performance testing completed!"
    log_info "Results saved to: $OUTPUT_FILE"
}

# Run main function
main "$@"
