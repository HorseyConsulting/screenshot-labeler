<#
    Registers the screenshot labeler as a Windows Scheduled Task that starts at
    logon and runs invisibly (pythonw.exe = no console window).

    Run once, from an ordinary PowerShell prompt:
        powershell -ExecutionPolicy Bypass -File ".\install-watcher-task.ps1"

    Remove it later with:
        Unregister-ScheduledTask -TaskName "Screenshot Labeler" -Confirm:$false
#>

param(
    # ollama = a vision model on your own GPU (fast, free, fully offline)
    # api    = metered Anthropic API key
    [ValidateSet("ollama", "api")]
    [string]$Engine = "ollama"
)

$ErrorActionPreference = "Stop"

$toolDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw    = Join-Path $toolDir ".venv\Scripts\pythonw.exe"
# OneDrive redirects the Pictures library on some machines and not others,
# so detect rather than assume. Created if absent -- Windows makes it on the
# first Win+PrtScn, and the watcher needs it to exist to watch it.
$oneDriveShots = Join-Path $env:USERPROFILE "OneDrive\Pictures\Screenshots"
$plainShots    = Join-Path $env:USERPROFILE "Pictures\Screenshots"
if (Test-Path $oneDriveShots) { $watchDir = $oneDriveShots } else { $watchDir = $plainShots }
if (-not (Test-Path $watchDir)) {
    New-Item -ItemType Directory -Path $watchDir -Force | Out-Null
    Write-Host "Created $watchDir"
}
$taskName   = "Screenshot Labeler"

if (-not (Test-Path $pythonw)) {
    throw "Virtual environment not found at $pythonw. Create it first with: python -m venv .venv"
}

# Check that whichever engine was chosen can actually work on this machine.
switch ($Engine) {
    "ollama" {
        # The engine talks to the local HTTP service, so reachability is what
        # matters here -- not whether ollama.exe happens to be on PATH.
        try {
            Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5 | Out-Null
        } catch {
            Write-Warning "Ollama is not responding on http://127.0.0.1:11434."
            Write-Warning "Install it from https://ollama.com, then run: ollama pull qwen2.5vl:7b"
        }
    }
    "api" {
        if (-not $env:ANTHROPIC_API_KEY) {
            Write-Warning "ANTHROPIC_API_KEY is not set. Set it with: setx ANTHROPIC_API_KEY \"sk-ant-...\""
        }
    }
}

$action = New-ScheduledTaskAction `
    -Execute $pythonw `
    -Argument "-m screenshot_labeler --watch --engine $Engine --dir `"$watchDir`"" `
    -WorkingDirectory $toolDir

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

# Stop any watcher already running, so re-installing replaces it rather than
# leaving a second copy racing the first over the same folder.
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
}
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*screenshot_labeler --watch*" } |
    ForEach-Object {
        Write-Host "Stopping previous watcher (PID $($_.ProcessId))."
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

# Restart on failure, never time out, and never run two copies at once.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0)

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Renames new screenshots from timestamps to descriptive labels." `
    -Force | Out-Null

Write-Host "Registered scheduled task '$taskName'." -ForegroundColor Green
Write-Host "Watching: $watchDir"
Write-Host "Engine:   $Engine"
Write-Host ""
Write-Host "Start it now without logging out:"
Write-Host "    Start-ScheduledTask -TaskName `"$taskName`""
