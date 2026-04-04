# Apply Alembic migrations (uses backend\.venv Python if present).
# Requires a filled .env at repo root or in this folder (see app.core.config).
$ErrorActionPreference = "Stop"
$backendRoot = $PSScriptRoot
Set-Location $backendRoot
$env:PYTHONPATH = $backendRoot
$venvPy = Join-Path $backendRoot ".venv\Scripts\python.exe"
$py = if (Test-Path $venvPy) { $venvPy } else { "python" }
& $py -m alembic upgrade head @args
