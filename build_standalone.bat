@echo off
setlocal enabledelayedexpansion
color 0E
title Verbum — Standalone Build

echo.
echo ============================================================
echo   Verbum — Standalone Build Script
echo ============================================================
echo.

:: ============================================================
:: STEP 0: Check prerequisites
:: ============================================================

echo [0/5] Checking prerequisites...

:: Check ffmpeg.exe is in place
if not exist "backend\bin\ffmpeg.exe" (
    echo.
    echo  [ERROR] backend\bin\ffmpeg.exe not found!
    echo.
    echo  Please download FFmpeg for Windows:
    echo    https://www.gyan.dev/ffmpeg/builds/
    echo    - Download: ffmpeg-release-essentials.zip
    echo    - Extract and copy bin\ffmpeg.exe to backend\bin\ffmpeg.exe
    echo.
    pause
    exit /b 1
)
echo  [OK] ffmpeg.exe found.

:: Check Python
python --version >NUL 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found on PATH. Install Python 3.10+ and try again.
    pause
    exit /b 1
)
echo  [OK] Python found.

:: Check Node
node --version >NUL 2>&1
if errorlevel 1 (
    echo  [ERROR] Node.js not found on PATH. Install Node.js 20+ and try again.
    pause
    exit /b 1
)
echo  [OK] Node.js found.

echo.

:: ============================================================
:: STEP 1: Install Python standalone dependencies
:: ============================================================

echo [1/5] Installing Python dependencies (standalone)...
pip install -r backend\requirements_standalone.txt --quiet
if errorlevel 1 (
    echo  [ERROR] pip install failed.
    pause
    exit /b 1
)
pip install pyinstaller --quiet
echo  [OK] Python packages installed.
echo.

:: ============================================================
:: STEP 2: Build the React frontend
:: ============================================================

echo [2/5] Building React frontend...
cd frontend
call npm install --silent
set VITE_API_URL=http://localhost:8000
call npm run build
if errorlevel 1 (
    echo  [ERROR] npm run build failed.
    cd ..
    pause
    exit /b 1
)
cd ..
echo  [OK] Frontend built successfully. (frontend\dist\)
echo.

:: ============================================================
:: STEP 3: Run PyInstaller
:: ============================================================

echo [3/5] Running PyInstaller (this may take 5-15 minutes)...
pyinstaller Verbum.spec --noconfirm
if errorlevel 1 (
    echo  [ERROR] PyInstaller failed. Check the output above for details.
    pause
    exit /b 1
)
echo  [OK] PyInstaller complete. Output: dist\Verbum\
echo.

:: ============================================================
:: STEP 4: Test the executable (optional quick check)
:: ============================================================

if not exist "dist\Verbum\Verbum.exe" (
    echo  [ERROR] dist\Verbum\Verbum.exe was not created.
    pause
    exit /b 1
)
echo [4/5] Executable verified: dist\Verbum\Verbum.exe
echo.

:: ============================================================
:: STEP 5: Compile Inno Setup installer (optional)
:: ============================================================

echo [5/5] Checking for Inno Setup to create installer...

set ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if not exist "%ISCC_PATH%" (
    set ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe
)

if exist "%ISCC_PATH%" (
    echo  Inno Setup found. Creating installer...
    mkdir installer_output 2>NUL
    "%ISCC_PATH%" installer\verbum_setup.iss
    if errorlevel 1 (
        echo  [WARNING] Inno Setup compilation failed. The .exe folder is still usable.
    ) else (
        echo  [OK] Installer created in installer_output\
    )
) else (
    echo  [SKIP] Inno Setup not found. Skipping installer creation.
    echo         Install from https://jrsoftware.org/isinfo.php and re-run this script,
    echo         or manually compile installer\verbum_setup.iss.
)

echo.
echo ============================================================
echo   BUILD COMPLETE
echo ============================================================
echo.
echo   Distributable folder : dist\RegulaVitae_Captions\
if exist "installer_output\RegulaVitae_Captions_Setup_v1.0.0.exe" (
    echo   Windows installer    : installer_output\RegulaVitae_Captions_Setup_v1.0.0.exe
)
echo.
echo   To test locally, run: dist\RegulaVitae_Captions\RegulaVitae_Captions.exe
echo.
pause
