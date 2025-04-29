import os
import io
import base64
import json
import threading
import datetime
from PIL import ImageGrab, Image, ImageDraw
from flask import render_template, request, jsonify

from app.config import flask_app, socketio, ocr_settings, ocr_results, macro_status, settings_file, status_file
from app.config import ocr_thread, stop_ocr_thread
from app.ocr.ocr_processor import perform_ocr, generate_highlighted_screenshot
import pytesseract

# Function to save macro status to file
def save_macro_status(status):
    """Save current macro status to file for persistence"""
    with open(status_file, 'w') as f:
        f.write(status)
    print(f"Macro status saved: {status}")

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
        
        # Save status to file
        save_macro_status(macro_status)
        
        # Always start OCR processing thread when macro is started
        stop_ocr_thread = False
        
        # Check if thread already exists and is alive
        if ocr_thread is None or not ocr_thread.is_alive():
            ocr_thread = threading.Thread(target=perform_ocr)
            ocr_thread.daemon = True
            ocr_thread.start()
            
            if ocr_settings["enabled"]:
                if ocr_settings["regions"]:
                    print(f"OCR processing started with {len(ocr_settings['regions'])} region(s)")
                else:
                    print("OCR is enabled but no regions are defined. Define regions in OCR Settings tab.")
                    # Send an notification to the client
                    socketio.emit('error', {'message': "OCR is enabled but no regions are defined. Please define regions in OCR Settings tab."})
            else:
                print("OCR is disabled. Enable it in the OCR Settings tab to process regions.")
                # Send an notification to the client
                socketio.emit('error', {'message': "OCR is disabled. Enable it in the OCR Settings tab to process regions."})
        else:
            print("OCR thread is already running")
        
        # Emit status update via WebSocket
        socketio.emit('status_update', {'status': macro_status})
        
        return jsonify({"status": macro_status, "message": "Macro started"})
    
    elif action == "pause":
        # Pause the macro
        macro_status = "paused"
        
        # Save status to file
        save_macro_status(macro_status)
        
        # Emit status update via WebSocket
        socketio.emit('status_update', {'status': macro_status})
        
        return jsonify({"status": macro_status, "message": "Macro paused"})
    
    elif action == "stop":
        # Stop the macro and OCR thread
        macro_status = "stopped"
        stop_ocr_thread = True
        print("OCR processing stopped")
        
        # Save status to file
        save_macro_status(macro_status)
        
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