@echo off
setlocal
cd /d "%~dp0"
title Vayu Backend - port 8002
if not exist ".venv\Scripts\python.exe" (
  echo Missing Python environment. Follow RUN_GUIDE.md setup first.
  pause
  exit /b 1
)
echo Backend: http://127.0.0.1:8002
echo API documentation: http://127.0.0.1:8002/docs
echo Keep this window open. Press Ctrl+C to stop.
".venv\Scripts\python.exe" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8002 --reload --reload-dir backend/app
pause
