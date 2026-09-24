param([int]$Port = 8000, [switch]$Setup)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if ($Setup) {
    if (-not (Test-Path '.venv/Scripts/python.exe')) { python -m venv .venv }
    & '.venv/Scripts/python.exe' -m pip install -r backend/requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed' }
    npm.cmd --prefix frontend ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed' }
}
if (-not (Test-Path '.venv/Scripts/python.exe')) { throw 'Run ./start.ps1 -Setup first.' }
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }
npm.cmd --prefix frontend run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
Write-Host "Vayu Health: http://localhost:$Port   API docs: http://localhost:$Port/docs"
& '.venv/Scripts/python.exe' -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port $Port
