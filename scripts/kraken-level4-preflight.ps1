# Level 4 session checklist + preflight (spot)
# Requires: kraken CLI on PATH, trade-only API credentials in env or `kraken auth set`
#
# Usage:
#   .\scripts\kraken-level4-preflight.ps1
#   .\scripts\kraken-level4-preflight.ps1 -AutonomyLevel 4 -LiveEnabled

param(
    [int]$AutonomyLevel = 4,
    [switch]$LiveEnabled,
    [int]$DeadmanSeconds = 600,
    [string]$MaxOrderSize = "0.01",
    [int]$MaxOpenPositions = 3,
    [int]$MaxTradesPerHour = 10,
    [string]$PairAllowlist = "BTCUSD,ETHUSD"
)

$ErrorActionPreference = "Stop"

function Invoke-KrakenJson {
    param([Parameter(Mandatory = $true)][string[]]$KrakenArgs)
    $raw = & kraken @KrakenArgs -o json 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "kraken $($KrakenArgs -join ' ') failed: $raw"
    }
    return $raw | Out-String | ConvertFrom-Json
}

Write-Host "=== Kraken Level 4 Preflight ===" -ForegroundColor Cyan

if (-not (Get-Command kraken -ErrorAction SilentlyContinue)) {
    Write-Host "[FAIL] kraken CLI not found on PATH" -ForegroundColor Red
    Write-Host "Install: https://github.com/krakenfx/kraken-cli/releases"
    exit 1
}
Write-Host "[OK]   kraken CLI present: $(kraken --version)"

if (-not $env:KRAKEN_API_KEY -or -not $env:KRAKEN_API_SECRET) {
    Write-Host "[WARN] KRAKEN_API_KEY / KRAKEN_API_SECRET unset - falling back to kraken auth config" -ForegroundColor Yellow
} else {
    Write-Host "[OK]   API credentials present in environment"
}

Write-Host ""
Write-Host "Configured guardrails (defaults for Level 4 agent code):"
Write-Host "  autonomy_level       = $AutonomyLevel"
Write-Host "  live_enabled         = $LiveEnabled"
Write-Host "  deadman_seconds      = $DeadmanSeconds"
Write-Host "  max_order_size       = $MaxOrderSize"
Write-Host "  max_open_positions   = $MaxOpenPositions"
Write-Host "  max_trades_per_hour  = $MaxTradesPerHour"
Write-Host "  pair_allowlist       = $PairAllowlist"
Write-Host ""
Write-Host "Checklist:"
Write-Host "  [ ] API key is trade-only (NO Withdraw Funds)"
Write-Host "  [ ] Level 3 supervised trading was consistent for >= 1 week"
Write-Host "  [ ] Separate Level 1 monitor process will run alongside the agent"
Write-Host ""

$failed = $false

try {
    $null = Invoke-KrakenJson -KrakenArgs @("auth", "test")
    Write-Host "[OK]   auth test"
} catch {
    Write-Host "[FAIL] auth test: $_" -ForegroundColor Red
    $failed = $true
}

try {
    $null = Invoke-KrakenJson -KrakenArgs @("balance")
    Write-Host "[OK]   balance"
} catch {
    Write-Host "[FAIL] balance: $_" -ForegroundColor Red
    $failed = $true
}

try {
    $null = Invoke-KrakenJson -KrakenArgs @("open-orders")
    Write-Host "[OK]   open-orders"
} catch {
    Write-Host "[FAIL] open-orders: $_" -ForegroundColor Red
    $failed = $true
}

foreach ($pair in ($PairAllowlist -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ })) {
    try {
        $null = Invoke-KrakenJson -KrakenArgs @("pairs", "--pair", $pair)
        Write-Host "[OK]   pair $pair tradable"
    } catch {
        Write-Host "[FAIL] pair ${pair}: $_" -ForegroundColor Red
        $failed = $true
    }
}

# Validate a tiny sample order (no submission)
$samplePair = ($PairAllowlist -split ",")[0].Trim()
try {
    $null = Invoke-KrakenJson -KrakenArgs @(
        "order", "buy", $samplePair, $MaxOrderSize,
        "--type", "limit", "--price", "1", "--validate"
    )
    Write-Host "[OK]   sample order --validate for $samplePair volume $MaxOrderSize"
} catch {
    Write-Host "[WARN] sample validate failed (pair/price may be unrealistic): $_" -ForegroundColor Yellow
}

if ($LiveEnabled -and $AutonomyLevel -ge 4) {
    try {
        $null = Invoke-KrakenJson -KrakenArgs @("order", "cancel-after", "$DeadmanSeconds")
        Write-Host "[OK]   deadman switch armed (${DeadmanSeconds}s)"
        Write-Host "       Refresh with: .\scripts\kraken-deadman-refresh.ps1 -Seconds $DeadmanSeconds"
    } catch {
        Write-Host "[FAIL] deadman switch: $_" -ForegroundColor Red
        $failed = $true
    }
} else {
    Write-Host "[SKIP] deadman switch (pass -LiveEnabled and AutonomyLevel 4 to arm)" -ForegroundColor Yellow
}

Write-Host ""
if ($failed) {
    Write-Host "Preflight FAILED - do not start Level 4 session." -ForegroundColor Red
    exit 1
}
Write-Host "Preflight PASSED. Next: start Level 1 monitor, then autonomous agent." -ForegroundColor Green
Write-Host "  .\scripts\kraken-level1-monitor.ps1"
Write-Host "  .\scripts\kraken-deadman-refresh.ps1 -Loop"
