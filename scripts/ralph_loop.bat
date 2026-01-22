@echo off
setlocal enabledelayedexpansion

REM Ralph Autonomous Loop Runner
REM This script runs Claude sessions one at a time until all stories complete
REM
REM Usage: scripts\ralph_loop.bat
REM To run in background: start /min scripts\ralph_loop.bat

cd /d "%~dp0.."
echo ============================================================
echo Ralph Autonomous Loop Runner
echo Working directory: %CD%
echo ============================================================
echo.

:loop
REM Get next story
echo.
echo Checking for next story...
for /f "tokens=*" %%i in ('python scripts/ralph_helper.py next 2^>^&1') do (
    echo %%i
    echo %%i | findstr /C:"ALL_COMPLETE" >nul && goto :complete
    echo %%i | findstr /C:"STORY:" >nul && set "line=%%i"
)

REM Extract story ID from output
for /f "tokens=2 delims=:" %%a in ("!line!") do set "STORY_ID=%%a"

if "!STORY_ID!"=="" (
    echo ERROR: Could not determine next story
    timeout /t 10
    goto :loop
)

echo.
echo ============================================================
echo Running Claude session for: !STORY_ID!
echo ============================================================
echo.

REM Run Claude with the prompt
REM Read prompt and pass to Claude using -p flag
set /p PROMPT=<".ralph-current-prompt.txt"

REM For long prompts, use stdin approach with --print for non-interactive
type ".ralph-current-prompt.txt" | claude --print --dangerously-skip-permissions

REM Check exit code
if %ERRORLEVEL% EQU 0 (
    echo.
    echo Session completed successfully, marking story as done...
    python scripts/ralph_helper.py mark
) else (
    echo.
    echo Session failed with error code %ERRORLEVEL%
    echo Waiting before retry...
    timeout /t 30
)

REM Brief pause between stories
timeout /t 5 /nobreak >nul

goto :loop

:complete
echo.
echo ============================================================
echo ALL STORIES COMPLETE!
echo Ralph has finished all PRDs.
echo ============================================================
pause
