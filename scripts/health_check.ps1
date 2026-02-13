# Health check script for APGI Standalone API (PowerShell)
# This script checks the /health/ready endpoint and exits with appropriate codes for monitoring systems
# Exit codes: 0 = healthy, 1 = unhealthy, 2 = connection error

param(
    [string]$Url = $env:API_URL,
    [string]$Endpoint = $env:HEALTH_ENDPOINT,
    [int]$Timeout = 10,
    [switch]$Verbose,
    [switch]$Quiet,
    [switch]$Help
)

# Default configuration
if ([string]::IsNullOrEmpty($Url)) {
    $Url = "http://localhost:8000"
}
if ([string]::IsNullOrEmpty($Endpoint)) {
    $Endpoint = "/health/ready"
}
if ($env:TIMEOUT) {
    $Timeout = [int]$env:TIMEOUT
}
if ($env:VERBOSE -eq "true") {
    $Verbose = $true
}
if ($env:QUIET -eq "true") {
    $Quiet = $true
}

# Show help
if ($Help) {
    Write-Host "Usage: .\health_check.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "Health check script for APGI Standalone API"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Url URL               API base URL (default: http://localhost:8000)"
    Write-Host "  -Endpoint PATH         Health endpoint path (default: /health/ready)"
    Write-Host "  -Timeout SECONDS       Request timeout in seconds (default: 10)"
    Write-Host "  -Verbose               Enable verbose output"
    Write-Host "  -Quiet                 Suppress all output (only exit codes)"
    Write-Host "  -Help                  Show this help message"
    Write-Host ""
    Write-Host "Environment variables:"
    Write-Host "  API_URL                API base URL"
    Write-Host "  HEALTH_ENDPOINT        Health endpoint path"
    Write-Host "  TIMEOUT                Request timeout"
    Write-Host "  VERBOSE                Enable verbose output (true/false)"
    Write-Host "  QUIET                  Suppress output (true/false)"
    Write-Host ""
    Write-Host "Exit codes:"
    Write-Host "  0 - Service is healthy"
    Write-Host "  1 - Service is unhealthy"
    Write-Host "  2 - Connection error or timeout"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\health_check.ps1"
    Write-Host "  .\health_check.ps1 -Url http://api.example.com:8000"
    Write-Host "  .\health_check.ps1 -Endpoint /health/live -Timeout 5"
    Write-Host "  .\health_check.ps1 -Quiet  # For use in monitoring scripts"
    exit 0
}

# Function to print messages (respects quiet mode)
function Write-Status {
    param($Message)
    if (-not $Quiet) {
        Write-Host "✓ $Message" -ForegroundColor Green
    }
}

function Write-ErrorMsg {
    param($Message)
    if (-not $Quiet) {
        Write-Host "✗ $Message" -ForegroundColor Red
    }
}

function Write-Warning {
    param($Message)
    if (-not $Quiet) {
        Write-Host "⚠ $Message" -ForegroundColor Yellow
    }
}

function Write-Info {
    param($Message)
    if (-not $Quiet -and $Verbose) {
        Write-Host "ℹ $Message" -ForegroundColor Blue
    }
}

# Construct full URL
$FullUrl = "$Url$Endpoint"

Write-Info "Checking health endpoint: $FullUrl"
Write-Info "Timeout: ${Timeout}s"

# Perform health check
try {
    $Response = Invoke-WebRequest -Uri $FullUrl -TimeoutSec $Timeout -UseBasicParsing -ErrorAction Stop
    $StatusCode = $Response.StatusCode
    $Content = $Response.Content
    
    Write-Info "HTTP Status Code: $StatusCode"
    
    if ($StatusCode -eq 200) {
        Write-Status "Service is healthy"
        
        # Parse and display additional information if verbose
        if ($Verbose -and $Content) {
            Write-Info "Response details:"
            try {
                $JsonResponse = $Content | ConvertFrom-Json
                $JsonResponse | ConvertTo-Json -Depth 10
            } catch {
                Write-Info "Response: $Content"
            }
        }
        
        exit 0
    } else {
        Write-ErrorMsg "Unexpected HTTP status code: $StatusCode"
        
        if ($Verbose -and $Content) {
            Write-Info "Response: $Content"
        }
        
        exit 1
    }
} catch {
    $StatusCode = $_.Exception.Response.StatusCode.value__
    
    if ($StatusCode -eq 503) {
        Write-ErrorMsg "Service is unhealthy (503 Service Unavailable)"
        
        # Try to show dependency status if available
        if ($Verbose) {
            try {
                $ErrorContent = $_.ErrorDetails.Message
                if ($ErrorContent) {
                    $JsonError = $ErrorContent | ConvertFrom-Json
                    if ($JsonError.dependencies) {
                        Write-Info "Dependency status:"
                        $JsonError.dependencies | ConvertTo-Json -Depth 10
                    }
                }
            } catch {
                # Ignore JSON parsing errors
            }
        }
        
        exit 1
    } elseif ($_.Exception.Message -match "timeout" -or $_.Exception.Message -match "timed out") {
        Write-ErrorMsg "Connection timeout after ${Timeout}s"
        exit 2
    } elseif ($_.Exception.Message -match "Unable to connect" -or $_.Exception.Message -match "No connection could be made") {
        Write-ErrorMsg "Failed to connect to $Url"
        exit 2
    } elseif ($_.Exception.Message -match "Could not resolve") {
        Write-ErrorMsg "Could not resolve host: $Url"
        exit 2
    } else {
        Write-ErrorMsg "Connection error: $($_.Exception.Message)"
        exit 2
    }
}
