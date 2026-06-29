@echo off
setlocal
cd /d "%~dp0"
title KreativOS

:: ── First-time setup ──────────────────────────────────────────────────────────
if not exist "venv\Scripts\python.exe" (
    echo [KreativOS] First-time setup — please wait...
    python --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python not found. Install Python 3.11+ from https://python.org
        pause & exit /b 1
    )
    python -m venv venv
    call venv\Scripts\activate
    pip install -r requirements.txt -q
    if errorlevel 1 ( echo ERROR: pip install failed. & pause & exit /b 1 )
    cd frontend
    call npm ci --silent
    if errorlevel 1 ( echo ERROR: npm ci failed. Install Node.js from https://nodejs.org & pause & exit /b 1 )
    call npm run build
    cd ..
    echo [KreativOS] Setup complete!
) else (
    call venv\Scripts\activate
)

:: ── Open browser after 3-second delay ─────────────────────────────────────────
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:8000"

echo.
echo  ██╗  ██╗██████╗ ███████╗ █████╗ ████████╗██╗██╗   ██╗ ██████╗ ███████╗
echo  ██║ ██╔╝██╔══██╗██╔════╝██╔══██╗╚══██╔══╝██║██║   ██║██╔═══██╗██╔════╝
echo  █████╔╝ ██████╔╝█████╗  ███████║   ██║   ██║██║   ██║██║   ██║███████╗
echo  ██╔═██╗ ██╔══██╗██╔══╝  ██╔══██║   ██║   ██║╚██╗ ██╔╝██║   ██║╚════██║
echo  ██║  ██╗██║  ██║███████╗██║  ██║   ██║   ██║ ╚████╔╝ ╚██████╔╝███████║
echo  ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═══╝   ╚═════╝ ╚══════╝
echo.
echo  Running at http://127.0.0.1:8000
echo  Press Ctrl+C to stop.
echo.

python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
endlocal
