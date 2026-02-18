# APGI API Performance Testing Script (PowerShell)
# Runs performance tests against the API to measure response times and throughput

param(
    [Parameter(Position = 0)]
    [ValidateSet("load", "stress", "spike", "soak", "all")]
    [string]$TestType = "all",

    [Parameter(Mandatory = $false)]
    [string]$Url = $env:API_URL,

    [Parameter(Mandatory = $false)]
    [int]$Duration = [int]$env:TEST_DURATION,

    [Parameter(Mandatory = $false)]
    [int]$Concurrency = [int]$env:CONCURRENCY,

    [Parameter(Mandatory = $false)]
    [int]$Rate = [int]$env:REQUEST_RATE,

    [Parameter(Mandatory = $false)]
    [int]$Timeout = [int]$env:REQUEST_TIMEOUT,

    [Parameter(Mandatory = $false)]
    [string]$OutputFile = $env:OUTPUT_FILE,

    [switch]$Verbose
)

# Set default values
if (-not $Url) { $Url = "http://localhost:8000" }
if (-not $Duration) { $Duration = 60 }
if (-not $Concurrency) { $Concurrency = 10 }
if (-not $Rate) { $Rate = 20 }
if (-not $Timeout) { $Timeout = 10 }
if (-not $OutputFile) { $OutputFile = "perf_results.json" }

# Logging functions
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

# Help function
function Show-Help {
    $helpText = @"
APGI API Performance Testing Script (PowerShell)

Usage: .\perf_test.ps1 [TEST_TYPE] [OPTIONS]

Test Types:
    load         Run load testing with concurrent requests
    stress       Run stress testing to find breaking points
    spike        Run spike testing with sudden traffic bursts
    soak         Run soak testing for extended periods
    all          Run all test types (default)

Options:
    -Url          API base URL [default: http://localhost:8000]
    -Duration     Test duration in seconds [default: 60]
    -Concurrency  Number of concurrent users [default: 10]
    -Rate         Request rate per second [default: 20]
    -Timeout      Request timeout [default: 10]
    -OutputFile   Output file for results [default: perf_results.json]
    -Verbose      Enable verbose output

Examples:
    .\perf_test.ps1 load                            # Run load test for 60 seconds
    .\perf_test.ps1 stress -Concurrency 50          # Run stress test with 50 concurrent users
    .\perf_test.ps1 spike -Duration 30              # Run spike test for 30 seconds
    .\perf_test.ps1 all -Url http://api.example.com -OutputFile results.json

Requirements:
    - PowerShell 5.1 or later

Environment Variables:
    API_URL          API base URL
    TEST_DURATION    Test duration in seconds
    CONCURRENCY      Number of concurrent users
    REQUEST_RATE     Request rate per second
    REQUEST_TIMEOUT  Request timeout in seconds
    OUTPUT_FILE      Output file for results

"@
    Write-Host $helpText
}

# Check API availability
function Test-ApiAvailability {
    param([string]$ApiUrl)

    Write-Info "Checking API availability at $ApiUrl"

    try {
        $response = Invoke-WebRequest -Uri "$ApiUrl/health" -TimeoutSec 5 -ErrorAction Stop
        Write-Success "API is available"
        return $true
    }
    catch {
        Write-Error "API is not available at $ApiUrl"
        return $false
    }
}

# Make HTTP request and measure response time
function Invoke-Request {
    param(
        [string]$Endpoint,
        [string]$Method = "GET",
        [string]$Body = ""
    )

    $startTime = Get-Date

    try {
        $params = @{
            Uri = "$Url$Endpoint"
            Method = $Method
            TimeoutSec = $Timeout
            ErrorAction = "Stop"
        }

        if ($Body) {
            $params.Body = $Body
            $params.ContentType = "application/json"
        }

        $response = Invoke-WebRequest @params
        $httpCode = $response.StatusCode
    }
    catch {
        if ($_.Exception.Response) {
            $httpCode = $_.Exception.Response.StatusCode.value__
        }
        else {
            $httpCode = 0
        }
    }

    $endTime = Get-Date
    $totalTime = ($endTime - $startTime).TotalSeconds

    return @{
        http_code = $httpCode.ToString()
        response_time = $totalTime
        total_time = $totalTime
    }
}

# Run load test
function Invoke-LoadTest {
    Write-Info "Running load test (duration: ${Duration}s, concurrency: $Concurrency)"

    $results = [System.Collections.Concurrent.ConcurrentBag[object]]::new()
    $startTime = Get-Date

    $jobs = @()

    # Start concurrent jobs
    for ($i = 0; $i -lt $Concurrency; $i++) {
        $job = Start-Job -ScriptBlock {
            param($Url, $Duration, $Timeout, $StartTime)

            $localResults = @()

            while (((Get-Date) - $StartTime).TotalSeconds -lt $Duration) {
                $result = Invoke-Request -Endpoint "/health" -Timeout $Timeout
                $localResults += $result

                # Small delay to avoid overwhelming the API
                Start-Sleep -Milliseconds 100
            }

            return $localResults
        } -ArgumentList $Url, $Duration, $Timeout, $startTime

        $jobs += $job
    }

    # Wait for all jobs to complete and collect results
    $jobs | Wait-Job | Receive-Job | ForEach-Object {
        $results.Add($_)
    }

    # Clean up jobs
    $jobs | Remove-Job

    # Convert ConcurrentBag to regular array
    $allResults = @()
    $results | ForEach-Object { $allResults += $_ }

    Analyze-Results -Results $allResults -TestName "load_test"
}

# Run stress test
function Invoke-StressTest {
    Write-Info "Running stress test (duration: ${Duration}s, max concurrency: $Concurrency)"

    $results = [System.Collections.Concurrent.ConcurrentBag[object]]::new()
    $maxConcurrency = $Concurrency
    $stepDuration = $Duration / 5

    for ($concurrency = 1; $concurrency -le $maxConcurrency; $concurrency++) {
        Write-Info "Testing with concurrency: $concurrency"

        $stepStartTime = Get-Date
        $jobs = @()

        # Start workers for this concurrency level
        for ($i = 0; $i -lt $concurrency; $i++) {
            $job = Start-Job -ScriptBlock {
                param($Url, $StepDuration, $Timeout, $StepStartTime)

                $localResults = @()

                while (((Get-Date) - $StepStartTime).TotalSeconds -lt $StepDuration) {
                    $result = Invoke-Request -Endpoint "/health" -Timeout $Timeout
                    $localResults += $result
                    Start-Sleep -Milliseconds 50
                }

                return $localResults
            } -ArgumentList $Url, $stepDuration, $Timeout, $stepStartTime

            $jobs += $job
        }

        # Wait for this concurrency level to complete
        $jobs | Wait-Job | Receive-Job | ForEach-Object {
            $results.Add($_)
        }

        # Clean up jobs
        $jobs | Remove-Job
    }

    # Convert ConcurrentBag to regular array
    $allResults = @()
    $results | ForEach-Object { $allResults += $_ }

    Analyze-Results -Results $allResults -TestName "stress_test"
}

# Run spike test
function Invoke-SpikeTest {
    Write-Info "Running spike test (duration: ${Duration}s, spike concurrency: $Concurrency)"

    $results = [System.Collections.Concurrent.ConcurrentBag[object]]::new()

    $jobs = @()

    # Sudden spike of requests
    for ($i = 0; $i -lt $Concurrency; $i++) {
        $job = Start-Job -ScriptBlock {
            param($Url, $Timeout)

            $localResults = @()

            for ($j = 0; $j -lt 10; $j++) {
                $result = Invoke-Request -Endpoint "/health" -Timeout $Timeout
                $localResults += $result
            }

            return $localResults
        } -ArgumentList $Url, $Timeout

        $jobs += $job
    }

    # Wait for all spike requests to complete
    $jobs | Wait-Job | Receive-Job | ForEach-Object {
        $results.Add($_)
    }

    # Clean up jobs
    $jobs | Remove-Job

    # Convert ConcurrentBag to regular array
    $allResults = @()
    $results | ForEach-Object { $allResults += $_ }

    Analyze-Results -Results $allResults -TestName "spike_test"
}

# Run soak test
function Invoke-SoakTest {
    Write-Info "Running soak test (duration: ${Duration}s, concurrency: $Concurrency)"

    $results = [System.Collections.Concurrent.ConcurrentBag[object]]::new()
    $startTime = Get-Date

    $jobs = @()

    # Long-running test with moderate load
    for ($i = 0; $i -lt $Concurrency; $i++) {
        $job = Start-Job -ScriptBlock {
            param($Url, $Duration, $Timeout, $StartTime)

            $localResults = @()

            while (((Get-Date) - $StartTime).TotalSeconds -lt $Duration) {
                $result = Invoke-Request -Endpoint "/health" -Timeout $Timeout
                $localResults += $result

                # Random delay between requests
                $delay = Get-Random -Minimum 0.1 -Maximum 0.6
                Start-Sleep -Seconds $delay
            }

            return $localResults
        } -ArgumentList $Url, $Duration, $Timeout, $startTime

        $jobs += $job
    }

    # Wait for all workers to complete
    $jobs | Wait-Job | Receive-Job | ForEach-Object {
        $results.Add($_)
    }

    # Clean up jobs
    $jobs | Remove-Job

    # Convert ConcurrentBag to regular array
    $allResults = @()
    $results | ForEach-Object { $allResults += $_ }

    Analyze-Results -Results $allResults -TestName "soak_test"
}

# Analyze test results
function Analyze-Results {
    param(
        [array]$Results,
        [string]$TestName
    )

    if (-not $Results -or $Results.Count -eq 0) {
        Write-Error "No results to analyze for $TestName"
        return
    }

    Write-Info "Analyzing results for $TestName"

    # Calculate statistics
    $totalRequests = $Results.Count
    $successCount = ($Results | Where-Object { $_.http_code -eq "200" }).Count
    $errorCount = $totalRequests - $successCount

    # Extract response times
    $responseTimes = $Results | ForEach-Object { $_.response_time } | Sort-Object

    if ($responseTimes.Count -gt 0) {
        $avgResponseTime = ($responseTimes | Measure-Object -Average).Average
        $minResponseTime = $responseTimes[0]
        $maxResponseTime = $responseTimes[-1]

        # Calculate percentiles
        $p50Index = [math]::Floor($responseTimes.Count * 0.5)
        $p95Index = [math]::Floor($responseTimes.Count * 0.95)
        $p99Index = [math]::Floor($responseTimes.Count * 0.99)

        $p50 = $responseTimes[$p50Index]
        $p95 = $responseTimes[$p95Index]
        $p99 = $responseTimes[$p99Index]
    }
    else {
        $avgResponseTime = 0
        $minResponseTime = 0
        $maxResponseTime = 0
        $p50 = 0
        $p95 = 0
        $p99 = 0
    }

    # Create results object
    $results = @{
        test_name = $TestName
        timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        config = @{
            api_url = $Url
            duration = $Duration
            concurrency = $Concurrency
            request_rate = $Rate
        }
        results = @{
            total_requests = $totalRequests
            successful_requests = $successCount
            error_requests = $errorCount
            success_rate = if ($totalRequests -gt 0) { ($successCount / $totalRequests) * 100 } else { 0 }
            response_times = @{
                avg = $avgResponseTime
                min = $minResponseTime
                max = $maxResponseTime
                p50 = $p50
                p95 = $p95
                p99 = $p99
            }
        }
    }

    # Save results to file
    $results | ConvertTo-Json -Depth 10 | Out-File -FilePath $OutputFile -Encoding UTF8

    # Display results
    Write-Success "Test completed: $TestName"
    Write-Host "Results saved to: $OutputFile"
    Write-Host "Total requests: $totalRequests"
    Write-Host ("Success rate: {0:N2}%" -f $results.results.success_rate)
    Write-Host ("Avg response time: {0:N3}s" -f $avgResponseTime)
    Write-Host ("95th percentile: {0:N3}s" -f $p95)
}

# Main execution
function Invoke-Main {
    Write-Info "Starting APGI API performance testing"

    # Check API availability
    if (-not (Test-ApiAvailability -ApiUrl $Url)) {
        exit 1
    }

    # Run tests based on type
    switch ($TestType) {
        "load" {
            Invoke-LoadTest
        }
        "stress" {
            Invoke-StressTest
        }
        "spike" {
            Invoke-SpikeTest
        }
        "soak" {
            Invoke-SoakTest
        }
        "all" {
            Write-Info "Running all performance tests..."
            Invoke-LoadTest
            Invoke-StressTest
            Invoke-SpikeTest
            Invoke-SoakTest
        }
    }

    Write-Success "Performance testing completed!"
    Write-Info "Results saved to: $OutputFile"
}

# Show help if requested
if ($args -contains "-h" -or $args -contains "--help" -or $args -contains "-Help") {
    Show-Help
    exit 0
}

# Run main function
try {
    Invoke-Main
}
catch {
    Write-Error "Performance testing failed: $($_.Exception.Message)"
    exit 1
}
