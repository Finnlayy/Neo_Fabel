$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot ".." )).Path
$runtime = Join-Path $root ".runtime"
$pidFile = Join-Path $runtime "api.pid"
New-Item -ItemType Directory -Path $runtime -Force | Out-Null

Set-Location $root
docker compose up -d postgres
docker compose ps

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
if (-not $healthy) {
    throw "PostgreSQL did not become healthy within 60 seconds."
}

alembic -c backend/alembic.ini upgrade head

if (Test-Path $pidFile) {
    $existingPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($existingPid -and (Get-Process -Id ([int]$existingPid) -ErrorAction SilentlyContinue)) {
        Write-Host "Neo Fabel API is already running with PID $existingPid."
        Wait-Process -Id ([int]$existingPid)
        exit
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

$api = Start-Process -FilePath "python" -ArgumentList @(
    "-m", "uvicorn", "backend.app.main:app", "--port", "8000"
) -WorkingDirectory $root -PassThru
$api.Id | Set-Content -Path $pidFile -NoNewline
Write-Host "Neo Fabel API running at http://127.0.0.1:8000 (PID $($api.Id))."
Write-Host "Use the desktop stop shortcut to shut it down."
Wait-Process -Id $api.Id
Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
