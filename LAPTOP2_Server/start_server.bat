@echo off
REM Starts the PawPet server. Start MySQL (XAMPP) first, and run setup_database.bat once before the very first start.
cd /d "%~dp0"
title PawPet Server
py app.py
pause
