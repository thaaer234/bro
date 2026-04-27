@echo off
title Biometric Bridge Watchdog
cd /d %~dp0

:loop
tasklist /FI "IMAGENAME eq biometric_bridge.exe" 2>nul | find /I "biometric_bridge.exe" >nul
if not %errorlevel%==0 (
  start "" /min "%~dp0dist\biometric_bridge.exe" --config "%~dp0biometric_bridge_config.json"
)
timeout /t 60 /nobreak >nul
goto loop

