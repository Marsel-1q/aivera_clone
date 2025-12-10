@echo off
cd /d "%~dp0"

REM Check for python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH.
    pause
    exit /b 1
)

REM Create venv if it doesn't exist
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo Installing dependencies...
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

REM Run the server
echo Starting AI Clone Server...
echo Open http://localhost:3000 in your browser.
set PYTHONPATH=%PYTHONPATH%;%cd%
python -m uvicorn ai_clone_server.app:app --host 127.0.0.1 --port 3000 --reload
pause
