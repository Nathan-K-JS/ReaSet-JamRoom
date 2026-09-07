@echo off
title Jam Room Importer
cd /d "%~dp0"

rem The server detects a occupied port itself. Never kill another process or
rem interrupt an in-progress import just because it owns port 8765.

set PYEXE=%LocalAppData%\Programs\Python\Python312\python.exe
if exist "%PYEXE%" ( "%PYEXE%" tools\jamroom_importer_server.py ) else ( python tools\jamroom_importer_server.py || py -3 tools\jamroom_importer_server.py )
echo.
echo The importer stopped. Press any key to close.
pause >nul
