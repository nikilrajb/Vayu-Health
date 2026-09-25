@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Missing Python environment. Follow RUN_GUIDE.md setup first.
  pause
  exit /b 1
)
set "PYTHONPATH=%~dp0backend"
echo Checking OpenAQ and weather directly from your computer.
echo This can take about a minute. Your API key will not be printed.
".venv\Scripts\python.exe" -m app.diagnostics
echo.
echo Copy the report above into the chat. Do not send your .env file or API key.
pause
