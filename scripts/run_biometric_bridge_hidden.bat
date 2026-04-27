@echo off
cd /d %~dp0\..
start "" /min dist\biometric_bridge.exe --config biometric_bridge_config.json
