@echo off
REM Opens TCP port 5000 in Windows Firewall so the other laptop and the phone can reach the server.
REM RIGHT-CLICK this file -> "Run as administrator".
net session >nul 2>&1
if errorlevel 1 (
  echo This must be run as Administrator: right-click the file and choose "Run as administrator".
  pause
  exit /b 1
)
netsh advfirewall firewall delete rule name="PawPet 5000" >nul 2>&1
netsh advfirewall firewall add rule name="PawPet 5000" dir=in action=allow protocol=TCP localport=5000 profile=any
echo.
echo Done. Port 5000 is open. This laptop's addresses (use the one starting with the same numbers as the other device):
ipconfig | findstr /i "IPv4"
echo.
pause
