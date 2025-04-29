# KEMac - Kori's RNG Macro

A web based macro for the Roblox Game [Kori's RNG](https://www.roblox.com/games/75221514607466)

This is very basic i don't plan on doing advanced macro, feel free to take this as a base, i know it is badly coded

## Features

- **Real-time OCR**: Capture text from defined screen regions automatically
- **Multiple OCR Methods**: Uses various preprocessing techniques to improve text detection accuracy
- **Configurable Regions**: Define custom regions on your screen for targeted text detection
- **Web Interface**: Monitor and control the application from any device on your network
- **WebSocket Support**: Real-time updates without page refreshes
- **Screenshot Preview**: Visual feedback showing monitored regions and detected text

## Requirements

- Python 3.9 or higher
- Tesseract OCR installed on your system
- Flask and related Python packages

## Installation

1. Install [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (default path: `C:\Program Files\Tesseract-OCR\tesseract.exe`)

2. Install required Python packages:
   ```
   pip install flask flask-socketio pillow pytesseract numpy opencv-python requests
   ```

3. Clone or download this repository

## Usage

1. Start the application:
   ```
   python index.py
   ```

2. Access the web interface:
   - Local access: http://127.0.0.1:5000/
   - Network access: http://{your-ip}:5000/

3. Configure OCR regions by defining areas on your screen

4. Start the OCR monitoring process using the web interface controls

## Configuration

OCR settings are saved in `settings/ocr_settings.json` and will be loaded automatically on startup.

## Debug Information

Debug images showing the OCR processing steps are saved in the `settings/debug/` directory.

## License

This project is provided for educational and personal use.