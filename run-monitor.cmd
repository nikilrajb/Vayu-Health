@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0backend"
echo Monitoring all configured locations. Each sweep is followed by a one-hour pause.
echo Results and alerts are saved locally; no email or SMS is sent.
".venv\Scripts\python.exe" -m app.monitor --cities all --interval 3600
pause
