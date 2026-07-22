# MCP stdio smoke: initialize → tools/list → place_order → process_next_bar
# Datei: smoke_stdio.ps1
# Zweck: End-to-end JSON-RPC auf stdout pruefen (kein Log auf stdout).
# Usage: powershell -File mcp/fable_mcp/smoke_stdio.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $root) { $root = "D:\Neo_Fabel" }
$exe = Join-Path $root "mcp\fable_mcp\target\release\fable-mcp.exe"
if (-not (Test-Path $exe)) {
    $exe = Join-Path $root "mcp\fable_mcp\target\release\fable-mcp"
}
if (-not (Test-Path $exe)) {
    Write-Error "Release binary not found. Run: cargo build --release --manifest-path mcp/fable_mcp/Cargo.toml"
}

$env:FABLE_MCP_BRIDGE_ENABLED = "true"
$env:RUST_LOG = "fable_mcp=warn"

$requests = @(
    '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}'
    '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
    '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"place_order","arguments":{"side":"buy","volume":25,"pair":"ADAUSD","rationale":"stdio smoke"}}}'
    '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"process_next_bar","arguments":{"open":0.5,"high":0.51,"low":0.49,"close":0.505}}}'
) -join "`n"

$tmpIn = [System.IO.Path]::GetTempFileName()
$tmpOut = [System.IO.Path]::GetTempFileName()
$tmpErr = [System.IO.Path]::GetTempFileName()
try {
    Set-Content -Path $tmpIn -Value $requests -NoNewline
    $proc = Start-Process -FilePath $exe -RedirectStandardInput $tmpIn -RedirectStandardOutput $tmpOut -RedirectStandardError $tmpErr -NoNewWindow -PassThru -Wait
    $stdout = Get-Content -Raw $tmpOut
    $stderr = Get-Content -Raw $tmpErr
    Write-Host "=== stdout (JSON-RPC) ==="
    Write-Host $stdout
    if ($stderr) {
        Write-Host "=== stderr (logs) ==="
        Write-Host $stderr
    }
    if ($proc.ExitCode -ne 0) { Write-Error "fable-mcp exit $($proc.ExitCode)" }

    $lines = ($stdout -split "`n") | Where-Object { $_.Trim() -ne "" }
    if ($lines.Count -lt 4) { Write-Error "expected >=4 JSON-RPC lines, got $($lines.Count)" }
    $parsed = @()
    foreach ($line in $lines) {
        if ($line -notmatch '"jsonrpc"') { Write-Error "non-JSON-RPC on stdout: $line" }
        $parsed += ($line | ConvertFrom-Json)
    }
    $toolsText = $lines[1]
    if ($toolsText -notmatch 'place_order') { Write-Error "tools/list missing place_order" }
    $placeText = $parsed[2].result.content[0].text
    if ($placeText -notmatch 'queued') { Write-Error "place_order did not queue" }
    $barText = $parsed[3].result.content[0].text
    $bar = $barText | ConvertFrom-Json
    if (-not $bar.events -or $bar.events.Count -lt 1) { Write-Error "process_next_bar missing events" }
    if ($bar.events[0].event -ne "entry") { Write-Error "process_next_bar missing entry event" }
    Write-Host "SMOKE PASS"
} finally {
    Remove-Item -Force $tmpIn, $tmpOut, $tmpErr -ErrorAction SilentlyContinue
}
