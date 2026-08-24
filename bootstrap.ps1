<#
    Screenshot Bot -- one-line installer.

    Downloads the project and runs the full setup (Python, Ollama, model,
    background watcher). Intended to be piped straight from GitHub:

        irm https://raw.githubusercontent.com/HorseyConsulting/screenshot-labeler/main/bootstrap.ps1 | iex

    NOTE: while the repository is private, that URL will 404 for everyone.
    Either flip the repo public, or clone it with an authenticated client:

        gh repo clone HorseyConsulting/screenshot-labeler
        cd screenshot-labeler
        powershell -ExecutionPolicy Bypass -File .\install.ps1

    Options (when run as a file rather than piped):
        -InstallDir <path>   where to put it (default: %LOCALAPPDATA%\ScreenshotBot)
        -Branch <name>       which branch to fetch (default: main)
#>

param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA "ScreenshotBot"),
    [string]$Branch = "main",
    [string]$Repo = "HorseyConsulting/screenshot-labeler"
)

$ErrorActionPreference = "Stop"

Write-Host "`nScreenshot Bot -- downloading" -ForegroundColor White

$zipUrl  = "https://github.com/$Repo/archive/refs/heads/$Branch.zip"
$tempZip = Join-Path $env:TEMP "screenshot-labeler-$Branch.zip"
$tempDir = Join-Path $env:TEMP "screenshot-labeler-extract"

try {
    Invoke-WebRequest -Uri $zipUrl -OutFile $tempZip -UseBasicParsing
} catch {
    Write-Host "`nCould not download from $zipUrl" -ForegroundColor Red
    Write-Host "If the repository is private, clone it with 'gh repo clone $Repo' instead." -ForegroundColor Yellow
    exit 1
}

if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
Expand-Archive -Path $tempZip -DestinationPath $tempDir -Force

# GitHub wraps the archive in a "<repo>-<branch>" folder.
$extracted = Get-ChildItem $tempDir -Directory | Select-Object -First 1

if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

# Copy source only -- never clobber an existing venv or rename log.
Get-ChildItem $extracted.FullName -Exclude ".venv", "rename-log.jsonl" | ForEach-Object {
    Copy-Item $_.FullName -Destination $InstallDir -Recurse -Force
}

Remove-Item $tempZip -Force -ErrorAction SilentlyContinue
Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Installed to $InstallDir" -ForegroundColor Green

& (Join-Path $InstallDir "install.ps1")
