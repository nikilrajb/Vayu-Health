@echo off
setlocal
cd /d "%~dp0"
title Vayu Frontend - port 5173
if not exist "frontend\node_modules" (
  echo Missing frontend dependencies. Run npm --prefix frontend ci first.
  pause
  exit /b 1
)
set "VAYU_API_TARGET=http://127.0.0.1:8002"
echo Website: http://127.0.0.1:5173
echo Keep this window open. Press Ctrl+C to stop.
call npm.cmd --prefix frontend run dev -- --host 127.0.0.1 --port 5173
pause
