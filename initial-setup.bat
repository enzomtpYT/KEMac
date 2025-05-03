@echo off
SETLOCAL EnableDelayedExpansion

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
    python -m venv venv
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
echo [INFO] Activating virtual environment and installing dependencies...
call venv\Scripts\activate.bat

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
    IF NOT EXIST "temp\" mkdir temp
    cd temp
    
    REM Download Tesseract OCR installer
    echo [INFO] Downloading Tesseract OCR installer...
    powershell -Command "& {Invoke-WebRequest -Uri 'https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe' -OutFile 'tesseract-installer.exe'}"
    IF %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to download Tesseract OCR.
        cd ..
        pause
        exit /b 1
    )
    
    REM Install Tesseract OCR silently
    echo [INFO] Installing Tesseract OCR...
    echo This may take a moment, and you may need to approve admin permissions.
    tesseract-installer.exe /S
    IF %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Failed to install Tesseract OCR.
        cd ..
        pause
        exit /b 1
    )
    
    cd ..
    echo [SUCCESS] Tesseract OCR installed successfully.
)

REM Add Tesseract to PATH for the current session if needed
SET "TESSPATH=C:\Program Files\Tesseract-OCR"
echo %PATH% | findstr /I /C:"%TESSPATH%" > nul
IF %ERRORLEVEL% NEQ 0 (
    echo [INFO] Adding Tesseract OCR to PATH for this session...
    SET "PATH=%PATH%;%TESSPATH%"
)

REM Create necessary directories if they don't exist
IF NOT EXIST "settings\logs\" mkdir settings\logs\
IF NOT EXIST "settings\debug\" mkdir settings\debug\

echo.
echo ===================================================
echo Setup completed successfully!
echo.
echo To run the application:
echo   1. Open a command prompt in this directory
echo   2. Run: venv\Scripts\activate
echo   3. Run: python app.py
echo.
echo You can now access the web interface at:
echo   - Local: http://127.0.0.1:5000/
echo   - Network: http://[your-ip]:5000/
echo ===================================================
echo.

call venv\Scripts\deactivate.bat
pause