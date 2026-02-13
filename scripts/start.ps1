# Start script for APGI Standalone API development environment (PowerShell)
# This script checks dependencies, starts docker-compose, runs migrations, and displays URLs

$ErrorActionPreference = "Stop"

# Script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "========================================" -ForegroundColor Blue
Write-Host "APGI Standalone API - Development Setup" -ForegroundColor Blue
Write-Host "========================================" -ForegroundColor Blue
Write-Host ""

# Function to check if a command exists
function Test-CommandExists {
    param($Command)
    $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

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

# Check dependencies
Write-Host "Checking dependencies..." -ForegroundColor Blue
Write-Host ""

$MissingDeps = 0

if (Test-CommandExists docker) {
    Write-Status "Docker is installed"
} else {
    Write-ErrorMsg "Docker is not installed"
    $MissingDeps = 1
}

# Check for docker compose (both old and new syntax)
$DockerComposeCmd = $null
if (docker compose version 2>$null) {
    Write-Status "Docker Compose is installed"
    $DockerComposeCmd = "docker compose"
} elseif (Test-CommandExists docker-compose) {
    Write-Status "Docker Compose is installed"
    $DockerComposeCmd = "docker-compose"
} else {
    Write-ErrorMsg "Docker Compose is not installed"
    $MissingDeps = 1
}

if ($MissingDeps -eq 1) {
    Write-Host ""
    Write-ErrorMsg "Missing required dependencies. Please install them and try again."
    exit 1
}

Write-Host ""

# Check if Docker daemon is running
try {
    docker info 2>&1 | Out-Null
    Write-Status "Docker daemon is running"
} catch {
    Write-ErrorMsg "Docker daemon is not running. Please start Docker and try again."
    exit 1
}

Write-Host ""

# Navigate to deployment directory
$DeploymentDir = Join-Path $ProjectRoot "deployment"
Set-Location $DeploymentDir

# Check if .env.development exists
$EnvDevPath = Join-Path $ProjectRoot ".env.development"
$EnvExamplePath = Join-Path $ProjectRoot ".env.example"

if (-not (Test-Path $EnvDevPath)) {
    Write-Warning ".env.development not found. Creating from .env.example..."
    if (Test-Path $EnvExamplePath) {
        Copy-Item $EnvExamplePath $EnvDevPath
        Write-Status "Created .env.development"
    } else {
        Write-ErrorMsg ".env.example not found. Cannot create .env.development"
        exit 1
    }
}

Write-Host ""

# Start docker-compose services
Write-Host "Starting Docker services..." -ForegroundColor Blue
Write-Host ""

if ($DockerComposeCmd -eq "docker compose") {
    docker compose up -d
} else {
    docker-compose up -d
}

Write-Host ""
Write-Status "Docker services started"
Write-Host ""

# Wait for services to be healthy
Write-Host "Waiting for services to be ready..." -ForegroundColor Blue
Write-Host ""

$MaxWait = 60
$WaitCount = 0

while ($WaitCount -lt $MaxWait) {
    if ($DockerComposeCmd -eq "docker compose") {
        $PostgresStatus = docker compose ps postgres 2>$null
        $RedisStatus = docker compose ps redis 2>$null
    } else {
        $PostgresStatus = docker-compose ps postgres 2>$null
        $RedisStatus = docker-compose ps redis 2>$null
    }
    
    $PostgresHealthy = ($PostgresStatus -match "healthy").Count -gt 0
    $RedisHealthy = ($RedisStatus -match "healthy").Count -gt 0
    
    if ($PostgresHealthy -and $RedisHealthy) {
        break
    }
    
    Write-Host "." -NoNewline
    Start-Sleep -Seconds 2
    $WaitCount += 2
}

Write-Host ""

if ($WaitCount -ge $MaxWait) {
    Write-Warning "Services did not become healthy within ${MaxWait}s. Continuing anyway..."
} else {
    Write-Status "PostgreSQL is healthy"
    Write-Status "Redis is healthy"
}

Write-Host ""

# Run database migrations
Write-Host "Running database migrations..." -ForegroundColor Blue
Write-Host ""

try {
    if ($DockerComposeCmd -eq "docker compose") {
        docker compose exec -T api alembic upgrade head 2>$null
    } else {
        docker-compose exec -T api alembic upgrade head 2>$null
    }
    Write-Status "Database migrations completed successfully"
} catch {
    Write-Warning "Failed to run migrations (container may still be starting). You can run them manually with:"
    Write-Info "  cd $DeploymentDir; $DockerComposeCmd exec api alembic upgrade head"
}

Write-Host ""

# Display service URLs
Write-Host "========================================" -ForegroundColor Green
Write-Host "Services are ready!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "API URL:          " -NoNewline -ForegroundColor Blue
Write-Host "http://localhost:8000"
Write-Host "API Docs:         " -NoNewline -ForegroundColor Blue
Write-Host "http://localhost:8000/docs"
Write-Host "API ReDoc:        " -NoNewline -ForegroundColor Blue
Write-Host "http://localhost:8000/redoc"
Write-Host "Health Check:     " -NoNewline -ForegroundColor Blue
Write-Host "http://localhost:8000/health"
Write-Host "Metrics:          " -NoNewline -ForegroundColor Blue
Write-Host "http://localhost:8000/metrics"
Write-Host ""
Write-Host "PostgreSQL:       " -NoNewline -ForegroundColor Blue
Write-Host "localhost:5432"
Write-Host "  Database:       " -NoNewline -ForegroundColor Blue
Write-Host "apgi_api_dev"
Write-Host "  User:           " -NoNewline -ForegroundColor Blue
Write-Host "apgi_dev"
Write-Host "  Password:       " -NoNewline -ForegroundColor Blue
Write-Host "dev_password"
Write-Host ""
Write-Host "Redis:            " -NoNewline -ForegroundColor Blue
Write-Host "localhost:6379"
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Yellow
Write-Host "  View logs:        cd $DeploymentDir; $DockerComposeCmd logs -f"
Write-Host "  View API logs:    cd $DeploymentDir; $DockerComposeCmd logs -f api"
Write-Host "  Stop services:    cd $DeploymentDir; $DockerComposeCmd down"
Write-Host "  Restart API:      cd $DeploymentDir; $DockerComposeCmd restart api"
Write-Host "  Run migrations:   cd $DeploymentDir; $DockerComposeCmd exec api alembic upgrade head"
Write-Host ""
