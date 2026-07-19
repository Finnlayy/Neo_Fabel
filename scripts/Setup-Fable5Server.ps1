#Requires -Version 5.1
<#
.SYNOPSIS
  One-click FABLE 5 / Neo_Fabel local server setup.

.DESCRIPTION
  Installs dependencies, enables TradingView paper ingress, starts Docker
  services (Postgres, Qdrant, API, signal-worker), starts Vite, opens an ngrok
  tunnel to the API, and writes the webhook base URL to the Desktop.
#>
param(
    [string]$RepoRoot = "D:\Neo_Fabel",
    [switch]$SkipNpm,
    [switch]$SkipDockerBuild,
    [switch]$NoNgrok,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$Desktop = [Environment]::GetFolderPath("Desktop")
$LogFile = Join-Path $Desktop "Fable5-Setup.log"
$UrlFile = Join-Path $Desktop "Fable5-TradingView-Webhook-Base.txt"

function Write-Log {
    param([string]$Message, [string]$Color = "White")
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $line -ForegroundColor $Color
    Add-Content -Path $LogFile -Value $line
}

function Assert-Command {
    param([string]$Name, [string]$Hint)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing required command '$Name'. $Hint"
    }
}

function Ensure-DockerDesktop {
    try {
        docker info 1>$null 2>$null
        if ($LASTEXITCODE -eq 0) { return }
    } catch {}

    Write-Log "Starting Docker Desktop..." "Yellow"
    $dockerUi = "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $dockerUi)) {
        throw "Docker Desktop not found at $dockerUi. Install Docker Desktop first."
    }
    Start-Process $dockerUi | Out-Null
    $deadline = (Get-Date).AddMinutes(3)
    do {
        Start-Sleep -Seconds 5
        docker info 1>$null 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Log "Docker Desktop is ready." "Green"
            return
        }
    } while ((Get-Date) -lt $deadline)
    throw "Docker Desktop did not become ready within 3 minutes."
}

function Set-DotEnvValue {
    param([string]$Path, [string]$Name, [string]$Value)
    $content = if (Test-Path $Path) { Get-Content $Path -Raw } else { "" }
    if ($content -match "(?m)^$([regex]::Escape($Name))=") {
        $content = [regex]::Replace($content, "(?m)^$([regex]::Escape($Name))=.*$", "$Name=$Value")
    } else {
        if ($content -and -not $content.EndsWith("`n")) { $content += "`r`n" }
        $content += "$Name=$Value`r`n"
    }
    Set-Content -Path $Path -Value $content -NoNewline
}

function Get-DotEnvValue {
    param([string]$Path, [string]$Name)
    if (-not (Test-Path $Path)) { return "" }
    $line = Select-String -Path $Path -Pattern "^$([regex]::Escape($Name))=(.*)$" | Select-Object -First 1
    if (-not $line) { return "" }
    return $line.Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'")
}

function Ensure-KrakenCli {
    $shimDir = Join-Path $RepoRoot "scripts\bin"
    $shim = Join-Path $shimDir "kraken.cmd"
    New-Item -ItemType Directory -Force -Path $shimDir | Out-Null
    if (-not (Test-Path $shim)) {
        @"
@echo off
set "WSLENV=KRAKEN_API_KEY/u:KRAKEN_API_SECRET/u:%WSLENV%"
wsl -e /root/.cargo/bin/kraken %*
"@ | Set-Content -Path $shim -Encoding ASCII
    }
    $env:Path = "$shimDir;" + $env:Path

    if (Get-Command wsl -ErrorAction SilentlyContinue) {
        wsl -e bash -lc "if [ ! -x /root/.cargo/bin/kraken ]; then curl --proto '=https' --tlsv1.2 -LsSf https://github.com/krakenfx/kraken-cli/releases/latest/download/kraken-cli-installer.sh | sh; fi; /root/.cargo/bin/kraken --version" | Out-Null
    }
}

try {
    "" | Set-Content $LogFile
    Write-Log "=== FABLE 5 server setup starting ===" "Cyan"
    Write-Log "Repo: $RepoRoot"

    if (-not (Test-Path $RepoRoot)) {
        throw "Repo not found: $RepoRoot"
    }
    Set-Location $RepoRoot

    Assert-Command "npm" "Install Node.js 20+ from https://nodejs.org"
    Assert-Command "python" "Install Python 3.11+ and ensure it is on PATH"
    Assert-Command "docker" "Install Docker Desktop for Windows"

    Ensure-DockerDesktop
    Ensure-KrakenCli

    $envLocal = Join-Path $RepoRoot ".env.local"
    $envExample = Join-Path $RepoRoot ".env.example"
    if (-not (Test-Path $envLocal)) {
        if (-not (Test-Path $envExample)) { throw ".env.example missing" }
        Copy-Item $envExample $envLocal
        Write-Log "Created .env.local from .env.example" "Yellow"
    }

    # Paper-safe TradingView ingress defaults
    Set-DotEnvValue $envLocal "SIGNAL_ROUTES_ENABLED" "true"
    Set-DotEnvValue $envLocal "TRADINGVIEW_INGRESS_ENABLED" "true"
    Set-DotEnvValue $envLocal "SIGNAL_WORKER_ENABLED" "true"
    Set-DotEnvValue $envLocal "SIGNAL_EXECUTION_ENABLED" "true"
    Set-DotEnvValue $envLocal "MCP_SIGNAL_ADAPTER_ENABLED" "false"
    Set-DotEnvValue $envLocal "AI_ADVISORY_ENABLED" "false"
    Set-DotEnvValue $envLocal "KRAKEN_AUTONOMY_LEVEL" "2"
    Set-DotEnvValue $envLocal "KRAKEN_LIVE_TRADING_ENABLED" "false"

    $pepper = Get-DotEnvValue $envLocal "SIGNAL_CREDENTIAL_PEPPER"
    if ([string]::IsNullOrWhiteSpace($pepper)) {
        $bytes = New-Object byte[] 32
        [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        $pepper = ($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
        Set-DotEnvValue $envLocal "SIGNAL_CREDENTIAL_PEPPER" $pepper
        Write-Log "Generated SIGNAL_CREDENTIAL_PEPPER" "Yellow"
    }

    if (-not $SkipNpm) {
        Write-Log "npm install..." "Cyan"
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
    }

    Write-Log "Python backend deps..." "Cyan"
    python -m pip install -e "backend[test,lint]"
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

    Write-Log "Starting Docker services (postgres, qdrant, api, signal-worker)..." "Cyan"
    $composeArgs = @(
        "compose", "--env-file", ".env.local", "--profile", "signals",
        "up", "-d", "postgres", "qdrant", "api", "signal-worker"
    )
    if (-not $SkipDockerBuild) {
        $composeArgs += "--build"
    }
    & docker @composeArgs
    if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }

    Write-Log "Waiting for API /health/live ..." "Cyan"
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health/live" -UseBasicParsing -TimeoutSec 3
            if ($resp.StatusCode -eq 200) { $ready = $true; break }
        } catch {}
        Start-Sleep -Seconds 2
    }
    if (-not $ready) { throw "API did not become healthy on :8000" }
    Write-Log "API is healthy on http://127.0.0.1:8000" "Green"

    # Vite UI
    Write-Log "Starting Vite UI on :5173 ..." "Cyan"
    $viteCmd = "Set-Location '$RepoRoot'; npm run dev"
    Start-Process powershell -ArgumentList @("-NoExit", "-NoProfile", "-Command", $viteCmd) | Out-Null

    $publicBase = "http://127.0.0.1:8000"
    if (-not $NoNgrok) {
        if (Get-Command ngrok -ErrorAction SilentlyContinue) {
            Write-Log "Starting ngrok http 8000 ..." "Cyan"
            Get-Process ngrok -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
            Start-Process ngrok -ArgumentList @("http", "8000", "--log=stdout") -WindowStyle Minimized
            Start-Sleep -Seconds 4
            try {
                $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -TimeoutSec 5
                $https = $tunnels.tunnels | Where-Object { $_.public_url -like "https://*" } | Select-Object -First 1
                if ($https) {
                    $publicBase = $https.public_url.TrimEnd("/")
                    Write-Log "ngrok public URL: $publicBase" "Green"
                } else {
                    Write-Log "ngrok running but no https tunnel yet — check http://127.0.0.1:4040" "Yellow"
                }
            } catch {
                Write-Log "Could not read ngrok API yet. Open http://127.0.0.1:4040" "Yellow"
            }
        } else {
            Write-Log "ngrok not found — TradingView needs a public HTTPS URL. Install ngrok and re-run." "Yellow"
        }
    }

    $webhookTemplate = @"
FABLE 5 / Neo_Fabel — TradingView webhook

1) Public API base (use this host):
   $publicBase

2) In the Fabel UI (http://localhost:5173) open Signal Routes (shortcut 5),
   sign in with a signal_admin Firebase user, create a route, rotate the
   TradingView credential, and copy the path shown as:
     /api/v1/webhooks/tradingview/<public_route_key>

3) Full URL for TradingView alert webhook:
   $publicBase/api/v1/webhooks/tradingview/<public_route_key>

4) Alert JSON must include schema_version=1 and the rotated credential.
   Execution target is kraken_paper (NOT live Kraken).

Local API:  http://127.0.0.1:8000
Local UI:   http://localhost:5173
Log:        $LogFile
"@
    Set-Content -Path $UrlFile -Value $webhookTemplate -Encoding UTF8
    Write-Log "Wrote $UrlFile" "Green"

    if (-not $NoBrowser) {
        Start-Process "http://localhost:5173"
        if ($publicBase -like "https://*") {
            Start-Process "http://127.0.0.1:4040"
        }
    }

    Write-Log "=== SETUP COMPLETE ===" "Green"
    Write-Host ""
    Write-Host $webhookTemplate -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Press Enter to close this window..." -ForegroundColor DarkGray
    Read-Host | Out-Null
    exit 0
}
catch {
    Write-Log "SETUP FAILED: $($_.Exception.Message)" "Red"
    Write-Host $_.ScriptStackTrace -ForegroundColor DarkRed
    Write-Host "Press Enter to close..." -ForegroundColor DarkGray
    Read-Host | Out-Null
    exit 1
}
