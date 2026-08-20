<#
.SYNOPSIS
Creates Hermes Dashboard, Hermes Trader (launcher), and Stop Hermes shortcuts
on the OneDrive desktop.
#>
Param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$desktop = 'C:\Users\mknig\OneDrive\Desktop'
if (-not (Test-Path -LiteralPath $desktop)) {
    $desktop = [Environment]::GetFolderPath('Desktop')
}

$scripts = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $scripts
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = 'python' }

$shell = New-Object -ComObject WScript.Shell

function New-HermesShortcut {
    param(
        [string]$Name,
        [string]$Arguments,
        [string]$Icon,
        [int]$WindowStyle = 1
    )
    $path = Join-Path $desktop ($Name + '.lnk')
    $s = $shell.CreateShortcut($path)
    $s.TargetPath = 'powershell.exe'
    $s.Arguments = $Arguments
    $s.WorkingDirectory = $root
    $s.WindowStyle = $WindowStyle
    $s.IconLocation = $Icon
    $s.Description = $Name
    $s.Save()
    Write-Host "Wrote $path"
}

$dashFile = Join-Path $scripts 'start_dashboard.ps1'
New-HermesShortcut -Name 'Hermes Dashboard' `
    -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$dashFile`"" `
    -Icon 'shell32.dll,21' `
    -WindowStyle 7

# Visible launcher window (python.exe, NOT pythonw / NOT Hidden)
$agentCmd = "& { Set-Location -LiteralPath '$root'; & '$python' '$scripts\launch_hermes_gui.py' '--working-dir' '$root' }"
New-HermesShortcut -Name 'Hermes Trader' `
    -Arguments "-NoProfile -ExecutionPolicy Bypass -Command `"$agentCmd`"" `
    -Icon 'shell32.dll,14' `
    -WindowStyle 1

$stopCmd = "& { Set-Location -LiteralPath '$root'; & '$python' '$scripts\stop_hermes.py' '$root' }"
New-HermesShortcut -Name 'Stop Hermes' `
    -Arguments "-NoProfile -ExecutionPolicy Bypass -Command `"$stopCmd`"" `
    -Icon 'shell32.dll,27' `
    -WindowStyle 1

Write-Host "Desktop shortcuts created in $desktop."
