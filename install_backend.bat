@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ======================================
echo Backend setup started
echo ======================================

set "PYTHON_CMD="

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=python"
    )
)

if not defined PYTHON_CMD (
    echo [ERROR] Python is not installed or not added to PATH.
    pause
    exit /b 1
)

echo [1/4] Using system Python without virtual environment...
call %PYTHON_CMD% --version
if errorlevel 1 goto :error

echo [2/4] Upgrading pip...
call %PYTHON_CMD% -m pip install --upgrade pip
if errorlevel 1 goto :error

echo [3/4] Installing requirements globally for this Python...
call %PYTHON_CMD% -m pip install -r requirements.txt
if errorlevel 1 goto :error

if exist "run_setup.py" (
    echo [4/4] Running project setup script...
    call %PYTHON_CMD% run_setup.py
    if errorlevel 1 (
        echo [WARNING] run_setup.py returned an error. Continuing with Django commands...
    )
) else (
    echo [4/4] No extra setup script found. Skipping.
)

echo Applying migrations...
call %PYTHON_CMD% manage.py migrate
if errorlevel 1 goto :error

echo Checking project...
call %PYTHON_CMD% manage.py check
if errorlevel 1 goto :error

echo.
echo ======================================
echo Backend setup completed successfully.
echo ======================================
pause
exit /b 0

:error
echo.
echo [ERROR] Setup failed.
pause
exit /b 1
