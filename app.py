import os
import json
import socket
import threading
import sys

# Add the current directory to the Python path for proper imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import configuration module - note we now import flask_app instead of app
from app.config import flask_app, socketio, ocr_settings, ocr_results, settings_file, ocr_thread, stop_ocr_thread, settings_dir, status_file, macro_status
from app.ocr.ocr_processor import perform_ocr
from app.utils.logger import get_logger, LogLevel

# Create logger for this module
logger = get_logger(__name__, os.path.join(settings_dir, "app.log"))

# Import all routes to register them with Flask
import app.routes.api
import app.routes.ocr_routes
import app.routes.webhook_routes
import app.routes.socket_handlers

# Load settings if they exist
if os.path.exists(settings_file):
    try:
        with open(settings_file, 'r') as f:
            loaded_settings = json.load(f)
            
            # Update existing settings with loaded values
            ocr_settings["enabled"] = loaded_settings.get("enabled", False)
            ocr_settings["regions"] = loaded_settings.get("regions", [])
            
            # Handle webhook settings, ensuring they exist
            if "webhook" in loaded_settings:
                ocr_settings["webhook"]["enabled"] = loaded_settings["webhook"].get("enabled", False)
                ocr_settings["webhook"]["url"] = loaded_settings["webhook"].get("url", "")
                ocr_settings["webhook"]["biome_notifications"] = loaded_settings["webhook"].get("biome_notifications", True)
                ocr_settings["webhook"]["user_id"] = loaded_settings["webhook"].get("user_id", "")
                ocr_settings["webhook"]["keywords"] = loaded_settings["webhook"].get("keywords", [])
            
            logger.info("OCR settings loaded successfully")
    except Exception as e:
        logger.error("Could not load OCR settings, using defaults: {}", str(e))

# Load macro status if it exists
if os.path.exists(status_file):
    try:
        with open(status_file, 'r') as f:
            saved_status = f.read().strip()
            if saved_status in ["running", "paused", "stopped"]:
                globals()["macro_status"] = saved_status
                logger.info("Loaded saved macro status: {}", macro_status)
                
                # If status is running, start the OCR thread
                if macro_status == "running":
                    globals()["stop_ocr_thread"] = False
                    globals()["ocr_thread"] = threading.Thread(target=perform_ocr)
                    globals()["ocr_thread"].daemon = True
                    globals()["ocr_thread"].start()
                    logger.info("Automatically restarting OCR processing thread")
    except Exception as e:
        logger.error("Could not load saved macro status: {}", str(e))

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        # Create a socket and connect to an external server
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # No actual connection is made
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"  # Fallback to localhost if can't determine IP

if __name__ == "__main__":
    host = "0.0.0.0"  # Listen on all available network interfaces
    port = 5000
    local_ip = get_local_ip()
    
    logger.info("Starting Macro Control Web App...")
    logger.info("Local access: http://127.0.0.1:{}/", port)
    logger.info("Network access: http://{}:{}/", local_ip, port)
    logger.info("(Press CTRL+C to quit)")
    
    socketio.run(flask_app, host=host, port=port, debug=True, allow_unsafe_werkzeug=True)