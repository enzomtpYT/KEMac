import os
import pytesseract
from flask import Flask
from flask_socketio import SocketIO

# Set the path to Tesseract executable - using default Windows installation path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Minimum dimensions for OCR regions to be processed
MIN_OCR_WIDTH = 10
MIN_OCR_HEIGHT = 10

# Flask app configuration - renaming to flask_app to avoid namespace conflict
flask_app = Flask(__name__, template_folder='../templates', static_folder='../static')
flask_app.config['SECRET_KEY'] = 'macro_control_secret_key'
socketio = SocketIO(flask_app, cors_allowed_origins="*")

# Global variables
macro_status = "stopped"  # Possible states: "running", "paused", "stopped"
ocr_settings = {
    "enabled": False,
    "regions": [],  # Will contain coordinates for OCR regions: [{"x1": 0, "y1": 0, "x2": 100, "y2": 100, "name": "Region 1"}]
    "webhook": {
        "enabled": False,
        "url": "",
        "biome_notifications": True,  # Enable biome notifications by default
        "user_id": "",  # User ID to ping in Discord
        "keywords": []  # List of keywords with ping settings: [{"text": "forest", "enabled": True, "ping": True}, ...]
    }
}
ocr_results = {}  # Store the latest OCR results for each region
ocr_thread = None  # Thread for OCR processing
stop_ocr_thread = False  # Flag to control the OCR thread

# Settings file path
settings_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "settings")
os.makedirs(settings_dir, exist_ok=True)
settings_file = os.path.join(settings_dir, "ocr_settings.json")