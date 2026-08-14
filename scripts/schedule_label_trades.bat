@echo off
REM Neo Trade Agent — Label paper fills for ML (18:00 Berlin / 12:00 ET)
REM Mirrors Fable5 TradeAgent schedule_label_trades.bat

cd /d "%~dp0.."
if not exist "logs" mkdir logs
set PYTHONPATH=%CD%
python -m backend.scripts.run_trade_agent label >> logs\labeling.log 2>&1
