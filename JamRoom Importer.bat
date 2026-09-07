@echo off
title Jam Room Importer
cd /d "%~dp0"

setlocal
rem The server detects an occupied port itself. Never kill another process or
rem interrupt an in-progress import just because it owns port 8765.

set "PYEXE=%LocalAppData%\Programs\Python\Python312\python.exe"
if exist "%PYEXE%" goto run_python
py -3 --version >nul 2>&1
if not errorlevel 1 (
    py -3 tools\jamroom_importer_server.py
    goto stopped
)
set "PYEXE=python"
:run_python
"%PYEXE%" tools\jamroom_importer_server.py
:stopped
echo.
echo The importer stopped. Press any key to close.
pause >nul
