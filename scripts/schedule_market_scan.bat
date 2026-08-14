@echo off
REM Neo Trade Agent — Market Hours Scan (16:00 Berlin / 10:00 ET)
REM Mirrors Fable5 TradeAgent schedule_market_scan.bat

cd /d "%~dp0.."
if not exist "logs" mkdir logs
set PYTHONPATH=%CD%
python -m backend.scripts.run_trade_agent market >> logs\market_scan.log 2>&1
