@echo off
REM Finds out why the desktop app cannot reach the server.
cd /d "%~dp0"
py check_connection.py
