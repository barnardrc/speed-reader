@echo off
setlocal

:: 1. Try Standard Python
where python >nul 2>nul
if %errorlevel% equ 0 (
    python install.py
    pause
    exit /b
)

:: 2. Try Conda (Fallback)
call conda --version >nul 2>nul
if %errorlevel% equ 0 (
    echo Python command not found, but Conda detected.
    echo Launching installer via Conda...
    call conda run -n base python install.py
    pause
    exit /b
)

:: 3. Failure
echo Error: Neither Python nor Conda were found in your PATH.
echo Please install Python from python.org or Anaconda.
pause