@echo off
REM Run ONCE as Administrator (right-click > Run as administrator) on LAPTOP 2.
REM Creates 2 scheduled tasks:
REM   PawPet Server    - starts the server when you log in
REM   PawPet Reminders - sends appointment reminders every day at 07:00
set "DIR=%~dp0"
schtasks /Create /F /TN "PawPet Server" /TR "\"%DIR%start_server.bat\"" /SC ONLOGON /DELAY 0001:00
schtasks /Create /F /TN "PawPet Reminders" /TR "\"%DIR%send_reminders.bat\"" /SC DAILY /ST 07:00
echo.
echo Done. Open "Task Scheduler" to check them. Test now:  schtasks /Run /TN "PawPet Reminders"
echo To remove:  schtasks /Delete /F /TN "PawPet Server"  and  schtasks /Delete /F /TN "PawPet Reminders"
pause
