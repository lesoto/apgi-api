# Database migration script for APGI Standalone API (PowerShell)
# This script runs Alembic migrations with error handling

$ErrorActionPreference = "Stop"

# Script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Function to print status messages
function Write-Status {
    param($Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-ErrorMsg {
    param($Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Write-Warning {
    param($Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-Info {
    param($Message)
    Write-Host "ℹ $Message" -ForegroundColor Blue
}

# Parse command line arguments
$MigrationTarget = if ($args.Count -gt 0) { $args[0] } else { "head" }
$UseDocker = if ($args.Count -gt 1) { $args[1] } else { "auto" }

Write-Host "========================================" -ForegroundColor Blue
Write-Host "APGI Standalone API - Database Migration" -ForegroundColor Blue
Write-Host "========================================" -ForegroundColor Blue
Write-Host ""

# Function to run migrations locally
function Invoke-LocalMigration {
    Write-Info "Running migrations locally..."
    
    # Check if alembic is available
    try {
        $null = Get-Command alembic -ErrorAction Stop
    } catch {
        Write-ErrorMsg "Alembic is not installed or not in PATH"
        Write-Info "Install with: pip install alembic"
        return $false
    }
    
    # Navigate to project root
    Set-Location $ProjectRoot
    
    # Check if alembic.ini exists
    if (-not (Test-Path "alembic.ini")) {
        Write-ErrorMsg "alembic.ini not found in $ProjectRoot"
        return $false
    }
    
    # Run migration
    Write-Info "Executing: alembic upgrade $MigrationTarget"
    try {
        alembic upgrade $MigrationTarget
        Write-Status "Migration completed successfully"
        return $true
    } catch {
        Write-ErrorMsg "Migration failed"
        Write-Host $_.Exception.Message -ForegroundColor Red
        return $false
    }
}

# Function to run migrations in Docker
function Invoke-DockerMigration {
    Write-Info "Running migrations in Docker container..."
    
    # Check if docker-compose is available
    $DockerComposeCmd = $null
    if (docker compose version 2>$null) {
        $DockerComposeCmd = "docker compose"
    } elseif (Get-Command docker-compose -ErrorAction SilentlyContinue) {
        $DockerComposeCmd = "docker-compose"
    } else {
        Write-ErrorMsg "Docker Compose is not installed"
        return $false
    }
    
    # Navigate to deployment directory
    $DeploymentDir = Join-Path $ProjectRoot "deployment"
    Set-Location $DeploymentDir
    
    # Check if docker-compose.yml exists
    if (-not (Test-Path "docker-compose.yml")) {
        Write-ErrorMsg "docker-compose.yml not found in $DeploymentDir"
        return $false
    }
    
    # Check if API container is running
    $ApiStatus = if ($DockerComposeCmd -eq "docker compose") {
        docker compose ps api 2>$null
    } else {
        docker-compose ps api 2>$null
    }
    
    if (-not ($ApiStatus -match "Up")) {
        Write-Warning "API container is not running"
        Write-Info "Starting services..."
        if ($DockerComposeCmd -eq "docker compose") {
            docker compose up -d
        } else {
            docker-compose up -d
        }
        
        # Wait for services to be ready
        Write-Info "Waiting for services to be ready..."
        Start-Sleep -Seconds 10
    }
    
    # Run migration in container
    Write-Info "Executing: $DockerComposeCmd exec api alembic upgrade $MigrationTarget"
    try {
        if ($DockerComposeCmd -eq "docker compose") {
            docker compose exec -T api alembic upgrade $MigrationTarget
        } else {
            docker-compose exec -T api alembic upgrade $MigrationTarget
        }
        Write-Status "Migration completed successfully"
        return $true
    } catch {
        Write-ErrorMsg "Migration failed"
        Write-Info "Check logs with: cd $DeploymentDir; $DockerComposeCmd logs api"
        return $false
    }
}

# Determine whether to use Docker or local execution
if ($UseDocker -eq "auto") {
    # Auto-detect: prefer Docker if available and running
    try {
        docker info 2>&1 | Out-Null
        $DeploymentDir = Join-Path $ProjectRoot "deployment"
        
        if (Test-Path (Join-Path $DeploymentDir "docker-compose.yml")) {
            Set-Location $DeploymentDir
            
            $DockerComposeCmd = $null
            if (docker compose version 2>$null) {
                $DockerComposeCmd = "docker compose"
            } elseif (Get-Command docker-compose -ErrorAction SilentlyContinue) {
                $DockerComposeCmd = "docker-compose"
            }
            
            if ($DockerComposeCmd) {
                $ApiStatus = if ($DockerComposeCmd -eq "docker compose") {
                    docker compose ps api 2>$null
                } else {
                    docker-compose ps api 2>$null
                }
                
                if ($ApiStatus -match "Up") {
                    Write-Info "Detected running Docker environment"
                    $UseDocker = "yes"
                } else {
                    Write-Info "Docker available but API container not running"
                    $UseDocker = "local"
                }
            } else {
                $UseDocker = "local"
            }
        } else {
            $UseDocker = "local"
        }
    } catch {
        $UseDocker = "local"
    }
}

# Execute migration
if ($UseDocker -eq "yes" -or $UseDocker -eq "docker") {
    if (Invoke-DockerMigration) {
        exit 0
    } else {
        exit 1
    }
} else {
    if (Invoke-LocalMigration) {
        exit 0
    } else {
        # If local migration fails, suggest Docker alternative
        Write-Host ""
        Write-Info "Tip: You can also run migrations in Docker with:"
        Write-Info "  .\migrate.ps1 $MigrationTarget docker"
        exit 1
    }
}
