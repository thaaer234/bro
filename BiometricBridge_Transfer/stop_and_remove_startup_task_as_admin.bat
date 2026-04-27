@echo off
setlocal

del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BiometricBridge_ensure_running.bat" >nul 2>&1
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BiometricBridge_start.bat" >nul 2>&1
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BiometricBridge Watchdog.lnk" >nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "BiometricBridgeWatchdog" /f >nul 2>&1
taskkill /F /IM biometric_bridge.exe >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*watchdog_loop.bat*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo.
echo Biometric Bridge startup entry stopped and removed.
pause
endlocal
