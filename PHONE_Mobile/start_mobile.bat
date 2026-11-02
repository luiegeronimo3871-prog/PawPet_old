@echo off
REM Run inside your pawpet-app folder after copying src. Starts the Ionic app.
cd /d "%~dp0"
call ionic serve
pause
