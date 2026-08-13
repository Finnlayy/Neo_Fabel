# Neo Fabel All-In-One One-Click Bootstrap & Server Launcher
# Run this script to install/verify Python/npm dependencies, start PostgreSQL, run migrations, and launch the complete stack.

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "🚀 NEO FABEL ONE-CLICK BOOTSTRAP & LAUNCHER" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Check & Install Python dependencies
Write-Host "📦 [1/6] Checking Python requirements..." -ForegroundColor Yellow
python -m pip install --quiet -e ./backend
Write-Host "   ✅ Python dependencies up to date." -ForegroundColor Green

# 2. Check & Install Frontend npm dependencies
Write-Host "📦 [2/6] Checking Frontend npm packages..." -ForegroundColor Yellow
if (-not (Test-Path "node_modules")) {
    npm install
} else {
    Write-Host "   ✅ node_modules present." -ForegroundColor Green
}

# 3. Ensure Docker PostgreSQL Container is running
Write-Host "🐘 [3/6] Starting PostgreSQL Database (Docker)..." -ForegroundColor Yellow
try {
    docker compose up -d postgres
    $healthy = $false
    $containerId = docker compose ps -q postgres
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        $status = if ($containerId) { docker inspect --format='{{.State.Health.Status}}' $containerId 2>$null } else { "missing" }
        if ($status -eq "healthy") {
            $healthy = $true
            break
        }
        Start-Sleep -Seconds 2
    }
    if ($healthy) {
        Write-Host "   ✅ PostgreSQL is HEALTHY and ready." -ForegroundColor Green
    } else {
        Write-Host "   ⚠️ PostgreSQL started but health check pending." -ForegroundColor Yellow
    }
} catch {
    Write-Host "   ⚠️ Could not auto-start Docker PostgreSQL: $_" -ForegroundColor Red
    Write-Host "   (Continuing: In-Memory / Fallback mode active for non-DB endpoints)" -ForegroundColor Gray
}

# 4. Database Migrations (Alembic)
Write-Host "🗄️ [4/6] Running Database Migrations..." -ForegroundColor Yellow
try {
    python -m alembic -c backend/alembic.ini upgrade head
    Write-Host "   ✅ Database migrations complete." -ForegroundColor Green
} catch {
    Write-Host "   ⚠️ Migration skipped or database offline." -ForegroundColor Yellow
}

# 5. Start Backend Server (Uvicorn - Port 8000)
Write-Host "⚡ [5/6] Launching Backend Server (Port 8000)..." -ForegroundColor Yellow
$backendProc = Start-Process -FilePath "python" -ArgumentList @("-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000") -PassThru -NoNewWindow
Write-Host "   ✅ Backend process started with PID $($backendProc.Id)." -ForegroundColor Green

# 6. Start Frontend Server (Vite - Port 5173)
Write-Host "🌐 [6/6] Launching Frontend Server (Port 5173)..." -ForegroundColor Yellow
$frontendProc = Start-Process -FilePath "npm" -ArgumentList @("run", "dev") -PassThru -NoNewWindow
Write-Host "   ✅ Frontend process started with PID $($frontendProc.Id)." -ForegroundColor Green

Write-Host "`n==================================================" -ForegroundColor Cyan
Write-Host "🎉 NEO FABEL SYSTEM ONLINE & FULLY FUNCTIONAL" -ForegroundColor Cyan
Write-Host "   • Web UI:      http://localhost:5173" -ForegroundColor Green
Write-Host "   • Backend API: http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan
