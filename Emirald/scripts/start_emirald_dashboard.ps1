Param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$desktop = Join-Path $env:USERPROFILE 'OneDrive\Desktop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$pythonw = Join-Path $root '.venv\Scripts\pythonw.exe'
if(-not (Test-Path $pythonw)){ $pythonw = 'python' }
$cmd = "@`"$pythonw`" `"$root\scripts\launch_emirald_gui.py`"`""
if(-not (Test-Path $desktop)){ $desktop = [Environment]::GetFolderPath('Desktop') }
$lnk = Join-Path $desktop 'Emirald Trader.lnk'
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$shortcut.TargetPath = 'powershell'
$shortcut.Arguments = "-NoProfile -WindowStyle Hidden -Command $cmd"
$shortcut.WorkingDirectory = $root
$shortcut.WindowStyle = 7
$shortcut.IconLocation = 'shell32.dll,14'
$shortcut.Save()
$lnk2 = Join-Path $desktop 'Emirald Dashboard.lnk'
$shortcut2 = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk2)
$shortcut2.TargetPath = 'powershell'
$shortcut2.Arguments = "-NoProfile -Command `"& '$root\Scripts\start_dashboard.ps1'`""
$shortcut2.WorkingDirectory = $root
$shortcut2.WindowStyle = 7
$shortcut2.IconLocation = 'shell32.dll,21'
$shortcut2.Save()
$lnk3 = Join-Path $desktop 'Stop Emirald.lnk'
$shortcut3 = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk3)
$shortcut3.TargetPath = 'powershell'
$shortcut3.Arguments = "-NoProfile -Command `"& '$root\Scripts\stop_emirald_gui.ps1'`""
$shortcut3.WorkingDirectory = $root
$shortcut3.WindowStyle = 7
$shortcut3.IconLocation = 'shell32.dll,27'
$shortcut3.Save()
