# Level 1 read-only monitor for a Level 4 autonomous session.
# Uses query endpoints only: balance + open-orders. Alerts on threshold breaches.
#
# Usage:
#   .\scripts\kraken-level1-monitor.ps1
#   .\scripts\kraken-level1-monitor.ps1 -IntervalSeconds 30 -MaxOpenOrders 3

param(
    [int]$IntervalSeconds = 30,
    [int]$MaxOpenOrders = 3,
    [switch]$Once
)

$ErrorActionPreference = "Continue"

if (-not (Get-Command kraken -ErrorAction SilentlyContinue)) {
    Write-Error "kraken CLI not found on PATH"
    exit 1
}

function Get-OpenOrderCount {
    param($Payload)
    if ($null -eq $Payload) { return 0 }
    if ($Payload.open) { return @($Payload.open.PSObject.Properties).Count }
    if ($Payload.result -and $Payload.result.open) {
        return @($Payload.result.open.PSObject.Properties).Count
    }
    if ($Payload.orders) { return @($Payload.orders).Count }
    return 0
}

function Invoke-MonitorPass {
    $stamp = Get-Date -Format "o"
    $alerts = @()

    try {
        $balanceRaw = & kraken balance -o json 2>&1
        if ($LASTEXITCODE -ne 0) { throw "balance failed: $balanceRaw" }
        $balance = $balanceRaw | Out-String | ConvertFrom-Json
        Write-Host "[$stamp] balance ok"
    } catch {
        $alerts += "balance: $_"
        Write-Host "[$stamp] ALERT balance — $_" -ForegroundColor Red
    }

    try {
        $ordersRaw = & kraken open-orders -o json 2>&1
        if ($LASTEXITCODE -ne 0) { throw "open-orders failed: $ordersRaw" }
        $orders = $ordersRaw | Out-String | ConvertFrom-Json
        $count = Get-OpenOrderCount $orders
        Write-Host "[$stamp] open_orders=$count (max=$MaxOpenOrders)"
        if ($count -gt $MaxOpenOrders) {
            $alerts += "open_orders $count exceeds max $MaxOpenOrders"
            Write-Host "[$stamp] ALERT open_orders breach" -ForegroundColor Red
        }
    } catch {
        $alerts += "open-orders: $_"
        Write-Host "[$stamp] ALERT open-orders — $_" -ForegroundColor Red
        if ("$_" -match "auth") {
            Write-Host "[$stamp] AUTH failure — Level 4 agent must STOP trading" -ForegroundColor Magenta
        }
    }

    return $alerts.Count
}

if ($Once) {
    $n = Invoke-MonitorPass
    exit $(if ($n -gt 0) { 1 } else { 0 })
}

Write-Host "Level 1 monitor every ${IntervalSeconds}s (Ctrl+C to stop)" -ForegroundColor Cyan
Write-Host "Max open orders threshold: $MaxOpenOrders"
while ($true) {
    Invoke-MonitorPass | Out-Null
    Start-Sleep -Seconds $IntervalSeconds
}
