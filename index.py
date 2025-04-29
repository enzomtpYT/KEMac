from flask import Flask, render_template, request, jsonify, Response
import os
import datetime
import socket
import base64
import json
from PIL import ImageGrab, Image, ImageEnhance, ImageFilter, ImageDraw
import io
import threading
import time
import pytesseract
import numpy as np
import requests
from flask_socketio import SocketIO, emit

# Set the path to Tesseract executable - uncommented and using default Windows installation path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Minimum dimensions for OCR regions to be processed
MIN_OCR_WIDTH = 10
MIN_OCR_HEIGHT = 10

app = Flask(__name__)
app.config['SECRET_KEY'] = 'macro_control_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

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

# Create settings directory if it doesn't exist
settings_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings")
os.makedirs(settings_dir, exist_ok=True)
settings_file = os.path.join(settings_dir, "ocr_settings.json")

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
            
            print("OCR settings loaded successfully")
    except Exception as e:
        print(f"Could not load OCR settings, using defaults: {str(e)}")

def send_webhook(region_name, text):
    """Send webhook notification for biome regions when text matches keywords"""
    if not ocr_settings["webhook"]["enabled"] or not ocr_settings["webhook"]["url"]:
        return False
    
    if not ocr_settings["webhook"]["biome_notifications"]:
        return False
    
    # Check if region name contains "biome" (case-insensitive)
    if "biome" not in region_name.lower():
        return False
    
    # Check if there are keywords defined
    keywords = ocr_settings["webhook"]["keywords"]
    
    # Normalize detected text for comparison
    detected_text = text.lower()
    
    # Variables to track matches
    text_matched = False
    matching_keyword = None
    should_ping = False
    
    # If no keywords are defined, allow all text
    if not keywords:
        text_matched = True
    else:
        # Check if any keyword matches the detected text
        for keyword in keywords:
            # Skip disabled keywords
            if not keyword.get("enabled", True):
                continue
                
            keyword_text = keyword.get("text", "").lower()
            if not keyword_text:
                continue
                
            # Check if the keyword is in the detected text
            if keyword_text in detected_text:
                text_matched = True
                matching_keyword = keyword
                should_ping = keyword.get("ping", False)
                print(f"OCR text in '{region_name}' matched keyword: '{keyword_text}'")
                break
    
    # If no keyword was matched and we have keywords defined, don't send webhook
    if not text_matched and keywords:
        print(f"OCR text in '{region_name}' did not match any keywords. Webhook not sent.")
        return False
    
    webhook_url = ocr_settings["webhook"]["url"]
    is_discord = "discord" in webhook_url.lower()
    user_id = ocr_settings["webhook"]["user_id"]
    
    # Get the cropped region image path
    debug_dir = os.path.join(settings_dir, "debug")
    original_image_path = os.path.join(debug_dir, f"{region_name}_original.png")
    
    # Generate a timestamp for the image filename
    current_time = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    try:
        timestamp = datetime.datetime.now().isoformat()
        
        if is_discord:
            # Format content with ping if required
            matched_keyword_text = matching_keyword.get("text", "Unknown") if matching_keyword else "Matched"
            content = f"**{matched_keyword_text}** detected in region **{region_name}**"
            
            if should_ping and user_id:
                content = f"<@{user_id}> {content}"
            
            # First, send a Discord message with the detected keyword and metadata
            files = {}
            
            # Check if the image exists and attach it
            if os.path.exists(original_image_path):
                # Create multipart form-data with image file
                with open(original_image_path, 'rb') as img_file:
                    # Format for Discord webhook with file attachment
                    payload = {
                        "username": "OCR Biome Detector",
                        "content": content,
                        "embeds": [
                            {
                                "title": f"Biome Detection in {region_name}",
                                "color": 3447003,  # Blue color
                                "timestamp": timestamp,
                                "fields": [
                                    {
                                        "name": "Region",
                                        "value": region_name,
                                        "inline": True
                                    },
                                    {
                                        "name": "Timestamp",
                                        "value": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        "inline": True
                                    },
                                    {
                                        "name": "Detected Keyword",
                                        "value": matched_keyword_text,
                                        "inline": True
                                    }
                                ],
                                "footer": {
                                    "text": "OCR Biome Detection System"
                                }
                            }
                        ]
                    }
                    
                    # Discord requires "file" as the key for file uploads
                    files = {
                        "file": (f"{region_name}_{current_time}.png", img_file, "image/png")
                    }
                    
                    # Send the webhook request with file
                    response = requests.post(
                        webhook_url,
                        data={"payload_json": json.dumps(payload)},
                        files=files,
                        timeout=5  # Slightly longer timeout
                    )
            else:
                # If image doesn't exist, send without attachment
                print(f"Image not found: {original_image_path}")
                payload = {
                    "username": "OCR Biome Detector",
                    "content": content,
                    "embeds": [
                        {
                            "title": f"Biome Detection in {region_name}",
                            "description": "No image available",
                            "color": 3447003,  # Blue color
                            "timestamp": timestamp,
                            "fields": [
                                {
                                    "name": "Region",
                                    "value": region_name,
                                    "inline": True
                                },
                                {
                                    "name": "Timestamp",
                                    "value": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    "inline": True
                                },
                                {
                                    "name": "Detected Keyword",
                                    "value": matched_keyword_text,
                                    "inline": True
                                }
                            ],
                            "footer": {
                                "text": "OCR Biome Detection System"
                            }
                        }
                    ]
                }
                
                # Send the webhook request
                response = requests.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=5
                )
        else:
            # Generic webhook format
            matched_keyword_text = matching_keyword.get("text", "Unknown") if matching_keyword else "Matched"
            
            payload = {
                "timestamp": timestamp,
                "region_name": region_name,
                "detected_keyword": matched_keyword_text
            }
            
            # Send the webhook request
            response = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5  # Slightly longer timeout
            )
        
        # Log the response
        print(f"Webhook sent for biome region '{region_name}': {response.status_code}")
        
        # If there was an error, log the response content
        if response.status_code >= 400:
            print(f"Webhook error response: {response.text}")
            
        return response.status_code < 400  # Return success if status code < 400
    
    except Exception as e:
        print(f"Webhook error for biome region '{region_name}': {str(e)}")
        return False

def preprocess_image_for_ocr(img):
    """Apply image preprocessing to improve OCR accuracy"""
    # Convert to grayscale if not already
    if img.mode != 'L':
        img = img.convert('L')
    
    # Try multiple preprocessing techniques and combine them
    methods = []
    
    # Method 1: High contrast
    img1 = img.copy()
    enhancer = ImageEnhance.Contrast(img1)
    img1 = enhancer.enhance(2.5)
    img1 = img1.point(lambda x: 0 if x < 140 else 255, '1')
    methods.append(img1)
    
    # Method 2: Sharpening with different threshold
    img2 = img.copy()
    enhancer = ImageEnhance.Contrast(img2)
    img2 = enhancer.enhance(2.0)
    img2 = img2.filter(ImageFilter.SHARPEN)
    img2 = img2.filter(ImageFilter.SHARPEN)
    img2 = img2.point(lambda x: 0 if x < 160 else 255, '1')
    methods.append(img2)
    
    # Method 3: Edge enhancement
    img3 = img.copy()
    img3 = img3.filter(ImageFilter.EDGE_ENHANCE_MORE)
    enhancer = ImageEnhance.Contrast(img3)
    img3 = enhancer.enhance(1.8)
    img3 = img3.point(lambda x: 0 if x < 150 else 255, '1')
    methods.append(img3)
    
    # Method 4: Inverted for light text on dark background
    img4 = img.copy()
    enhancer = ImageEnhance.Contrast(img4)
    img4 = enhancer.enhance(2.0)
    img4 = img4.point(lambda x: 0 if x > 100 else 255, '1')  # Inverted threshold
    methods.append(img4)
    
    return methods

def perform_ocr():
    """Thread function to perform OCR at regular intervals"""
    global stop_ocr_thread, ocr_results
    
    while macro_status == "running" and not stop_ocr_thread:
        if ocr_settings["enabled"] and ocr_settings["regions"]:
            try:
                # Take a screenshot
                screenshot = ImageGrab.grab()
                
                # Get screen dimensions
                screen_width, screen_height = screenshot.size
                
                # Process each region
                for i, region in enumerate(ocr_settings["regions"]):
                    try:
                        # Get region name
                        region_name = region.get("name", f"Region {i+1}")
                        
                        # Ensure coordinates are within screen boundaries
                        x1 = max(0, min(region["x1"], screen_width - 1))
                        y1 = max(0, min(region["y1"], screen_height - 1))
                        x2 = max(x1 + 1, min(region["x2"], screen_width))
                        y2 = max(y1 + 1, min(region["y2"], screen_height))
                        
                        # Calculate dimensions
                        width = x2 - x1
                        height = y2 - y1
                        
                        # Skip extremely small regions
                        if width < MIN_OCR_WIDTH or height < MIN_OCR_HEIGHT:
                            print(f"Region '{region_name}' is too small ({width}x{height}), minimum size is {MIN_OCR_WIDTH}x{MIN_OCR_HEIGHT}. Skipping.")
                            ocr_results[region_name] = f"Region too small for OCR ({width}x{height})"
                            continue
                        
                        # Crop the screenshot to the region
                        region_img = screenshot.crop((x1, y1, x2, y2))
                        
                        # Save original region for debug
                        debug_dir = os.path.join(settings_dir, "debug")
                        os.makedirs(debug_dir, exist_ok=True)
                        original_debug = os.path.join(debug_dir, f"{region_name}_original.png")
                        region_img.save(original_debug)
                        
                        # Check if the region is small (but still processable)
                        is_small = width < 50 or height < 20
                        
                        # Apply upscaling if region is small
                        if is_small:
                            print(f"Region '{region_name}' is small ({width}x{height}), applying enhancement.")
                            # Resize small regions to improve OCR (scale up 3x)
                            scale_factor = 3
                            region_img = region_img.resize((width * scale_factor, height * scale_factor), Image.LANCZOS)
                        
                        # Apply multiple preprocessing methods
                        processed_imgs = preprocess_image_for_ocr(region_img)
                        
                        # Save debug images
                        for idx, processed_img in enumerate(processed_imgs):
                            debug_file = os.path.join(debug_dir, f"{region_name}_method{idx+1}.png")
                            processed_img.save(debug_file)
                        
                        # Try different OCR configurations
                        ocr_configs = [
                            '--psm 6',  # Assume a single uniform block of text
                            '--psm 7',  # Single line of text
                            '--psm 8',  # Single word
                            '--psm 4',  # Assume single column of text of variable sizes
                            '--psm 3 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,-:;(){}[]<>!@#$%^&*+=/\\|"\'?_ '
                        ]
                        
                        # Find the best OCR result
                        best_text = ""
                        best_config = ""
                        best_method = 0
                        
                        for idx, processed_img in enumerate(processed_imgs):
                            for config in ocr_configs:
                                text = pytesseract.image_to_string(processed_img, config=config).strip()
                                
                                # Skip empty results
                                if not text:
                                    continue
                                    
                                # Check if this text is better than what we have
                                if len(text) > len(best_text):
                                    best_text = text
                                    best_config = config
                                    best_method = idx + 1
                        
                        # If no text was detected
                        if not best_text:
                            best_text = "(No text detected)"
                            # Try one more trick: use image_to_data for low confidence text detection
                            try:
                                data = pytesseract.image_to_data(processed_imgs[0], output_type=pytesseract.Output.DICT)
                                text_candidates = []
                                for j in range(len(data['text'])):
                                    if int(data['conf'][j]) > 10 and data['text'][j].strip():  # Very low confidence threshold
                                        text_candidates.append(data['text'][j])
                                
                                if text_candidates:
                                    best_text = " ".join(text_candidates)
                                    best_method = "low_conf"
                            except:
                                pass
                            
                        # Log metadata about the detection
                        print(f"OCR Result for {region_name} ({width}x{height}):")
                        print(f"Best method: {best_method}, Config: {best_config}")
                        print(f"Text: {best_text}")
                        print("-" * 40)
                        
                        # Save result
                        ocr_results[region_name] = best_text.strip()
                        
                        # Send webhook for biome regions
                        if "biome" in region_name.lower() and ocr_settings["webhook"]["enabled"] and ocr_settings["webhook"]["url"]:
                            webhook_sent = send_webhook(region_name, best_text.strip())
                            if webhook_sent:
                                print(f"Webhook notification sent for biome region: {region_name}")
                        
                    except Exception as e:
                        error_msg = f"Error processing region {region_name}: {str(e)}"
                        print(error_msg)
                        # Store the error in results
                        ocr_results[region_name] = f"Error: {str(e)}"
                
                # Log timestamp
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"OCR scan completed at {timestamp}")
                print("=" * 60)
                
                # Emit OCR results via WebSockets
                socketio.emit('ocr_update', {'results': ocr_results, 'timestamp': timestamp})
                
                # Generate and emit highlighted screenshot
                try:
                    highlighted_screenshot = generate_highlighted_screenshot(screenshot)
                    socketio.emit('screenshot_update', {'screenshot': highlighted_screenshot})
                except Exception as e:
                    print(f"Error generating highlighted screenshot: {str(e)}")
                
            except Exception as e:
                print(f"OCR processing error: {str(e)}")
        
        # Sleep for 0.5 seconds
        time.sleep(0.5)

def generate_highlighted_screenshot(screenshot):
    """Generate a screenshot with OCR regions highlighted"""
    highlight_img = screenshot.copy()
    draw = ImageDraw.Draw(highlight_img, "RGBA")
    
    # Draw rectangles for each region with labels
    for i, region in enumerate(ocr_settings["regions"]):
        region_name = region.get("name", f"Region {i+1}")
        x1 = max(0, min(region["x1"], screenshot.width - 1))
        y1 = max(0, min(region["y1"], screenshot.height - 1))
        x2 = max(x1 + 1, min(region["x2"], screenshot.width))
        y2 = max(y1 + 1, min(region["y2"], screenshot.height))
        
        # Draw rectangle with semi-transparent fill
        draw.rectangle([x1, y1, x2, y2], 
                      outline=(255, 0, 0), 
                      fill=(255, 0, 0, 64), 
                      width=2)
        
        # Draw region name
        text_bg_width = len(region_name) * 7 + 4
        draw.rectangle([x1, y1-20, x1+text_bg_width, y1], 
                      fill=(0, 0, 0, 200))
        draw.text((x1+2, y1-18), region_name, fill=(255, 255, 255))
        
        # Draw OCR result if available
        if region_name in ocr_results:
            result_text = ocr_results[region_name]
            if not result_text.startswith("Error") and not result_text.startswith("Region too small"):
                # Truncate if too long
                if len(result_text) > 30:
                    result_text = result_text[:27] + "..."
                
                # Draw result near the bottom of region
                text_bg_width = len(result_text) * 7 + 4
                draw.rectangle([x1, y2+2, x1+text_bg_width, y2+22], 
                              fill=(0, 0, 128, 200))
                draw.text((x1+2, y2+4), result_text, fill=(255, 255, 255))
    
    # Convert the image to bytes
    img_byte_arr = io.BytesIO()
    highlight_img.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    
    # Convert to base64 for displaying in browser
    return base64.b64encode(img_byte_arr).decode('utf-8')

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/status")
def status():
    return jsonify({"status": macro_status})

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket client connection"""
    print('Client connected')
    # Send current status and data to the newly connected client
    emit('status_update', {'status': macro_status})
    emit('ocr_update', {'results': ocr_results})
    # If we have regions defined, send a screenshot
    if ocr_settings["regions"]:
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
    emit('status_update', {'status': macro_status})

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

@app.route("/control", methods=["POST"])
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

@app.route("/screenshot", methods=["GET"])
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

@app.route("/ocr_settings", methods=["GET", "POST"])
def manage_ocr_settings():
    global ocr_settings
    
    if request.method == "GET":
        return jsonify(ocr_settings)
    
    elif request.method == "POST":
        data = request.json
        ocr_settings["enabled"] = data.get("enabled", False)
        ocr_settings["regions"] = data.get("regions", [])
        
        # Save settings to file
        with open(settings_file, 'w') as f:
            json.dump(ocr_settings, f)
        
        # Broadcast settings update via WebSocket
        socketio.emit('settings_update', {'settings': ocr_settings})
        
        return jsonify({"message": "OCR settings saved successfully", "settings": ocr_settings})

@app.route("/add_ocr_region", methods=["POST"])
def add_ocr_region():
    global ocr_settings
    
    data = request.json
    new_region = {
        "x1": data.get("x1"),
        "y1": data.get("y1"),
        "x2": data.get("x2"),
        "y2": data.get("y2"),
        "name": data.get("name", f"Region {len(ocr_settings['regions']) + 1}")
    }
    
    ocr_settings["regions"].append(new_region)
    
    # Save settings to file
    with open(settings_file, 'w') as f:
        json.dump(ocr_settings, f)
    
    # Broadcast settings update via WebSocket
    socketio.emit('settings_update', {'settings': ocr_settings})
    
    return jsonify({"message": "OCR region added", "region": new_region, "settings": ocr_settings})

@app.route("/delete_ocr_region", methods=["POST"])
def delete_ocr_region():
    global ocr_settings
    
    data = request.json
    index = data.get("index")
    
    if 0 <= index < len(ocr_settings["regions"]):
        removed = ocr_settings["regions"].pop(index)
        
        # Save settings to file
        with open(settings_file, 'w') as f:
            json.dump(ocr_settings, f)
        
        # Broadcast settings update via WebSocket
        socketio.emit('settings_update', {'settings': ocr_settings})
        
        return jsonify({"message": f"OCR region '{removed['name']}' deleted", "settings": ocr_settings})
    
    return jsonify({"message": "Invalid region index", "settings": ocr_settings}), 400

@app.route("/ocr_results", methods=["GET"])
def get_ocr_results():
    """API endpoint to get the latest OCR results"""
    return jsonify(ocr_results)

@app.route("/verify_tesseract", methods=["GET"])
def verify_tesseract():
    """Endpoint to verify Tesseract installation and configuration"""
    result = {
        "installed": False,
        "path": None,
        "version": None,
        "error": None
    }
    
    try:
        # Check if tesseract path is set and exists
        tesseract_path = pytesseract.pytesseract.tesseract_cmd
        result["path"] = tesseract_path
        
        if not os.path.exists(tesseract_path):
            result["error"] = f"Tesseract executable not found at: {tesseract_path}"
            return jsonify(result)
        
        # Try to get tesseract version
        version_info = pytesseract.get_tesseract_version()
        result["version"] = str(version_info)
        result["installed"] = True
        
        # Create a simple test image with text
        test_img = Image.new('RGB', (100, 30), color=(255, 255, 255))
        
        # Test OCR functionality
        try:
            pytesseract.image_to_string(test_img)
            result["test_passed"] = True
        except Exception as e:
            result["test_passed"] = False
            result["test_error"] = str(e)
        
        return jsonify(result)
        
    except Exception as e:
        result["error"] = str(e)
        return jsonify(result)

@app.route("/highlighted_screenshot", methods=["GET"])
def get_highlighted_screenshot():
    """Generate and return a screenshot with OCR regions highlighted"""
    try:
        # Take a screenshot
        screenshot = ImageGrab.grab()
        
        # Create a copy for drawing
        highlight_img = screenshot.copy()
        draw = ImageDraw.Draw(highlight_img)
        
        # Draw rectangles for each region with labels
        for i, region in enumerate(ocr_settings["regions"]):
            region_name = region.get("name", f"Region {i+1}")
            x1 = max(0, min(region["x1"], screenshot.width - 1))
            y1 = max(0, min(region["y1"], screenshot.height - 1))
            x2 = max(x1 + 1, min(region["x2"], screenshot.width))
            y2 = max(y1 + 1, min(region["y2"], screenshot.height))
            
            # Draw rectangle with semi-transparent fill
            draw.rectangle([x1, y1, x2, y2], 
                          outline=(255, 0, 0), 
                          fill=(255, 0, 0, 64), 
                          width=2)
            
            # Draw region name
            text_bg_width = len(region_name) * 7 + 4
            draw.rectangle([x1, y1-20, x1+text_bg_width, y1], 
                          fill=(0, 0, 0, 200))
            draw.text((x1+2, y1-18), region_name, fill=(255, 255, 255))
            
            # Draw OCR result if available
            if region_name in ocr_results:
                result_text = ocr_results[region_name]
                if not result_text.startswith("Error") and not result_text.startswith("Region too small"):
                    # Truncate if too long
                    if len(result_text) > 30:
                        result_text = result_text[:27] + "..."
                    
                    # Draw result near the bottom of region
                    text_bg_width = len(result_text) * 7 + 4
                    draw.rectangle([x1, y2+2, x1+text_bg_width, y2+22], 
                                  fill=(0, 0, 128, 200))
                    draw.text((x1+2, y2+4), result_text, fill=(255, 255, 255))
        
        # Convert the image to bytes
        img_byte_arr = io.BytesIO()
        highlight_img.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        # Convert to base64 for displaying in browser
        img_base64 = base64.b64encode(img_byte_arr).decode('utf-8')
        
        return jsonify({"screenshot": img_base64})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/webhook_settings", methods=["GET", "POST"])
def manage_webhook_settings():
    global ocr_settings
    
    if request.method == "GET":
        return jsonify(ocr_settings["webhook"])
    
    elif request.method == "POST":
        data = request.json
        ocr_settings["webhook"]["enabled"] = data.get("enabled", False)
        ocr_settings["webhook"]["url"] = data.get("url", "")
        ocr_settings["webhook"]["biome_notifications"] = data.get("biome_notifications", True)
        ocr_settings["webhook"]["user_id"] = data.get("user_id", "")
        
        # Handle keywords
        if "keywords" in data:
            ocr_settings["webhook"]["keywords"] = data["keywords"]
        
        # Save settings to file
        with open(settings_file, 'w') as f:
            json.dump(ocr_settings, f)
        
        # Broadcast settings update via WebSocket
        socketio.emit('webhook_update', {'webhook': ocr_settings["webhook"]})
        
        return jsonify({"message": "Webhook settings saved successfully", "webhook": ocr_settings["webhook"]})

@app.route("/test_webhook", methods=["POST"])
def test_webhook():
    """Endpoint to test webhook with proper format for Discord"""
    data = request.json
    webhook_url = data.get("url", "")
    
    if not webhook_url:
        return jsonify({"success": False, "message": "No webhook URL provided"}), 400
    
    is_discord = "discord" in webhook_url.lower()
    
    try:
        timestamp = datetime.datetime.now().isoformat()
        
        if is_discord:
            # Format for Discord webhook
            payload = {
                "username": "OCR Biome Detector",
                "content": "**Test Webhook** - Biome detection system is working!",
                "embeds": [
                    {
                        "title": "Test Notification",
                        "description": "This is a test notification from the OCR Biome Detection system.",
                        "color": 3447003,  # Blue color
                        "timestamp": timestamp,
                        "fields": [
                            {
                                "name": "Test Region",
                                "value": "Test_Biome_Region",
                                "inline": True
                            },
                            {
                                "name": "Timestamp",
                                "value": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                "inline": True
                            }
                        ],
                        "footer": {
                            "text": "OCR Biome Detection System - Test"
                        }
                    }
                ]
            }
        else:
            # Generic webhook format
            payload = {
                "timestamp": timestamp,
                "region_name": "Test_Biome_Region",
                "detected_text": "This is a test webhook notification from the OCR system",
                "is_test": True
            }
        
        # Send the webhook request
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        # Log the response for debugging
        print(f"Test webhook response: {response.status_code}")
        response_text = response.text[:500]  # Truncate long responses
        print(f"Response content: {response_text}")
        
        if response.status_code >= 400:
            return jsonify({
                "success": False,
                "status_code": response.status_code,
                "message": f"Webhook test failed with status {response.status_code}",
                "response": response_text
            }), 500
            
        return jsonify({
            "success": True,
            "status_code": response.status_code,
            "message": "Webhook test successful"
        })
        
    except Exception as e:
        print(f"Test webhook error: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Error testing webhook: {str(e)}"
        }), 500

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
    
    print("Starting Macro Control Web App...")
    print(f"Local access: http://127.0.0.1:{port}/")
    print(f"Network access: http://{local_ip}:{port}/")
    print("(Press CTRL+C to quit)")
    
    socketio.run(app, host=host, port=port, debug=True, allow_unsafe_werkzeug=True)