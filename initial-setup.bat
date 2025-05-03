@echo off
SETLOCAL DisableDelayedExpansion

echo ===================================================
echo KEMac - Kori's RNG Macro Setup Script
echo ===================================================
echo.

REM Check for Python installation
python --version > nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.9 or higher from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

REM Extract Python version
for /f "tokens=2" %%I in ('python --version 2^>^&1') do set "PYTHON_VERSION=%%I"
echo [INFO] Found Python %PYTHON_VERSION%

REM Create virtual environment if it doesn't exist
IF NOT EXIST "venv\" (
    echo [INFO] Creating virtual environment...
    python -m venv "%~dp0venv"
    IF %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [SUCCESS] Virtual environment created.
) ELSE (
    echo [INFO] Virtual environment already exists.
)

REM Activate virtual environment and install dependencies
echo [INFO] Activating virtual environment...
set "VENV_ACTIVATE=%~dp0venv\Scripts\activate.bat"
call "%VENV_ACTIVATE%"

REM Check if activation was successful
IF NOT DEFINED VIRTUAL_ENV (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

echo [INFO] Upgrading pip...
python -m pip install --upgrade pip

echo [INFO] Installing Python dependencies...
pip install flask flask-socketio pillow pytesseract numpy opencv-python requests
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install Python dependencies.
    pause
    exit /b 1
)
echo [SUCCESS] Python dependencies installed.

REM Check if Tesseract OCR is already installed
IF EXIST "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    echo [INFO] Tesseract OCR is already installed.
) ELSE (
    echo [INFO] Tesseract OCR not found. Downloading and installing...
    
    REM Create temp directory for downloads
    IF NOT EXIST "%~dp0temp" mkdir "%~dp0temp"
    pushd "%~dp0temp"
    
    REM Download Tesseract OCR installer
    echo [INFO] Downloading Tesseract OCR installer...
    powershell -Command "& {Invoke-WebRequest -Uri 'https://github.com/UB-Mannheim/tesseract/releases/download/v5.3.3.20231005/tesseract-ocr-w64-setup-5.3.3.20231005.exe' -OutFile 'tesseract-installer.exe'}"
    IF %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to download Tesseract OCR.
        popd
        pause
        exit /b 1
    )
    
    REM Install Tesseract OCR silently
    echo [INFO] Installing Tesseract OCR...
    echo This may take a moment, and you may need to approve admin permissions.
    tesseract-installer.exe /S
    IF %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to install Tesseract OCR.
        popd
        pause
        exit /b 1
    )
    
    popd
    echo [SUCCESS] Tesseract OCR installed successfully.
)

REM Add Tesseract to PATH for the current session (without using findstr)
SET "TESSPATH=C:\Program Files\Tesseract-OCR"
echo [INFO] Adding Tesseract OCR to PATH for this session...
SET "PATH=%PATH%;%TESSPATH%"

REM Create necessary directories if they don't exist
IF NOT EXIST "%~dp0settings\logs\" mkdir "%~dp0settings\logs\"
IF NOT EXIST "%~dp0settings\debug\" mkdir "%~dp0settings\debug\"

echo.
echo ===================================================
echo Setup completed successfully!
echo.
echo To run the application:
echo   1. Double-click start.bat in this folder
echo   or
echo   1. Open a command prompt in this directory
echo   2. Run: venv\Scripts\activate
echo   3. Run: python app.py
echo.
echo You can now access the web interface at:
echo   - Local: http://127.0.0.1:5000/
echo   - Network: http://[your-ip]:5000/
echo ===================================================
echo.

call deactivate
pause