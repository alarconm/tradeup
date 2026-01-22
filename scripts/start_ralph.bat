@echo off
REM Start Ralph Autonomous Runner in the background
REM Usage: scripts\start_ralph.bat

cd /d "%~dp0.."
echo Starting Ralph Autonomous Runner...
echo Log file: ralph-run.log
echo.
echo Press Ctrl+C in this window to stop Ralph.
echo.

REM Run Ralph with unlimited iterations (will run until all PRDs complete)
python scripts\ralph_runner.py --max-iterations 500 --timeout 45

echo.
echo Ralph has stopped.
pause
