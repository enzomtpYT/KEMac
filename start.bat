@echo off
SETLOCAL DisableDelayedExpansion

echo ===================================================
echo KEMac - Kori's RNG Macro
echo ===================================================
echo.

REM Check if virtual environment exists
IF NOT EXIST "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found.
    echo Please run initial-setup.bat first to set up the environment.
    pause
    exit /b 1
)

REM Activate virtual environment using full direct path
echo [INFO] Activating virtual environment...
set "VENV_ACTIVATE=%~dp0venv\Scripts\activate.bat"
call "%VENV_ACTIVATE%"

REM Check if activation was successful by checking if VIRTUAL_ENV is defined
IF NOT DEFINED VIRTUAL_ENV (
    echo [ERROR] Failed to activate virtual environment.
    echo Please try running the script as administrator or recreate the virtual environment.
    pause
    exit /b 1
)

REM Add Tesseract to PATH if it exists (without using findstr)
SET "TESSPATH=C:\Program Files\Tesseract-OCR"
IF EXIST "%TESSPATH%\tesseract.exe" (
    REM Simply add to PATH, Windows will handle duplicates appropriately
    echo [INFO] Adding Tesseract OCR to PATH for this session...
    SET "PATH=%PATH%;%TESSPATH%"
) ELSE (
    echo [WARNING] Tesseract OCR not found at %TESSPATH%
    echo The application may not function correctly without Tesseract OCR.
    echo Please run initial-setup.bat to install Tesseract OCR.
)

REM Store the current directory to return here after running the app
SET "CURRENT_DIR=%CD%"

REM Start the Python application
echo [INFO] Starting KEMac application...
echo.
echo Press Ctrl+C to stop the application
echo.
python "%~dp0app.py"

REM Return to the original directory
cd /d "%CURRENT_DIR%"

REM Deactivate virtual environment when done using the full path
IF DEFINED VIRTUAL_ENV (
    echo [INFO] Deactivating virtual environment...
    call "%~dp0venv\Scripts\deactivate.bat"
    IF ERRORLEVEL 1 (
        echo [WARNING] Could not properly deactivate the virtual environment.
        echo This is not a critical error and won't affect functionality.
    )
)

echo.
echo ===================================================
echo Application closed.
echo ===================================================

pause