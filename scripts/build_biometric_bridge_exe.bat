@echo off
setlocal

cd /d %~dp0\..

python -m pip install pyinstaller pyzk
python -m PyInstaller --noconfirm --onefile --name biometric_bridge --noconsole scripts\biometric_bridge.py

echo.
echo Build finished.
echo EXE path:
echo %CD%\dist\biometric_bridge.exe
endlocal
