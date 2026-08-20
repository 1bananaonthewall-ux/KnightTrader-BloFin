@echo off
setlocal EnableExtensions
title KnightTrader Launcher

cd /d "%~dp0KnightTrader"
if errorlevel 1 (
  echo ERROR: KnightTrader folder not found next to this launcher.
  pause
  exit /b 1
)

set "ELECTRON=node_modules\electron\dist\electron.exe"
if exist "%ELECTRON%" (
  start "" "%ELECTRON%" .
  exit /b 0
)

where npm >nul 2>&1
if errorlevel 1 (
  echo ERROR: Electron not found and npm is not on PATH.
  echo Install Node.js from https://nodejs.org then run: npm install
  pause
  exit /b 1
)

echo Starting via npm...
start "" cmd /c "npm start"
exit /b 0
