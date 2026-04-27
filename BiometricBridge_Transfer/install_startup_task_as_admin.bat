@echo off
setlocal
cd /d %~dp0

set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "STARTUP_BAT=%STARTUP_DIR%\BiometricBridge_start.bat"
set "STARTUP_LNK=%STARTUP_DIR%\BiometricBridge Watchdog.lnk"
set "LAUNCHER=%~dp0launch_watchdog.vbs"

if not exist "%STARTUP_DIR%" (
  echo Startup folder not found:
  echo %STARTUP_DIR%
  pause
  exit /b 1
)

del "%STARTUP_BAT%" >nul 2>&1
del "%STARTUP_LNK%" >nul 2>&1

(
  echo Set shell = CreateObject^("WScript.Shell"^)
  echo shell.Run """" ^& "%~dp0watchdog_loop.bat" ^& """", 0, False
) > "%LAUNCHER%"

reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "BiometricBridgeWatchdog" /t REG_SZ /d "wscript.exe \"%LAUNCHER%\"" /f >nul

call "%~dp0start_watchdog_hidden.bat"

echo.
echo Biometric Bridge installed and started.
echo It will run from the current-user Run registry entry when you log in.
echo The hidden watchdog checks every 1 minute and starts the app if it is stopped.
echo.
echo Registry entry:
echo HKCU\Software\Microsoft\Windows\CurrentVersion\Run\BiometricBridgeWatchdog
pause
endlocal
