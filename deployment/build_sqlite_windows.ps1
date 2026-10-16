param([string]$ReleaseDirectory = "release\EATL-SQLite-SingleFile-20261015", [string]$SnapshotDirectory = "release\SQLite-Snapshot-20261015")
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$releaseRoot = Join-Path $projectRoot $ReleaseDirectory
$snapshotRoot = (Resolve-Path -LiteralPath $SnapshotDirectory).Path
$verification = Get-Content -LiteralPath (Join-Path $snapshotRoot 'migration-verification.json') -Raw | ConvertFrom-Json
if ($verification.status -ne 'verified') { throw 'Snapshot must be verified before packaging.' }
if (Test-Path -LiteralPath $releaseRoot) { throw 'Choose a new ReleaseDirectory; existing releases will not be overwritten.' }
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$eiRoot = Join-Path $projectRoot 'jobrec-review'
$djangoSite = Join-Path $eiRoot '.venv-jobrec\Lib\site-packages'
$workRoot = Join-Path $projectRoot 'build\pyinstaller-sqlite-single'
New-Item -ItemType Directory -Force -Path $releaseRoot,$workRoot | Out-Null
& $python -m PyInstaller --noconfirm --onefile --noconsole --noupx `
    --name EATL-Integrated-Lab --distpath $releaseRoot --workpath $workRoot --specpath $workRoot `
    --paths $projectRoot --paths $eiRoot --paths $djangoSite `
    --collect-all django --collect-all rest_framework --collect-all django_filters `
    --collect-all openpyxl --collect-all reportlab --collect-submodules core `
    --hidden-import qrcode --hidden-import requests --hidden-import jobrec.settings `
    --hidden-import jobrec.urls --hidden-import jobrec.wsgi `
    --add-data "$(Join-Path $projectRoot 'templates');templates" `
    --add-data "$(Join-Path $projectRoot 'static');static" `
    --add-data "$(Join-Path $projectRoot 'scripts\populate_report_cover.ps1');scripts" `
    --add-data "$(Join-Path $eiRoot 'core');jobrec-review\core" `
    --add-data "$(Join-Path $djangoSite 'rest_framework');rest_framework" `
    --add-data "$(Join-Path $djangoSite 'django_filters');django_filters" `
    --add-data "$(Join-Path $snapshotRoot 'data');seed-data" `
    (Join-Path $projectRoot 'deployment\flowlab_launcher.py')
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README-SQLite.txt') -Destination (Join-Path $releaseRoot 'README.txt')
Copy-Item -LiteralPath (Join-Path $snapshotRoot 'migration-verification.json') -Destination $releaseRoot
Copy-Item -LiteralPath (Join-Path $projectRoot 'docs\EI-workflow-audit-20261016.md') -Destination (Join-Path $releaseRoot 'Workflow-Review.md')
Compress-Archive -Path (Join-Path $releaseRoot 'EATL-Integrated-Lab.exe'),(Join-Path $releaseRoot 'README.txt'),(Join-Path $releaseRoot 'migration-verification.json'),(Join-Path $releaseRoot 'Workflow-Review.md') -DestinationPath (Join-Path $releaseRoot 'EATL-SQLite-Windows.zip')
Write-Output "Private SQLite executable: $releaseRoot"
