@echo off
REM Set a new password for any account (e.g. admin) when you do not know the current one. MySQL must be running.
cd /d "%~dp0"
py reset_password.py
pause
