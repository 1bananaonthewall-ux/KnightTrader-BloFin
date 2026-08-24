<#
.SYNOPSIS
Starts the Emirald dashboard and opens it in the default browser.
#>
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = 'python' }

$port = 8766
$proc = Get-Process -Name python* -ErrorAction SilentlyContinue | Where-Object {
  try { $_.CommandLine -match 'apps\.dashboard\.main:app|uvicorn apps\.dashboard\.main' } catch { $false }
}
if (-not $proc) {
  Start-Process -FilePath $python -ArgumentList "-m","uvicorn","apps.dashboard.main:app","--host","127.0.0.1","--port","$port" -WorkingDirectory $root -WindowStyle Hidden | Out-Null
  Start-Sleep -Milliseconds 800
}

Start-Process "http://127.0.0.1:$port/"
