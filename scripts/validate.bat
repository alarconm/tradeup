@echo off
REM TradeUp Pre-Deployment Validation (Windows)
cd /d "%~dp0\.."
python scripts\validate.py
