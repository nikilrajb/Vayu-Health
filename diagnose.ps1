$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) { throw 'Create the Python environment first; see RUN_GUIDE.md.' }
$env:PYTHONPATH = Join-Path $PSScriptRoot 'backend'
& '.venv/Scripts/python.exe' -m app.diagnostics
exit $LASTEXITCODE
