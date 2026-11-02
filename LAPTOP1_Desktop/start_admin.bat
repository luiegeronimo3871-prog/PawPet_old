@echo off
REM Starts the PawPet desktop admin app. Server URL on the login screen: http://<IP OF LAPTOP 2>:5000
cd /d "%~dp0"
py admin.py
pause
