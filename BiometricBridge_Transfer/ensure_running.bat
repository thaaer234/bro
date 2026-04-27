@echo off
cd /d %~dp0

tasklist /FI "IMAGENAME eq biometric_bridge.exe" 2>nul | find /I "biometric_bridge.exe" >nul
if %errorlevel%==0 (
  exit /b 0
)

start "" /min "%~dp0dist\biometric_bridge.exe" --config "%~dp0biometric_bridge_config.json"
exit /b 0
