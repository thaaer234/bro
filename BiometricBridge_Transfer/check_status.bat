@echo off
echo Checking Startup folder entry...
echo.
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BiometricBridge_start.bat" (
  echo Startup BAT exists:
  echo %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BiometricBridge_start.bat
) else (
  echo Startup BAT is missing.
)
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BiometricBridge Watchdog.lnk" (
  echo Startup shortcut exists:
  echo %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BiometricBridge Watchdog.lnk
) else (
  echo Startup shortcut is missing.
)
echo.
echo Checking registry fallback...
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "BiometricBridgeWatchdog"
echo.
echo Checking watchdog process...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*watchdog_loop.bat*' } | Select-Object ProcessId,CommandLine | Format-Table -Wrap"
echo.
echo Checking running process...
powershell -NoProfile -Command "Get-Process | Where-Object { $_.ProcessName -like '*biometric*' } | Select-Object ProcessName,Id,Path | Format-Table -AutoSize"
echo.
echo Last log lines:
if exist "%~dp0biometric_bridge.log" (
  powershell -NoProfile -Command "Get-Content -Tail 30 '%~dp0biometric_bridge.log'"
) else (
  echo No biometric_bridge.log file found yet.
)
echo.
pause
