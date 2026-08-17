@echo off
rem Copy ReaSet.html + Sortable.min.js into REAPER's web root.
rem REAPER's web root location varies by install, so update every candidate
rem that exists (harmless if both do) and only create one as a last resort.
set REPO=%~dp0..
set DEPLOYED=0
for %%D in ("%APPDATA%\REAPER\reaper_www_root" "%APPDATA%\REAPER\Plugins\reaper_www_root") do (
  if exist "%%~D" (
    copy /Y "%REPO%\ReaSet.html" "%%~D\ReaSet.html" >nul
    copy /Y "%REPO%\Sortable.min.js" "%%~D\Sortable.min.js" >nul
    echo   updated %%~D
    set DEPLOYED=1
  )
)
if "%DEPLOYED%"=="0" (
  mkdir "%APPDATA%\REAPER\reaper_www_root" 2>nul
  copy /Y "%REPO%\ReaSet.html" "%APPDATA%\REAPER\reaper_www_root\ReaSet.html" >nul
  copy /Y "%REPO%\Sortable.min.js" "%APPDATA%\REAPER\reaper_www_root\Sortable.min.js" >nul
  echo   created %APPDATA%\REAPER\reaper_www_root and copied files there
  echo   NOTE: if ReaSet already worked from a different folder, check
  echo         REAPER: Options - Preferences - Control/OSC/web for the web root
  echo         and copy ReaSet.html + Sortable.min.js there instead.
)
exit /b 0
