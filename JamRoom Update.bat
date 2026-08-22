@echo off
title Jam Room - update

rem Run from a COPY in %TEMP%. "git pull" updates this very file, and cmd reads
rem a running .bat from disk by byte offset, so replacing it mid-run makes cmd
rem skip lines and execute garbage (verified). Working from a copy means git can
rem rewrite the original safely.
if "%~1"=="" (
  if not exist "%TEMP%\jamroom_upd" mkdir "%TEMP%\jamroom_upd"
  copy /Y "%~f0" "%TEMP%\jamroom_upd\update.bat" >nul
  "%TEMP%\jamroom_upd\update.bat" "%~dp0."
  exit /b
)
cd /d "%~1"

for /f "delims=" %%i in ('git rev-parse HEAD 2^>nul') do set BEFORE=%%i
if "%BEFORE%"=="" (
  echo This folder is not a git clone, so it cannot update itself.
  echo Download a fresh ZIP from GitHub instead.
  echo.
  pause
  exit /b 1
)

echo Fetching the latest Jam Room version...
git pull
if errorlevel 1 (
  echo.
  echo UPDATE FAILED - see the message above. Nothing was changed, and your
  echo current setup still works. Common cause: a file here was edited by hand.
  echo.
  pause
  exit /b 1
)
for /f "delims=" %%i in ('git rev-parse HEAD') do set AFTER=%%i

set NEED_BROWSER=0
set NEED_REAPER=0
set NEED_IMPORTER=0

if "%BEFORE%"=="%AFTER%" goto :nochange

git diff --name-only %BEFORE% %AFTER% > "%TEMP%\jr_changed.txt"
echo.
echo Updated files:
type "%TEMP%\jr_changed.txt"

findstr /i /c:"ReaSet.html" /c:"Sortable.min.js" "%TEMP%\jr_changed.txt" >nul && set NEED_BROWSER=1
findstr /i /c:"Requirements/ReaSet_JamRoom.lua" /c:"Requirements/ReaSet_NativeLoop.lua" /c:"Requirements/X-Raym" /c:"Requirements/ReaSet_Startup.lua" "%TEMP%\jr_changed.txt" >nul && set NEED_REAPER=1
findstr /i /c:"tools/" "%TEMP%\jr_changed.txt" >nul && set NEED_IMPORTER=1

:nochange
echo.
echo Deploying ReaSet to REAPER's web interface...
call "%CD%\tools\deploy_reaset.bat"
echo.
echo Updating yt-dlp (YouTube changes break downloading every few weeks)...
yt-dlp -U
echo.
echo ============================================
if "%BEFORE%"=="%AFTER%" (
  echo  Already on the latest version.
  echo  Nothing changed, so nothing needs restarting.
  goto :done
)
echo  WHAT YOU NEED TO DO NOW:
echo.
if "%NEED_REAPER%"=="1" (
  echo   [ ] RESTART REAPER. Background scripts changed, and a running
  echo       script keeps using the old code until REAPER is restarted.
  echo       Save your project first. They restart themselves if you set
  echo       the startup action.
)
if "%NEED_IMPORTER%"=="1" (
  echo   [ ] RESTART THE IMPORTER. Close the "Jam Room Importer" window,
  echo       then double-click "JamRoom Importer.bat" again.
)
if "%NEED_BROWSER%"=="1" (
  echo   [ ] REFRESH REASET on the PC and on every tablet: Ctrl+F5
  echo       ^(a normal refresh may serve the old cached page^).
)
if "%NEED_REAPER%%NEED_IMPORTER%%NEED_BROWSER%"=="000" (
  echo   Nothing - the changes were docs or notes only.
)
:done
echo.
echo  Nothing was deleted. Your Fadr key, downloaded songs in imports\,
echo  your REAPER project and your setlists are all untouched.
echo ============================================
echo.
pause
