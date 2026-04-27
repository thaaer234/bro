@echo off
cd /d %~dp0
echo Testing biometric bridge connections...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$cfg = Get-Content -Raw 'biometric_bridge_config.json' | ConvertFrom-Json; " ^
  "Write-Host 'Device:' $cfg.device_ip':'$cfg.device_port; " ^
  "$device = Test-NetConnection -ComputerName $cfg.device_ip -Port $cfg.device_port -WarningAction SilentlyContinue; " ^
  "if ($device.TcpTestSucceeded) { Write-Host 'DEVICE OK: laptop can reach biometric device.' -ForegroundColor Green } else { Write-Host 'DEVICE FAILED: laptop cannot reach biometric device IP/port.' -ForegroundColor Red }; " ^
  "Write-Host ''; " ^
  "$uri = [Uri]$cfg.server_url; " ^
  "Write-Host 'Server:' $uri.Host':443'; " ^
  "$server = Test-NetConnection -ComputerName $uri.Host -Port 443 -WarningAction SilentlyContinue; " ^
  "if ($server.TcpTestSucceeded) { Write-Host 'SERVER PORT OK: laptop can reach HTTPS server.' -ForegroundColor Green } else { Write-Host 'SERVER FAILED: laptop cannot reach HTTPS server.' -ForegroundColor Red }; " ^
  "Write-Host ''; " ^
  "try { $r = Invoke-WebRequest -Uri $cfg.server_url -Method Head -TimeoutSec 20 -UseBasicParsing; Write-Host 'HTTP OK:' $r.StatusCode -ForegroundColor Green } catch { Write-Host 'HTTP CHECK:' $_.Exception.Message -ForegroundColor Yellow }"

echo.
echo Done.
pause
