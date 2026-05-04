@echo off
REM FastAPI Trash Classification - Startup

setlocal enabledelayedexpansion

echo.
echo ===== TRASH CLASSIFICATION SYSTEM =====
echo.

echo Checking Python...
python --version
if errorlevel 1 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)

echo.
echo Starting FastAPI server...
echo Press Ctrl+C to stop server
echo.

cd /d "%~dp0"
python -m app.run

echo.
echo Server stopped.
pause
