<#
    Screenshot Bot -- full setup from a clean machine.

    Installs Python and Ollama if they are missing, downloads a vision model
    sized to this PC's GPU, builds the virtual environment, registers the
    background watcher, and verifies the whole thing end to end.

    Run:
        powershell -ExecutionPolicy Bypass -File ".\install.ps1"

    Options:
        -Engine ollama|cli|api   labeling backend (default: ollama)
        -Model  <name>           override the auto-selected Ollama model
        -SkipVerify              don't run the end-to-end test at the end
#>

param(
    [ValidateSet("ollama", "cli", "api")]
    [string]$Engine = "ollama",
    [string]$Model = "",
    [switch]$SkipVerify
)

$ErrorActionPreference = "Stop"
$toolDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Write-Step  ($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Write-Ok    ($m) { Write-Host "    $m" -ForegroundColor Green }
function Write-Note  ($m) { Write-Host "    $m" -ForegroundColor DarkGray }
function Write-Warn2 ($m) { Write-Host "    $m" -ForegroundColor Yellow }

function Find-Exe ($name, $extraPaths) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($p in $extraPaths) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

# --------------------------------------------------------------------------
Write-Host "`nScreenshot Bot -- setup" -ForegroundColor White
Write-Host "Names your screenshots automatically, on this PC." -ForegroundColor DarkGray

# --- 1. winget -------------------------------------------------------------
Write-Step "Checking prerequisites"
$winget = Get-Command winget -ErrorAction SilentlyContinue
if (-not $winget) {
    throw "winget is required but was not found. Install 'App Installer' from the Microsoft Store, then re-run."
}
Write-Ok "winget found"

# --- 2. Python -------------------------------------------------------------
$pythonPaths = @(
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
)
$python = Find-Exe "python" $pythonPaths
if (-not $python -or -not (& $python --version 2>$null)) {
    Write-Step "Installing Python"
    winget install --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements --silent | Out-Null
    $python = Find-Exe "python" $pythonPaths
    if (-not $python) {
        throw "Python installed but could not be located. Open a new terminal and re-run this script."
    }
}
Write-Ok "Python: $(& $python --version)"

# --- 3. Virtual environment ------------------------------------------------
Write-Step "Building the virtual environment"
$venvPython  = Join-Path $toolDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    & $python -m venv (Join-Path $toolDir ".venv")
}
& $venvPython -m pip install --quiet --upgrade pip
& $venvPython -m pip install --quiet anthropic pillow watchdog winsdk pytest
Write-Ok "Dependencies installed"

# --- 4. Ollama (only when that engine was chosen) ---------------------------
if ($Engine -eq "ollama") {
    Write-Step "Setting up the local vision model"

    $ollamaPaths = @(
        "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe",
        "$env:ProgramFiles\Ollama\ollama.exe"
    )
    $ollama = Find-Exe "ollama" $ollamaPaths
    if (-not $ollama) {
        Write-Note "Ollama not found -- installing (about 1 GB)..."
        winget install --id Ollama.Ollama --accept-source-agreements --accept-package-agreements --silent | Out-Null
        $ollama = Find-Exe "ollama" $ollamaPaths
        if (-not $ollama) {
            throw "Ollama installed but could not be located. Open a new terminal and re-run this script."
        }
    }
    Write-Ok "Ollama: $(& $ollama --version)"

    # Pick a model that fits this GPU. WMI's AdapterRAM caps at 4 GB and lies
    # about anything larger, so read the true size from the driver registry.
    if (-not $Model) {
        $vramGB = 0
        $keys = Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}\*" -ErrorAction SilentlyContinue |
                Where-Object { $_.'HardwareInformation.qwMemorySize' }
        foreach ($k in $keys) {
            $gb = [math]::Round($k.'HardwareInformation.qwMemorySize' / 1GB, 1)
            if ($gb -gt $vramGB) { $vramGB = $gb }
        }

        # Only ever auto-select a model that is licensed for commercial use.
        # qwen2.5vl:3b would fit smaller GPUs, but upstream it carries the Qwen
        # Research Licence (non-commercial only) -- despite Ollama shipping an
        # Apache 2.0 licence file with it. See NOTICE.md.
        $Model = "qwen2.5vl:7b"

        if ($vramGB -ge 8) {
            Write-Ok "Detected $vramGB GB VRAM -- selecting $Model"
        } elseif ($vramGB -gt 0) {
            Write-Warn2 "Detected $vramGB GB VRAM. Using $Model anyway; part of it will"
            Write-Warn2 "run on the CPU, so labeling will be slower."
        } else {
            Write-Warn2 "Could not detect a GPU. Using $Model on CPU -- expect it to be slow."
        }
    }

    $have = (& $ollama list) -join "`n"
    if ($have -match [regex]::Escape($Model)) {
        Write-Ok "Model $Model already present"
    } else {
        Write-Note "Downloading $Model -- this is several GB and may take a while..."
        & $ollama pull $Model
        if ($LASTEXITCODE -ne 0) { throw "Failed to download $Model." }
        Write-Ok "Model downloaded"
    }

    # The engine talks to the local HTTP service, so confirm it is answering.
    $ready = $false
    foreach ($attempt in 1..10) {
        try {
            Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null
            $ready = $true
            break
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    if ($ready) { Write-Ok "Ollama service responding" }
    else { Write-Warn2 "Ollama service is not responding yet; it usually starts on its own shortly." }
}

if ($Engine -eq "cli" -and -not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Warn2 "The 'claude' CLI was not found. Install Claude Code, or use -Engine ollama."
}
if ($Engine -eq "api" -and -not $env:ANTHROPIC_API_KEY) {
    Write-Warn2 "ANTHROPIC_API_KEY is not set. Set it with: setx ANTHROPIC_API_KEY `"sk-ant-...`""
}

# --- 5. Background watcher -------------------------------------------------
Write-Step "Registering the background watcher"
$installTask = Join-Path $toolDir "install-watcher-task.ps1"
if ($Model) { $env:SCREENSHOT_LABELER_MODEL = $Model }
& $installTask -Engine $Engine | Out-Null
Start-ScheduledTask -TaskName "Screenshot Labeler"
Write-Ok "Watcher registered and started"

# --- 6. End-to-end verification -------------------------------------------
if (-not $SkipVerify) {
    Write-Step "Verifying"
    $verify = Join-Path $toolDir "verify-install.py"
    if (Test-Path $verify) {
        & $venvPython $verify --engine $Engine
        if ($LASTEXITCODE -ne 0) {
            Write-Warn2 "Verification did not pass. See the message above."
        }
    } else {
        Write-Note "verify-install.py not found; skipping."
    }
}

# --------------------------------------------------------------------------
Write-Host "`nSetup complete." -ForegroundColor Green
Write-Host "Take a screenshot and it will be renamed within a few seconds." -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Label existing screenshots:  .venv\Scripts\python.exe -m screenshot_labeler --backfill --dry-run"
Write-Host "  Undo the last run:           .venv\Scripts\python.exe -m screenshot_labeler --undo"
Write-Host "  Stop the watcher:            Stop-ScheduledTask -TaskName `"Screenshot Labeler`""
Write-Host ""
