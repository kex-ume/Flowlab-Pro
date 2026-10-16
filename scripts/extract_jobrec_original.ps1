$ErrorActionPreference = "Stop"

$sourceArchive = "C:\Users\Administrator\AppData\Local\Packages\5319275A.WhatsAppDesktop_cv1g1gvanyjgm\LocalState\sessions\29705637083AEF82BE54547D8723E7E27D10680E\transfers\2026-40\JobRec-deploy.zip"
$destination = "C:\Users\Administrator\Projects\FlowLab-Pro-1\jobrec-original"

if (-not (Test-Path -LiteralPath $destination)) {
    Expand-Archive -LiteralPath $sourceArchive -DestinationPath $destination
}

Write-Output $destination
