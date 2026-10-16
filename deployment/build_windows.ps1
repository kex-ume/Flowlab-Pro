param([string]$ReleaseDirectory = "release\EATL-SQLite-Windows-20261015", [string]$SnapshotDirectory = "")
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$releaseRoot = Join-Path $projectRoot $ReleaseDirectory
$workRoot = Join-Path $projectRoot "build\pyinstaller-integrated"
$flowPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$djangoSite = Join-Path $projectRoot "jobrec-review\.venv-jobrec\Lib\site-packages"
$eiRoot = Join-Path $projectRoot "jobrec-review"

if (Test-Path -LiteralPath (Join-Path $releaseRoot "EATL-Integrated-Lab")) {
    throw "Release folder already exists. Choose a new ReleaseDirectory; existing installations and their data will not be overwritten."
}
New-Item -ItemType Directory -Force -Path $releaseRoot, $workRoot | Out-Null

& $flowPython -m PyInstaller --noconfirm --onedir --noconsole `
    --name EATL-Integrated-Lab `
    --distpath $releaseRoot `
    --workpath $workRoot `
    --specpath $workRoot `
    --paths $projectRoot `
    --paths $eiRoot `
    --paths $djangoSite `
    --collect-all django `
    --collect-all rest_framework `
    --collect-all django_filters `
    --collect-all openpyxl `
    --collect-all reportlab `
    --collect-submodules core `
    --collect-all psycopg `
    --collect-all psycopg_binary `
    --hidden-import rest_framework `
    --hidden-import rest_framework.authtoken `
    --hidden-import django_filters `
    --hidden-import qrcode `
    --hidden-import requests `
    --hidden-import jobrec.settings `
    --hidden-import jobrec.urls `
    --hidden-import jobrec.wsgi `
    --add-data "$(Join-Path $projectRoot 'templates');templates" `
    --add-data "$(Join-Path $projectRoot 'static');static" `
    --add-data "$(Join-Path $projectRoot 'scripts\populate_report_cover.ps1');scripts" `
    --add-data "$(Join-Path $eiRoot 'core');jobrec-review\core" `
    --add-data "$(Join-Path $djangoSite 'rest_framework');rest_framework" `
    --add-data "$(Join-Path $djangoSite 'django_filters');django_filters" `
    (Join-Path $projectRoot "deployment\flowlab_launcher.py")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE." }

$bundle = Join-Path $releaseRoot "EATL-Integrated-Lab"
$dataRoot = Join-Path $bundle "data"
New-Item -ItemType Directory -Force -Path (Join-Path $dataRoot "shared_files") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $dataRoot "private") | Out-Null
if ($SnapshotDirectory) {
    $snapshotRoot = (Resolve-Path -LiteralPath $SnapshotDirectory).Path
    $verification = Get-Content -LiteralPath (Join-Path $snapshotRoot 'migration-verification.json') -Raw | ConvertFrom-Json
    if ($verification.status -ne 'verified') { throw 'The database snapshot has not passed verification.' }
    Copy-Item -Path (Join-Path $snapshotRoot 'data\*') -Destination $dataRoot -Recurse
    Copy-Item -LiteralPath (Join-Path $snapshotRoot 'migration-verification.json') -Destination $bundle
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "configuration.env.example") -Destination $bundle
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "README-Windows.txt") -Destination (Join-Path $bundle "README.txt")
New-Item -ItemType Directory -Force -Path (Join-Path $bundle "_internal\scripts") | Out-Null
Copy-Item -LiteralPath (Join-Path $projectRoot "scripts\populate_report_cover.ps1") -Destination (Join-Path $bundle "_internal\scripts")

$zipPath = Join-Path $releaseRoot "EATL-Integrated-Lab-Windows.zip"
if (Test-Path $zipPath) { throw "Deployment ZIP already exists. Choose a new ReleaseDirectory to preserve earlier builds." }
Compress-Archive -Path $bundle -DestinationPath $zipPath -CompressionLevel Optimal

Write-Output "Integrated application: $bundle"
Write-Output "Deployment ZIP: $zipPath"
