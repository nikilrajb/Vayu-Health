@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0backend"
echo Create a local account. Password input is hidden.
set /p "VAYU_USERNAME=Username:nikhil "
set /p "VAYU_ROLE=Role (operator or reviewer):operator "
".venv\Scripts\python.exe" -m app.auth "%VAYU_USERNAME%" --role "%VAYU_ROLE%"
pause
