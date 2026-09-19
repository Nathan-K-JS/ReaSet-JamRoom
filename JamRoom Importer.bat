@echo off
title Jam Room Importer
cd /d "%~dp0"

setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\ensure_importer_dependencies.ps1"
if errorlevel 1 goto stopped
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
echo Launcher finished. An existing importer may still be running.
echo Use Stop importer safely on its page to shut it down.
echo Press any key to close this window.
pause >nul
