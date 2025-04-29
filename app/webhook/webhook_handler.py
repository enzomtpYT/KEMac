import os
import json
import datetime
import time
import requests

from app.config import ocr_settings, log_dir, settings_dir
from app.utils.logger import get_logger

# Create a logger for the webhook handler
logger = get_logger(__name__, os.path.join(log_dir, "webhook.log"))

# File to store the last detected text and matched keywords for persistence
LAST_DETECTIONS_FILE = os.path.join(settings_dir, "last_detections.json")

# Dictionary to store the last webhook time for each region
last_webhook_time = {}

# Cooldown period in seconds before sending another webhook for the same region
WEBHOOK_COOLDOWN = 5  # 5 seconds cooldown

def load_last_detections():
    """Load the last detected data (text and matched keywords) for each region from the file"""
    if os.path.exists(LAST_DETECTIONS_FILE):
        try:
            with open(LAST_DETECTIONS_FILE, 'r') as f:
                content = f.read().strip()
                if not content:  # Handle empty file
                    logger.warning("Last detections file is empty")
                    return {}
                
                # Load the JSON data
                data = json.load(open(LAST_DETECTIONS_FILE, 'r'))
                
                # Convert old format (string values) to new format (dict values)
                # This ensures backward compatibility with existing last_detections.json files
                converted_data = {}
                for region_name, value in data.items():
                    if isinstance(value, str):
                        # Old format - convert to new format
                        converted_data[region_name] = {
                            "text": value,
                            "matched_keyword": None
                        }
                    else:
                        # New format - keep as is
                        converted_data[region_name] = value
                
                return converted_data
                
        except json.JSONDecodeError as e:
            logger.error("Error loading last detections: Invalid JSON - {}", str(e))
            # Backup the corrupted file for inspection
            backup_path = LAST_DETECTIONS_FILE + ".bak"
            try:
                if os.path.exists(LAST_DETECTIONS_FILE):
                    import shutil
                    shutil.copy2(LAST_DETECTIONS_FILE, backup_path)
                    logger.info("Backed up corrupted JSON file to {}", backup_path)
            except Exception as backup_err:
                logger.error("Failed to create backup of corrupted JSON: {}", str(backup_err))
        except Exception as e:
            logger.error("Error loading last detections: {}", str(e))
    return {}

def save_last_detection(region_name, text, matched_keyword_text=None):
    """Save the last detected text and matched keyword for a region to the file"""
    detections = load_last_detections()
    
    # Store both the text and the matched keyword
    if region_name not in detections:
        detections[region_name] = {}
    
    detections[region_name]["text"] = text
    
    # Only update the matched keyword if one was provided
    if matched_keyword_text is not None:
        detections[region_name]["matched_keyword"] = matched_keyword_text
    
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(LAST_DETECTIONS_FILE), exist_ok=True)
        
        with open(LAST_DETECTIONS_FILE, 'w') as f:
            json.dump(detections, f)
    except Exception as e:
        logger.error("Error saving last detection: {}", str(e))

def send_webhook(region_name, text):
    """Send webhook notification for biome regions when text matches keywords"""
    global last_webhook_time
    
    if not ocr_settings["webhook"]["enabled"] or not ocr_settings["webhook"]["url"]:
        logger.debug("Webhook not enabled or URL not set. Skipping.")
        return False
    
    if not ocr_settings["webhook"]["biome_notifications"]:
        logger.debug("Biome notifications not enabled. Skipping.")
        return False
    
    # Check if region name contains "biome" (case-insensitive)
    if "biome" not in region_name.lower():
        logger.debug("Region '{}' is not a biome region. Skipping webhook.", region_name)
        return False
    
    # Load previous detections from file for persistence
    last_detections = load_last_detections()
    
    # Check if there are keywords defined
    keywords = ocr_settings["webhook"].get("keywords", [])
    logger.debug("Keywords for webhook: {}", keywords)
    
    # Normalize detected text for comparison
    detected_text = text.lower()
    
    # Variables to track matches
    text_matched = False
    matching_keyword = None
    should_ping = False
    matched_keyword_text = None
    
    # If no keywords are defined, allow all text
    if not keywords:
        text_matched = True
        matched_keyword_text = "AllText"
        logger.info("No keywords defined, allowing all text")
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
                matched_keyword_text = keyword_text
                should_ping = keyword.get("ping", False)
                logger.info("OCR text in '{}' matched keyword: '{}'", region_name, keyword_text)
                break
    
    # If no keyword was matched and we have keywords defined, don't send webhook
    if not text_matched and keywords:
        logger.info("OCR text in '{}' did not match any keywords. Webhook not sent.", region_name)
        
        # Still save the detection to avoid repeated checks
        save_last_detection(region_name, text, None)
        return False
    
    # Check if this is the same keyword match as the last detection for this region
    if region_name in last_detections and \
       "matched_keyword" in last_detections[region_name] and \
       last_detections[region_name]["matched_keyword"] == matched_keyword_text:
        logger.debug("Same keyword '{}' matched in '{}' as previous detection. Skipping webhook.", 
                    matched_keyword_text, region_name)
        
        # Update the text but keep the same matched keyword
        save_last_detection(region_name, text, matched_keyword_text)
        return False
    
    # Check if we've recently sent a webhook for this region (cooldown period)
    current_time = time.time()
    if region_name in last_webhook_time:
        time_since_last_webhook = current_time - last_webhook_time[region_name]
        if time_since_last_webhook < WEBHOOK_COOLDOWN:
            logger.debug("Webhook for '{}' on cooldown. {:.1f} seconds remaining.", 
                      region_name, WEBHOOK_COOLDOWN - time_since_last_webhook)
            # Still save the detection even if on cooldown
            save_last_detection(region_name, text, matched_keyword_text)
            return False
    
    # Store the current time for cooldown
    last_webhook_time[region_name] = current_time
    
    # Store the current text and matched keyword for future comparison
    save_last_detection(region_name, text, matched_keyword_text)
    
    # Log webhook activity
    logger.info("Processing webhook for '{}' with text: '{}', matched keyword: '{}'", 
               region_name, text, matched_keyword_text)
    
    webhook_url = ocr_settings["webhook"]["url"]
    is_discord = "discord" in webhook_url.lower()
    user_id = ocr_settings["webhook"]["user_id"]
    
    # Get the cropped region image path
    debug_dir = os.path.join(settings_dir, "debug")
    original_image_path = os.path.join(debug_dir, f"{region_name}_original.png")
    
    # Generate a timestamp for the image filename
    current_time_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    try:
        timestamp = datetime.datetime.now().isoformat()
        
        if is_discord:
            # Format content with ping if required
            display_keyword = matching_keyword.get("text", "Unknown") if matching_keyword else "Matched"
            content = f"**{display_keyword}** detected in region **{region_name}**"
            
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
                                        "name": "Detected Text",
                                        "value": text,
                                        "inline": True
                                    },
                                    {
                                        "name": "Matched Keyword",
                                        "value": display_keyword,
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
                        "file": (f"{region_name}_{current_time_str}.png", img_file, "image/png")
                    }
                    
                    logger.info("Sending Discord webhook with image for '{}'", region_name)
                    
                    # Send the webhook request with file
                    response = requests.post(
                        webhook_url,
                        data={"payload_json": json.dumps(payload)},
                        files=files,
                        timeout=5  # Slightly longer timeout
                    )
            else:
                # If image doesn't exist, send without attachment
                logger.warning("Image not found: {}", original_image_path)
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
                                    "name": "Detected Text",
                                    "value": text,
                                    "inline": True
                                },
                                {
                                    "name": "Matched Keyword",
                                    "value": display_keyword,
                                    "inline": True
                                }
                            ],
                            "footer": {
                                "text": "OCR Biome Detection System"
                            }
                        }
                    ]
                }
                
                logger.info("Sending Discord webhook without image for '{}'", region_name)
                
                # Send the webhook request
                response = requests.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=5
                )
        else:
            # Generic webhook format
            display_keyword = matching_keyword.get("text", "Unknown") if matching_keyword else "Matched"
            
            payload = {
                "timestamp": timestamp,
                "region_name": region_name,
                "detected_text": text,
                "detected_keyword": display_keyword
            }
            
            logger.info("Sending generic webhook for '{}'", region_name)
            
            # Send the webhook request
            response = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5  # Slightly longer timeout
            )
        
        # Log the response
        logger.info("Webhook sent for biome region '{}': {}", region_name, response.status_code)
        
        # If there was an error, log the response content
        if response.status_code >= 400:
            logger.error("Webhook error response: {}", response.text)
            
        return response.status_code < 400  # Return success if status code < 400
    
    except Exception as e:
        logger.error("Webhook error for biome region '{}': {}", region_name, str(e))
        return False