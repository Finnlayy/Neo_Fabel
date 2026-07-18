@echo off
REM Official kraken-cli ships Linux/macOS binaries only; forward to WSL.
set "WSLENV=KRAKEN_API_KEY/u:KRAKEN_API_SECRET/u:%WSLENV%"
wsl -e /root/.cargo/bin/kraken %*
