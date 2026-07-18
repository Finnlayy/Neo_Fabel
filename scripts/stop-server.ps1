$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot ".." )).Path
$pidFile = Join-Path $root ".runtime\api.pid"
Set-Location $root

if (Test-Path $pidFile) {
    $pidText = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($pidText -and ($process = Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $process.Id -Force
        Write-Host "Stopped Neo Fabel API process $($process.Id)."
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
} else {
    Write-Host "No Neo Fabel API PID file found; API process was not stopped."
}

docker compose stop postgres | Out-Host
Write-Host "Stopped Neo Fabel PostgreSQL container."
