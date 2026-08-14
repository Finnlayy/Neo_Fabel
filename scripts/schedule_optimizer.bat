@echo off
REM Neo Trade Agent — Overnight GA optimizer (02:30 Berlin)

cd /d "%~dp0.."
if not exist "logs" mkdir logs
set PYTHONPATH=%CD%
python -m backend.scripts.run_trade_agent optimize >> logs\optimizer.log 2>&1
