import os
import json
import pytesseract
from PIL import Image, ImageDraw, ImageGrab
import io
import base64
from flask import request, jsonify

from app.config import flask_app, socketio, ocr_settings, ocr_results, settings_file, log_dir
from app.utils.logger import get_logger

# Create a logger for this module
logger = get_logger(__name__, os.path.join(log_dir, "routes.log"))

@flask_app.route("/ocr_settings", methods=["GET", "POST"])
def manage_ocr_settings():
    global ocr_settings
    
    if request.method == "GET":
        logger.debug("OCR settings requested")
        return jsonify(ocr_settings)
    
    elif request.method == "POST":
        data = request.json
        ocr_settings["enabled"] = data.get("enabled", False)
        ocr_settings["regions"] = data.get("regions", [])
        
        # Save settings to file with proper indentation
        try:
            with open(settings_file, 'w') as f:
                json.dump(ocr_settings, f, indent=4)
            logger.info("OCR settings saved successfully")
        except Exception as e:
            logger.error("Failed to save OCR settings: {}", str(e))
            return jsonify({"error": f"Failed to save settings: {str(e)}"}), 500
        
        # Broadcast settings update via WebSocket
        socketio.emit('settings_update', {'settings': ocr_settings})
        
        return jsonify({"message": "OCR settings saved successfully", "settings": ocr_settings})

@flask_app.route("/add_ocr_region", methods=["POST"])
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
    
    # Save settings to file with proper indentation
    try:
        with open(settings_file, 'w') as f:
            json.dump(ocr_settings, f, indent=4)
        logger.info("Added new OCR region: {}", new_region['name'])
    except Exception as e:
        logger.error("Failed to save OCR region: {}", str(e))
        return jsonify({"error": f"Failed to save region: {str(e)}"}), 500
    
    # Broadcast settings update via WebSocket
    socketio.emit('settings_update', {'settings': ocr_settings})
    
    return jsonify({"message": "OCR region added", "region": new_region, "settings": ocr_settings})

@flask_app.route("/delete_ocr_region", methods=["POST"])
def delete_ocr_region():
    global ocr_settings
    
    data = request.json
    index = data.get("index")
    
    if 0 <= index < len(ocr_settings["regions"]):
        removed = ocr_settings["regions"].pop(index)
        
        # Save settings to file with proper indentation
        try:
            with open(settings_file, 'w') as f:
                json.dump(ocr_settings, f, indent=4)
            logger.info("Deleted OCR region: {}", removed['name'])
        except Exception as e:
            logger.error("Failed to save after deleting region: {}", str(e))
            return jsonify({"error": f"Failed to save changes: {str(e)}"}), 500
        
        # Broadcast settings update via WebSocket
        socketio.emit('settings_update', {'settings': ocr_settings})
        
        return jsonify({"message": f"OCR region '{removed['name']}' deleted", "settings": ocr_settings})
    
    logger.warning("Invalid region index: {}", index)
    return jsonify({"message": "Invalid region index", "settings": ocr_settings}), 400

@flask_app.route("/ocr_results", methods=["GET"])
def get_ocr_results():
    """API endpoint to get the latest OCR results"""
    logger.debug("OCR results requested")
    return jsonify(ocr_results)

@flask_app.route("/verify_tesseract", methods=["GET"])
def verify_tesseract():
    """Endpoint to verify Tesseract installation and configuration"""
    logger.info("Verifying Tesseract installation")
    
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
            error_msg = f"Tesseract executable not found at: {tesseract_path}"
            logger.error(error_msg)
            result["error"] = error_msg
            return jsonify(result)
        
        # Try to get tesseract version
        version_info = pytesseract.get_tesseract_version()
        result["version"] = str(version_info)
        result["installed"] = True
        logger.info("Tesseract verified - version: {}", version_info)
        
        # Create a simple test image with text
        test_img = Image.new('RGB', (100, 30), color=(255, 255, 255))
        
        # Test OCR functionality
        try:
            pytesseract.image_to_string(test_img)
            result["test_passed"] = True
            logger.info("OCR test passed")
        except Exception as e:
            result["test_passed"] = False
            result["test_error"] = str(e)
            logger.error("OCR test failed: {}", str(e))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error("Error verifying tesseract: {}", str(e))
        result["error"] = str(e)
        return jsonify(result)

@flask_app.route("/highlighted_screenshot", methods=["GET"])
def get_highlighted_screenshot():
    """Generate and return a screenshot with OCR regions highlighted"""
    logger.debug("Generating highlighted screenshot")
    
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
        error_msg = f"Error generating highlighted screenshot: {str(e)}"
        logger.error(error_msg)
        return jsonify({"error": error_msg}), 500