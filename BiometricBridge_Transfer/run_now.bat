@echo off
cd /d %~dp0
"%~dp0dist\biometric_bridge.exe" --config "%~dp0biometric_bridge_config.json"
pause
