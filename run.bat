@echo off
setlocal enabledelayedexpansion
title Xiaomi BE3600 Pro Root Toolbox

REM Change directory to script directory
cd /d "%~dp0"

REM Set console code page to UTF-8
chcp 65001 >nul 2>&1

REM Detect available Python interpreter
set "PY_CMD="

REM 1. Try python
python -c "import sys; sys.exit(0)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
    goto :run_tool
)

REM 2. Try py -3
py -3 -c "import sys; sys.exit(0)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py -3"
    goto :run_tool
)

REM 3. Try py -2
py -2 -c "import sys; sys.exit(0)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py -2"
    goto :run_tool
)

REM 4. Try py
py -c "import sys; sys.exit(0)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py"
    goto :run_tool
)

REM 5. Try python3
python3 -c "import sys; sys.exit(0)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python3"
    goto :run_tool
)

:not_found
echo.
echo =====================================================================
echo [-] Error: Python was not found on your system!
echo.
echo Please download and install Python from:
echo   https://www.python.org/downloads/
echo.
echo NOTE: Make sure to check "Add python.exe to PATH" during installation.
echo =====================================================================
echo.
goto :exit_pause

:run_tool
%PY_CMD% run.py %*
set "EXIT_CODE=!errorlevel!"

if !EXIT_CODE! neq 0 (
    echo.
    echo [-] Program exited with status code: !EXIT_CODE!
)

:exit_pause
echo.
echo Press any key to exit...
pause >nul

:end
endlocal
