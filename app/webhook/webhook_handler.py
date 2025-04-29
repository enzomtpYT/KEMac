import os
import json
import datetime
import requests

from app.config import ocr_settings, settings_dir

# File to store last detected text for persistence between runs
last_detections_file = os.path.join(settings_dir, "last_detections.json")

# Dictionary to store the last detected text for each region
last_detected_text = {}

# Load last detections from file if it exists
def load_last_detections():
    global last_detected_text
    if os.path.exists(last_detections_file):
        try:
            with open(last_detections_file, 'r') as f:
                last_detected_text = json.load(f)
                print(f"Loaded {len(last_detected_text)} previous detections from file")
        except Exception as e:
            print(f"Error loading last detections: {str(e)}")
            last_detected_text = {}

# Save last detections to file for persistence
def save_last_detections():
    try:
        with open(last_detections_file, 'w') as f:
            json.dump(last_detected_text, f)
    except Exception as e:
        print(f"Error saving last detections: {str(e)}")

# Load last detections when the module is imported
load_last_detections()

def send_webhook(region_name, text):
    """Send webhook notification for biome regions when text matches keywords"""
    global last_detected_text
    
    if not ocr_settings["webhook"]["enabled"] or not ocr_settings["webhook"]["url"]:
        return False
    
    if not ocr_settings["webhook"]["biome_notifications"]:
        return False
    
    # Check if region name contains "biome" (case-insensitive)
    if "biome" not in region_name.lower():
        return False
    
    # Check if this is the same text as the last detection for this region
    if region_name in last_detected_text and last_detected_text[region_name] == text:
        print(f"Same text detected in '{region_name}' as previous detection. Skipping webhook.")
        return False
    
    # Store the current text for future comparison and persist to file
    last_detected_text[region_name] = text
    save_last_detections()
    
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