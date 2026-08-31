@echo off
setlocal enabledelayedexpansion
title Captions by RegulaVitae — Standalone App Launcher

echo.
echo ============================================================
echo   Captions by RegulaVitae — Launching Application...
echo ============================================================
echo.

:: Ensure Python is available
python --version >NUL 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found on system PATH.
    echo Please install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
)

:: Run launcher.py directly via signed python.exe
python backend\launcher.py

pause
