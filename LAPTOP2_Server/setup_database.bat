@echo off
REM ONE-TIME database setup. Start MySQL in XAMPP first, then double-click this file.
REM Safe to run again: it never deletes anything unless you run:  py setup_database.py --reset
cd /d "%~dp0"
py setup_database.py
echo.
pause
