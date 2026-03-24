@echo off
setlocal
color 0E
title Jo-L Captions Engine Core

echo ===================================================
echo   [!] IGNITING ARTIFICIAL INTELLIGENCE ENGINES...
echo ===================================================
echo.
echo Starting backend servers, Redis, and Audio Processors...
docker compose up -d

echo.
echo ===================================================
echo   [+] ENGINES ONLINE. LAUNCHING STUDIO INTERFACE!
echo ===================================================
timeout /t 3 /nobreak > NUL

:: Launch the App Interface
start msedge --app="http://localhost:3000" 2>NUL || start chrome --app="http://localhost:3000" 2>NUL || start http://localhost:3000

echo.
echo ---------------------------------------------------
echo.
echo   SOFTWARE IS RUNNING! 
echo   DO NOT CLOSE THIS WINDOW UNTIL YOU ARE FINISHED.
echo.
echo ---------------------------------------------------
echo.
echo When you are done using Jo-L Captions, 
echo press ANY KEY in this window to safely shut down.
echo.
pause

echo.
echo ===================================================
echo   [-] POWERING DOWN ALL ENGINES...
echo ===================================================
docker compose down

echo.
echo Shut down complete. PC RAM freed successfully.
timeout /t 3 > NUL
exit
