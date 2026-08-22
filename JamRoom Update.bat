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
call "%~dp0tools\deploy_reaset.bat"
echo.
echo Updating yt-dlp (YouTube changes break downloading every few weeks)...
yt-dlp -U
echo.
echo ============================================
echo  Up to date. Reload ReaSet in the browser
echo  (Ctrl+F5) to pick up the new version.
echo ============================================
pause
