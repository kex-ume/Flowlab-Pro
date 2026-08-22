param(
    [Parameter(Mandatory = $true)][int[]]$ProcessIds,
    [int]$LifetimeSeconds = 86400
)

Start-Sleep -Seconds $LifetimeSeconds
foreach ($ProcessId in $ProcessIds) {
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}
