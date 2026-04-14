@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "URL=http://127.0.0.1:8000/"
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

set "CHROME_PATH=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_PATH%" set "CHROME_PATH=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_PATH%" set "CHROME_PATH=%LocalAppData%\Google\Chrome\Application\chrome.exe"

if exist "%CHROME_PATH%" (
    echo Opening %URL% in Chrome...
    start "" "%CHROME_PATH%" "%URL%"
) else (
    echo Chrome was not found. Opening in the default browser instead...
    start "" "%URL%"
)

echo Starting Django server on 127.0.0.1:8000 ...
call %PYTHON_CMD% manage.py runserver 127.0.0.1:8000

pause
