# Start BOTH FlowLab Pro and E&I Lab on one port. Do not use web_app:app.
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Python environment is missing. For standalone deployment, use EATL-Integrated-Lab.exe.' }
Set-Location -LiteralPath $projectRoot
& $pythonPath (Join-Path $projectRoot 'scripts\run_integrated_server.py')
