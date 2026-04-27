@echo off
cd /d %~dp0
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "Start-Process -WindowStyle Hidden -FilePath '%~dp0watchdog_loop.bat'"

