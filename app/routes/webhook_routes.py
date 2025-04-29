import os
import json
import datetime
import requests
from flask import request, jsonify

from app.config import flask_app, socketio, ocr_settings, settings_file

@flask_app.route("/webhook_settings", methods=["GET", "POST"])
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
        
        # Save settings to file with proper indentation
        with open(settings_file, 'w') as f:
            json.dump(ocr_settings, f, indent=4)
        
        # Broadcast settings update via WebSocket
        socketio.emit('webhook_update', {'webhook': ocr_settings["webhook"]})
        
        return jsonify({"message": "Webhook settings saved successfully", "webhook": ocr_settings["webhook"]})

@flask_app.route("/test_webhook", methods=["POST"])
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