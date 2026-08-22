@echo off
title Jam Room Importer
cd /d "%~dp0"

rem Stop any importer still holding the port. Closing the window does not
rem always end the process, and Windows will happily let a second server bind
rem the same port - leaving the OLD code answering after a "restart".
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" >nul 2>&1

set PYEXE=%LocalAppData%\Programs\Python\Python312\python.exe
if exist "%PYEXE%" ( "%PYEXE%" tools\jamroom_importer_server.py ) else ( python tools\jamroom_importer_server.py || py -3 tools\jamroom_importer_server.py )
echo.
echo The importer stopped. Press any key to close.
pause >nul
