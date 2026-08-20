Param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "Hermes venv python missing at $python"
}

# Dedicated Hermes port — do NOT share 8765 with LLM KnightTrader.
$Port = 8766
$Url = "http://127.0.0.1:$Port/"

function Test-HermesDashboard {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -lt 200 -or $r.StatusCode -ge 500) { return $false }
        $body = [string]$r.Content
        # Must be THIS project, not KnightTrader on a colliding port.
        return ($body -match 'Hermes Trader' -and $body -notmatch 'KnightTrader')
    } catch {
        return $false
    }
}

if (-not (Test-HermesDashboard)) {
    # Kill only a listener on Hermes' dedicated port if it's the wrong app.
    try {
        $owners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($ownerPid in $owners) {
            if ($ownerPid -and $ownerPid -gt 4) {
                Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue
            }
        }
    } catch { }

    $log = Join-Path $root 'data\dashboard_stdout.log'
    $err = Join-Path $root 'data\dashboard_stderr.log'
    New-Item -ItemType Directory -Force -Path (Join-Path $root 'data') | Out-Null
    $proc = Start-Process -FilePath $python -ArgumentList @(
        '-m', 'uvicorn', 'apps.dashboard.main:app',
        '--port', "$Port", '--host', '127.0.0.1'
    ) -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError $err

    $deadline = (Get-Date).AddSeconds(25)
    do {
        Start-Sleep -Milliseconds 400
        if (Test-HermesDashboard) { break }
        if ($proc.HasExited) { break }
    } while ((Get-Date) -lt $deadline)
}

if (-not (Test-HermesDashboard)) {
    $hint = ''
    $errPath = Join-Path $root 'data\dashboard_stderr.log'
    if (Test-Path -LiteralPath $errPath) {
        $hint = (Get-Content -LiteralPath $errPath -Raw -ErrorAction SilentlyContinue)
    }
    throw "Hermes Trader dashboard failed to start on $Url. $hint"
}

Start-Process $Url
