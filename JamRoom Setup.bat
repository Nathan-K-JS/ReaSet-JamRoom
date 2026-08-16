@echo off
title Jam Room Importer - one-time setup
echo ============================================
echo  Jam Room Importer - one-time setup
echo ============================================
echo This installs the free programs the importer needs.
echo (Python, yt-dlp, ffmpeg - all via Windows' winget)
echo.
pause
winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
winget install --id yt-dlp.yt-dlp -e --accept-package-agreements --accept-source-agreements
winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
echo.
echo Installing Python libraries...
set PYEXE=%LocalAppData%\Programs\Python\Python312\python.exe
if exist "%PYEXE%" ( "%PYEXE%" -m pip install requests numpy ) else ( python -m pip install requests numpy || py -3 -m pip install requests numpy )
echo.
if not exist "%~dp0tools\jamroom_import.config.json" copy "%~dp0tools\jamroom_import.config.example.json" "%~dp0tools\jamroom_import.config.json"
echo ============================================
echo  Setup finished.
echo  Next: double-click "JamRoom Importer.bat".
echo  (It will ask for your Fadr API key the first time.)
echo ============================================
pause
