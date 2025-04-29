from PIL import ImageGrab
import os
from app.config import socketio, ocr_results, status_file
from app.ocr.ocr_processor import generate_highlighted_screenshot
from flask_socketio import emit

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket client connection"""
    print('Client connected')
    
    # Get the current status from the status file if it exists
    current_status = "stopped"  # Default status
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r') as f:
                saved_status = f.read().strip()
                if saved_status in ["running", "paused", "stopped"]:
                    current_status = saved_status
                    print(f"Sending saved status to client: {current_status}")
        except Exception as e:
            print(f"Error reading status file: {str(e)}")
    
    # Send current status and data to the newly connected client
    emit('status_update', {'status': current_status})
    emit('ocr_update', {'results': ocr_results})
    
    # If we have regions defined, send a screenshot
    try:
        screenshot = ImageGrab.grab()
        highlighted_screenshot = generate_highlighted_screenshot(screenshot)
        emit('screenshot_update', {'screenshot': highlighted_screenshot})
    except Exception as e:
        print(f"Error sending initial screenshot: {str(e)}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket client disconnection"""
    print('Client disconnected')

@socketio.on('request_status')
def handle_request_status():
    """Send current status to client"""
    # Get the current status from the status file if it exists
    current_status = "stopped"  # Default status
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r') as f:
                saved_status = f.read().strip()
                if saved_status in ["running", "paused", "stopped"]:
                    current_status = saved_status
        except Exception as e:
            print(f"Error reading status file: {str(e)}")
    
    emit('status_update', {'status': current_status})

@socketio.on('request_screenshot')
def handle_request_screenshot():
    """Generate and send a new screenshot to client"""
    try:
        screenshot = ImageGrab.grab()
        highlighted_screenshot = generate_highlighted_screenshot(screenshot)
        emit('screenshot_update', {'screenshot': highlighted_screenshot})
    except Exception as e:
        emit('error', {'message': f"Error generating screenshot: {str(e)}"})

@socketio.on('request_ocr_results')
def handle_request_ocr_results():
    """Send current OCR results to client"""
    emit('ocr_update', {'results': ocr_results})