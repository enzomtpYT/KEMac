@echo off
SETLOCAL EnableDelayedExpansion

echo ===================================================
echo KEMac - Kori's RNG Macro
echo ===================================================
echo.

REM Check if virtual environment exists
IF NOT EXIST "venv\" (
    echo [ERROR] Virtual environment not found.
    echo Please run initial-setup.bat first to set up the environment.
    pause
    exit /b 1
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if Tesseract is in PATH
SET "TESSPATH=C:\Program Files\Tesseract-OCR"
IF EXIST "%TESSPATH%\tesseract.exe" (
    echo %PATH% | findstr /I /C:"%TESSPATH%" > nul
    IF %ERRORLEVEL% NEQ 0 (
        echo [INFO] Adding Tesseract OCR to PATH for this session...
        SET "PATH=%PATH%;%TESSPATH%"
    )
) ELSE (
    echo [WARNING] Tesseract OCR not found at %TESSPATH%
    echo The application may not function correctly without Tesseract OCR.
    echo Please run initial-setup.bat to install Tesseract OCR.
)

REM Start the Python application
echo [INFO] Starting KEMac application...
echo.
echo Press Ctrl+C to stop the application
echo.
python app.py

REM Deactivate virtual environment when done
call venv\Scripts\deactivate.bat

echo.
echo ===================================================
echo Application closed.
echo ===================================================

pause