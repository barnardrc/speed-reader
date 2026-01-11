@echo off
:: Check if Python is installed
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python is not installed. Please install it from python.org.
    pause
    exit /b
)

:: Run the Python installer
python install.py
pause