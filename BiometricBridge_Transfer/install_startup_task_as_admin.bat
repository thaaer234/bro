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

(
  echo @echo off
  echo call "%~dp0start_watchdog_hidden.bat"
) > "%STARTUP_BAT%"

(
  echo Set shell = CreateObject^("WScript.Shell"^)
  echo shell.Run """" ^& "%~dp0watchdog_loop.bat" ^& """", 0, False
) > "%LAUNCHER%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%STARTUP_LNK%'); $s.TargetPath='wscript.exe'; $s.Arguments='\"%LAUNCHER%\"'; $s.WorkingDirectory='%~dp0'; $s.WindowStyle=7; $s.Save()"

reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "BiometricBridgeWatchdog" /t REG_SZ /d "wscript.exe \"%LAUNCHER%\"" /f >nul

call "%~dp0start_watchdog_hidden.bat"

echo.
echo Biometric Bridge installed and started.
echo It will run from the Windows Startup folder when you log in.
echo It also added a current-user Run registry entry as a fallback.
echo The hidden watchdog checks every 1 minute and starts the app if it is stopped.
echo.
echo Startup files:
echo %STARTUP_BAT%
echo %STARTUP_LNK%
echo.
echo Registry entry:
echo HKCU\Software\Microsoft\Windows\CurrentVersion\Run\BiometricBridgeWatchdog
pause
endlocal
