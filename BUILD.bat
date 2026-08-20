@echo off
title Build DPDP Scanner .exe
color 0B

echo.
echo  ================================================
echo   DPDP SCANNER - BUILD STANDALONE .EXE
echo  ================================================
echo.
echo  This is a ONE-TIME build step. It requires Python.
echo  The .exe it produces will NOT require Python or any
echo  dependencies to run — copy it anywhere and double-click.
echo.

python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo  [ERROR] Python not found.
    echo          Install Python 3.11+ from https://python.org
    echo          ^(check "Add python.exe to PATH" during install^),
    echo          then run BUILD.bat again.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo  [OK] Python %PYVER% found.
echo.

echo  [..] Installing build dependencies (this happens once)...
python -m pip install -r requirements.txt pyinstaller --quiet --no-warn-script-location
IF %ERRORLEVEL% NEQ 0 (
    echo  [ERROR] pip install failed. Try running as Administrator.
    pause
    exit /b 1
)
echo  [OK] Dependencies installed.
echo.

echo  [..] Building DPDP_Scanner.exe — this takes 2-5 minutes...
echo.
python -m PyInstaller dpdp_scanner.spec --clean --noconfirm

IF NOT EXIST "dist\DPDP_Scanner.exe" (
    echo.
    echo  [ERROR] Build failed — DPDP_Scanner.exe was not created.
    echo          Scroll up for the PyInstaller error output.
    pause
    exit /b 1
)

echo.
echo  ================================================
echo   BUILD COMPLETE
echo  ================================================
echo.
echo   Your standalone app is here:
echo     dist\DPDP_Scanner.exe
echo.
echo   Copy that single file anywhere — a USB stick, another
echo   PC, a shared drive — and double-click it to run.
echo   No Python, no pip, no internet required to run it.
echo.
echo  ================================================
pause
