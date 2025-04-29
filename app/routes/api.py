import os
import io
import base64
import json
import threading
import datetime
from PIL import ImageGrab, Image, ImageDraw
from flask import render_template, request, jsonify

from app.config import flask_app, socketio, ocr_settings, ocr_results, macro_status, settings_file
from app.config import ocr_thread, stop_ocr_thread
from app.ocr.ocr_processor import perform_ocr, generate_highlighted_screenshot
import pytesseract

@flask_app.route("/")
def home():
    return render_template("index.html")

@flask_app.route("/status")
def status():
    return jsonify({"status": macro_status})

@flask_app.route("/control", methods=["POST"])
def control_macro():
    global macro_status, ocr_thread, stop_ocr_thread
    action = request.form.get("action")
    
    if action == "start":
        # Start the macro
        macro_status = "running"
        
        # Start OCR processing in a separate thread if OCR is enabled
        if ocr_settings["enabled"] and ocr_settings["regions"]:
            stop_ocr_thread = False
            ocr_thread = threading.Thread(target=perform_ocr)
            ocr_thread.daemon = True
            ocr_thread.start()
            print("OCR processing started")
        
        # Emit status update via WebSocket
        socketio.emit('status_update', {'status': macro_status})
        
        return jsonify({"status": macro_status, "message": "Macro started"})
    
    elif action == "pause":
        # Pause the macro
        macro_status = "paused"
        
        # Emit status update via WebSocket
        socketio.emit('status_update', {'status': macro_status})
        
        return jsonify({"status": macro_status, "message": "Macro paused"})
    
    elif action == "stop":
        # Stop the macro and OCR thread
        macro_status = "stopped"
        stop_ocr_thread = True
        print("OCR processing stopped")
        
        # Emit status update via WebSocket
        socketio.emit('status_update', {'status': macro_status})
        
        return jsonify({"status": macro_status, "message": "Macro stopped"})
    
    return jsonify({"status": macro_status, "message": "Invalid action"})

@flask_app.route("/screenshot", methods=["GET"])
def take_screenshot():
    # Take a screenshot of the entire screen
    screenshot = ImageGrab.grab()
    
    # Convert the image to bytes
    img_byte_arr = io.BytesIO()
    screenshot.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    
    # Convert to base64 for displaying in browser
    img_base64 = base64.b64encode(img_byte_arr).decode('utf-8')
    
    return jsonify({"screenshot": img_base64})