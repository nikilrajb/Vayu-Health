@echo off
setlocal
cd /d "%~dp0"
echo Starting Vayu backend and frontend in separate windows.
echo Once both are ready, open http://127.0.0.1:5173
echo Do not run this launcher twice. Close the server windows before restarting.
start "Vayu Backend" cmd.exe /c call "%~dp0run-backend.cmd"
start "Vayu Frontend" cmd.exe /c call "%~dp0run-frontend.cmd"
