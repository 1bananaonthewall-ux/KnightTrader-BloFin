<#
.SYNOPSIS
Launches the Hermes stopper prompt.
#>
Param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$python = Join-Path $root '.venv\Scripts\python.exe'
if(-not (Test-Path $python)){ $python = 'python' }
$script = Join-Path $root 'scripts/stop_hermes.py'
Start-Process -FilePath 'powershell' -ArgumentList @('-NoProfile','-WindowStyle','Hidden','-Command',"& '$python' '$script'") -WorkingDirectory $root
