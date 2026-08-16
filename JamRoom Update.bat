@echo off
title Jam Room - update from GitHub
cd /d "%~dp0"
echo Fetching the latest Jam Room version...
git pull
if errorlevel 1 (
  echo.
  echo Update FAILED - see the message above. Nothing was changed.
  pause
  exit /b 1
)
echo.
echo Deploying ReaSet to REAPER's web interface...
if not exist "%APPDATA%\REAPER\reaper_www_root" mkdir "%APPDATA%\REAPER\reaper_www_root"
copy /Y ReaSet.html "%APPDATA%\REAPER\reaper_www_root\ReaSet.html" >nul
copy /Y Sortable.min.js "%APPDATA%\REAPER\reaper_www_root\Sortable.min.js" >nul
echo.
echo ============================================
echo  Up to date. Reload ReaSet in the browser
echo  (Ctrl+F5) to pick up the new version.
echo ============================================
pause
