@echo off
REM Sends appointment reminders (today + tomorrow). Used by Task Scheduler; the server must be running.
cd /d "%~dp0"
py send_reminders.py
