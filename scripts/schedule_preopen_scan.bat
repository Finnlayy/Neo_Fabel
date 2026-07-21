@echo off
REM Pre-Open Scan (15:00 Berlin / 9:00 AM ET)
REM Final check before US cash open at 9:30 AM ET
REM Mirrors Fable5 TradeAgent schedule_preopen_scan.bat

cd /d "%~dp0.."
if not exist "logs" mkdir logs
set PYTHONPATH=%CD%
python -m backend.scripts.run_trade_agent pre-market >> logs\preopen_scan.log 2>&1
