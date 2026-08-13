@echo off
title Launch Neo Fabel Stack
cd /d "%~dp0.."
powershell -ExecutionPolicy Bypass -File "%~dp0run-all.ps1"
pause
