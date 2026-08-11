@echo off
REM ============================================================
REM  DermAI - one-click launcher (Windows)
REM  Double-click this file. It sets up everything and runs the app.
REM ============================================================
cd /d "%~dp0"
echo ============================================================
echo   DermAI - Quantum Coders : starting up
echo ============================================================

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat

echo Installing requirements (first run only)...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
python -m pip install --quiet PyMySQL

echo.
echo Launching DermAI...  (open http://localhost:5000 in your browser)
echo Press CTRL+C here to stop.
echo.
python app.py

echo.
echo App stopped. Press any key to close.
pause >nul
