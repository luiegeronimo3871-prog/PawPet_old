@echo off
REM ONE-TIME setup of the Ionic app. Run from the PHONE_Mobile folder (needs Node.js).
REM Before running, edit src\app\config.ts -> http://<IP OF LAPTOP 2>:5000/api
cd /d "%~dp0"
call npm install -g @ionic/cli
call ionic start pawpet-app blank --type=angular --no-git --no-interactive
cd pawpet-app
call npm install zone.js
xcopy /E /Y /I "..\src" "src"
echo.
echo Done. Start the app with:  cd pawpet-app  then  ionic serve
pause
