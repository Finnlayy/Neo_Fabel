# PowerShell: register Windows Task Scheduler jobs for Neo Trade Agent.
# Adapted from Fable5 TradeAgent setup_scheduled_tasks.ps1
#
# Run (normal user is enough for Interactive tasks):
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup_scheduled_tasks.ps1
#
# Optional:
#   -UnregisterOnly   Remove NeoFabel_* tasks without recreating
#   -IncludeOptimizer Also register 02:30 overnight GA optimizer

param(
    [switch]$UnregisterOnly,
    [switch]$IncludeOptimizer
)

$ErrorActionPreference = "Stop"
$ProjectPath = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ScriptsPath = Join-Path $ProjectPath "scripts"
$LogsPath = Join-Path $ProjectPath "logs"

Write-Host "Neo Trade Agent — Windows Task Scheduler setup" -ForegroundColor Green
Write-Host "Project: $ProjectPath" -ForegroundColor DarkGray
Write-Host ""

if (-not (Test-Path $LogsPath)) {
    New-Item -ItemType Directory -Path $LogsPath | Out-Null
    Write-Host "Created logs directory: $LogsPath" -ForegroundColor Yellow
}

function Remove-NeoTask([string]$Name) {
    Unregister-ScheduledTask -TaskName $Name -Confirm:$false -ErrorAction SilentlyContinue
}

function Register-NeoDailyTask {
    param(
        [Parameter(Mandatory)][string]$TaskName,
        [Parameter(Mandatory)][string]$BatFile,
        [Parameter(Mandatory)][string]$At,
        [Parameter(Mandatory)][string]$Description
    )
    $batFull = Join-Path $ScriptsPath $BatFile
    if (-not (Test-Path $batFull)) {
        Write-Host "  SKIP: missing $BatFile" -ForegroundColor Yellow
        return
    }
    Write-Host "Creating $TaskName ($At daily)..." -ForegroundColor Cyan
    $action = New-ScheduledTaskAction -Execute $batFull -WorkingDirectory $ProjectPath
    $trigger = New-ScheduledTaskTrigger -Daily -At $At
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive -RunLevel Limited
    try {
        Remove-NeoTask $TaskName
        Register-ScheduledTask `
            -TaskName $TaskName `
            -Action $action `
            -Trigger $trigger `
            -Settings $settings `
            -Principal $principal `
            -Description $Description | Out-Null
        Write-Host "  SUCCESS: $TaskName" -ForegroundColor Green
    } catch {
        Write-Host "  ERROR: $TaskName — $($_.Exception.Message)" -ForegroundColor Red
    }
}

$taskNames = @(
    "NeoFabel_MorningScan",
    "NeoFabel_PreOpenScan",
    "NeoFabel_MarketScan",
    "NeoFabel_LabelTrades",
    "NeoFabel_Optimizer"
)

if ($UnregisterOnly) {
    Write-Host "Removing NeoFabel_* scheduled tasks..." -ForegroundColor Yellow
    foreach ($n in $taskNames) { Remove-NeoTask $n }
    Write-Host "Done." -ForegroundColor Green
    return
}

# Same Berlin wall-clock slots as Fable5 TradeAgent
Register-NeoDailyTask `
    -TaskName "NeoFabel_MorningScan" `
    -BatFile "schedule_morning_scan.bat" `
    -At "07:00AM" `
    -Description "Neo pre-market / morning momentum scan (07:00 Berlin)"

Register-NeoDailyTask `
    -TaskName "NeoFabel_PreOpenScan" `
    -BatFile "schedule_preopen_scan.bat" `
    -At "03:00PM" `
    -Description "Neo pre-open scan (15:00 Berlin / ~09:00 ET, 30m before US open)"

Register-NeoDailyTask `
    -TaskName "NeoFabel_MarketScan" `
    -BatFile "schedule_market_scan.bat" `
    -At "04:00PM" `
    -Description "Neo market-hours scan (16:00 Berlin / ~10:00 ET)"

Register-NeoDailyTask `
    -TaskName "NeoFabel_LabelTrades" `
    -BatFile "schedule_label_trades.bat" `
    -At "06:00PM" `
    -Description "Neo ML paper-fill labeling (18:00 Berlin / 12:00 ET)"

if ($IncludeOptimizer) {
    Register-NeoDailyTask `
        -TaskName "NeoFabel_Optimizer" `
        -BatFile "schedule_optimizer.bat" `
        -At "02:30AM" `
        -Description "Neo overnight GA optimizer (02:30 Berlin)"
} else {
    Remove-NeoTask "NeoFabel_Optimizer"
    Write-Host "Optimizer task skipped (pass -IncludeOptimizer to register 02:30)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "SCHEDULED TASKS SETUP COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Daily schedule (Berlin wall clock):" -ForegroundColor Yellow
Write-Host "  07:00 - Morning Pre-Market Scan" -ForegroundColor White
Write-Host "  15:00 - Pre-Open Scan (30 min before US cash open)" -ForegroundColor White
Write-Host "  16:00 - Market Hours Scan" -ForegroundColor White
Write-Host "  18:00 - ML Trade Labeling" -ForegroundColor White
if ($IncludeOptimizer) {
    Write-Host "  02:30 - GA Optimizer" -ForegroundColor White
}
Write-Host ""
Write-Host "Tasks are paper-first (FableEngine dry-run / label / GA)." -ForegroundColor DarkGray
Write-Host "View: Task Scheduler -> Task Scheduler Library -> NeoFabel_*" -ForegroundColor Yellow
Write-Host "Remove all: powershell -File .\scripts\setup_scheduled_tasks.ps1 -UnregisterOnly" -ForegroundColor Yellow
Write-Host "Logs: $LogsPath" -ForegroundColor Cyan
Write-Host ""
