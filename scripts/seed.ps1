# APGI API Database Seeding Script (PowerShell)
# Seeds the database with test data for development and testing

param(
    [Parameter(Position = 0)]
    [ValidateSet("users", "sessions", "tasks", "all")]
    [string]$Command = "all",

    [Parameter(Mandatory = $false)]
    [ValidateSet("development", "staging", "test")]
    [string]$Environment = "development",

    [Parameter(Mandatory = $false)]
    [ValidateSet("auto", "docker", "local")]
    [string]$Mode = "auto",

    [switch]$Force
)

# Script configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$DockerComposeFile = Join-Path $ProjectRoot "deployment\docker-compose.yml"

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
APGI API Database Seeding Script (PowerShell)

Usage: .\seed.ps1 [COMMAND] [OPTIONS]

Commands:
    users          Seed user accounts
    sessions       Seed session data
    tasks          Seed task data
    all            Seed all data types (default)

Options:
    -Environment   Environment (development, staging, test) [default: development]
    -Mode          Execution mode (docker, local) [default: auto]
    -Force         Force reseeding (drop existing data)

Examples:
    .\seed.ps1 users                           # Seed users in development
    .\seed.ps1 all -Environment test           # Seed all data for test environment
    .\seed.ps1 sessions -Mode docker           # Seed sessions using Docker
    .\seed.ps1 all -Force                      # Force reseed all data

Environment Variables:
    SEED_USERS_COUNT    Number of users to create [default: 10]
    SEED_SESSIONS_COUNT Number of sessions per user [default: 5]
    SEED_TASKS_COUNT    Number of tasks per session [default: 3]

"@
    Write-Host $helpText
}

# Check if Docker is running and should be used
function Test-DockerMode {
    if ($Mode -eq "docker") {
        return $true
    }
    elseif ($Mode -eq "local") {
        return $false
    }
    else {
        # Auto mode - check if Docker is running and compose file exists
        try {
            $null = docker version 2>$null
            if ($LASTEXITCODE -eq 0 -and (Test-Path $DockerComposeFile)) {
                return $true
            }
        }
        catch {
            # Docker not available
        }
        return $false
    }
}

# Execute Python seeding script
function Invoke-Seeder {
    param(
        [string]$ScriptName,
        [bool]$DockerMode
    )

    Write-Info "Running seeder: $ScriptName"

    $arguments = @(
        "-m", "scripts.seeders.$ScriptName",
        "--env", $Environment
    )

    if ($Force) {
        $arguments += "--force"
    }

    if ($DockerMode) {
        # Run in Docker container
        Push-Location $ProjectRoot
        try {
            $dockerArgs = @(
                "compose",
                "-f", $DockerComposeFile,
                "exec",
                "-T",
                "api",
                "python"
            ) + $arguments

            & docker $dockerArgs
            if ($LASTEXITCODE -ne 0) {
                throw "Docker command failed with exit code $LASTEXITCODE"
            }
        }
        finally {
            Pop-Location
        }
    }
    else {
        # Run locally
        Push-Location $ProjectRoot
        try {
            & python $arguments
            if ($LASTEXITCODE -ne 0) {
                throw "Python command failed with exit code $LASTEXITCODE"
            }
        }
        finally {
            Pop-Location
        }
    }
}

# Main execution
function Invoke-Main {
    Write-Info "Starting database seeding for environment: $Environment"

    # Check Docker mode
    $dockerMode = Test-DockerMode
    if ($dockerMode) {
        Write-Info "Using Docker execution mode"
    }
    else {
        Write-Info "Using local execution mode"
    }

    # Execute seeding based on command
    switch ($Command) {
        "users" {
            Invoke-Seeder "seed_users" $dockerMode
        }
        "sessions" {
            Invoke-Seeder "seed_sessions" $dockerMode
        }
        "tasks" {
            Invoke-Seeder "seed_tasks" $dockerMode
        }
        "all" {
            Write-Info "Seeding all data types..."
            Invoke-Seeder "seed_users" $dockerMode
            Invoke-Seeder "seed_sessions" $dockerMode
            Invoke-Seeder "seed_tasks" $dockerMode
        }
    }

    Write-Success "Database seeding completed successfully!"
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
    Write-Error "Database seeding failed: $($_.Exception.Message)"
    exit 1
}
