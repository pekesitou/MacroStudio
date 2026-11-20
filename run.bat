@echo off
cd /d "%~dp0"

rem ---------------------------------------------------------------------------
rem Macro Studio - launcher WITHOUT a visible terminal.
rem
rem If the compiled executable exists, launch it (built with --noconsole).
rem `start` detaches the process and this batch exits immediately, so no
rem console window stays open on screen.
rem ---------------------------------------------------------------------------
if exist "dist\MacroStudio-NoInstall.exe" (
    start "" "dist\MacroStudio-NoInstall.exe"
    exit /b
)

rem ---------------------------------------------------------------------------
rem Fallback for running from source: pythonw.exe is the GUI build of
rem Python and never creates a console window. Dependencies are installed
rem silently the first time if they are missing.
rem ---------------------------------------------------------------------------
python -c "import customtkinter, pynput, PIL" >nul 2>&1
if errorlevel 1 (
    python -m pip install --user customtkinter pynput pillow >nul 2>&1
)

start "" pythonw main.py
exit /b
