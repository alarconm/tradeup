@echo off
REM TradeUp Validate and Push (Windows)
cd /d "%~dp0\.."

echo Running pre-deployment validation...
python scripts\validate.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo VALIDATION FAILED - Push blocked
    echo Fix the issues above before pushing.
    exit /b 1
)

echo.
echo Validation passed! Pushing to main...
git push origin main

echo.
echo Pushed! Railway will auto-deploy.
echo Monitor at: https://railway.app
