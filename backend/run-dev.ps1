# Start FastAPI with auto-reload (uses backend\.venv if present).
$ErrorActionPreference = "Stop"
$backendRoot = $PSScriptRoot
Set-Location $backendRoot
$env:PYTHONPATH = $backendRoot
$venvPy = Join-Path $backendRoot ".venv\Scripts\python.exe"
$py = if (Test-Path $venvPy) { $venvPy } else { "python" }
& $py -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 @args
