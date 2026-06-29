@echo off
cd /d "%~dp0"
title KreativOS Uninstaller

echo.
echo  KreativOS Uninstaller
echo  =====================
echo  This removes ONLY files created during install:
echo    - venv\               (Python virtual environment)
echo    - frontend\node_modules\  (npm packages)
echo    - frontend\dist\      (built frontend)
echo    - backend __pycache__ dirs  (Python bytecode)
echo.
echo  Your workspace, projects, memory, and uploaded files are NOT touched.
echo.
set /p "confirm=Type YES to proceed (anything else cancels): "
if /i not "%confirm%"=="YES" (
    echo Cancelled — nothing removed.
    pause & exit /b 0
)

echo.
if exist "venv" (
    echo Removing venv...
    rd /s /q "venv"
)
if exist "frontend\node_modules" (
    echo Removing node_modules...
    rd /s /q "frontend\node_modules"
)
if exist "frontend\dist" (
    echo Removing frontend build...
    rd /s /q "frontend\dist"
)
echo Removing Python cache...
for /d /r "%~dp0backend" %%d in (__pycache__) do (
    if exist "%%d" rd /s /q "%%d"
)

echo.
echo Done. KreativOS install files removed.
echo Run KreativOS.bat again to reinstall.
pause
