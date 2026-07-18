# Refresh Kraken dead man's switch (cancel-after).
# If this process stops refreshing, open orders auto-cancel when the timer expires.
#
# Usage:
#   .\scripts\kraken-deadman-refresh.ps1
#   .\scripts\kraken-deadman-refresh.ps1 -Seconds 600 -Loop -IntervalSeconds 120

param(
    [int]$Seconds = 600,
    [switch]$Loop,
    [int]$IntervalSeconds = 120
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command kraken -ErrorAction SilentlyContinue)) {
    Write-Error "kraken CLI not found on PATH"
    exit 1
}

if ($Seconds -lt 1) {
    Write-Error "Seconds must be >= 1"
    exit 1
}

function Refresh-Deadman {
    $raw = & kraken order cancel-after $Seconds -o json 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "cancel-after failed: $raw"
    }
    $stamp = Get-Date -Format "o"
    Write-Host "[$stamp] deadman armed for ${Seconds}s"
}

if (-not $Loop) {
    Refresh-Deadman
    exit 0
}

Write-Host "Refreshing dead man's switch every ${IntervalSeconds}s (Ctrl+C to stop)" -ForegroundColor Cyan
while ($true) {
    try {
        Refresh-Deadman
    } catch {
        Write-Host "[ERROR] $_" -ForegroundColor Red
        Write-Host "Auth/network failure — stop autonomous trading until resolved." -ForegroundColor Red
    }
    Start-Sleep -Seconds $IntervalSeconds
}
