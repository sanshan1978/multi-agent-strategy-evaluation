param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$Reload
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$ArgsList = @(
    "-m", "uvicorn",
    "api_fastapi:app",
    "--host", $HostAddress,
    "--port", "$Port"
)

if ($Reload) {
    $ArgsList += "--reload"
}

Write-Host "Starting service at http://$HostAddress`:$Port/"
python @ArgsList
