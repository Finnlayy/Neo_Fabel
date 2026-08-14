@echo off
REM Morning Pre-Market Scan (7:00 AM Berlin)
REM Analyzes market via Neo Trade Agent (paper dry-run scan)
REM Mirrors Fable5 TradeAgent schedule_morning_scan.bat

cd /d "%~dp0.."
if not exist "logs" mkdir logs
set PYTHONPATH=%CD%
python -m backend.scripts.run_trade_agent pre-market >> logs\morning_scan.log 2>&1
