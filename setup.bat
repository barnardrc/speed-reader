@echo off
setlocal

:: 1. Check if 'python' is a working interpreter (bypasses Windows Store shims)
python --version >nul 2>&1
if %errorlevel% equ 0 (
    python install.py
    pause
    exit /b
)

:: 2. Try Conda (Fallback)
call conda --version >nul 2>nul
if %errorlevel% equ 0 (
    echo System Python not found or not working.
    echo Conda detected. Launching installer via Conda...
    call conda run -n base python install.py
    pause
    exit /b
)

:: 3. Failure
echo Error: Neither a working Python installation nor Conda were found.
echo Note: If Python is installed, ensure it is added to your system PATH.
pause