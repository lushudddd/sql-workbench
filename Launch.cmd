@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "app.py"
    exit /b
)
where pythonw.exe >nul 2>&1
if errorlevel 1 (
    echo Python with Tkinter is required. See README.md.
    pause
    exit /b 1
)
start "" pythonw.exe "app.py"
