import os
import io
import threading
import time
import datetime
import base64
import numpy as np
from PIL import ImageGrab, Image, ImageEnhance, ImageFilter, ImageDraw, ImageOps
import pytesseract
import cv2
import re

from app.config import socketio, ocr_settings, ocr_results, macro_status, stop_ocr_thread, MIN_OCR_WIDTH, MIN_OCR_HEIGHT, settings_dir, status_file
from app.webhook.webhook_handler import send_webhook

def preprocess_image_for_ocr(img):
    """Apply advanced preprocessing to improve OCR accuracy"""
    # Try multiple preprocessing techniques and combine them
    methods = []
    
    # First convert to numpy array for OpenCV processing if needed
    np_img = np.array(img)
    
    # Method 1: High contrast with adaptive thresholding
    img1 = img.copy()
    enhancer = ImageEnhance.Contrast(img1)
    img1 = enhancer.enhance(3.0)  # Increased contrast
    img1 = img1.convert('L')  # Convert to grayscale
    img1 = img1.point(lambda x: 0 if x < 140 else 255, '1')  # Binary threshold
    methods.append(img1)
    
    # Method 2: Sharpening with different threshold and noise reduction
    img2 = img.copy()
    img2 = img2.convert('L')  # Convert to grayscale first
    enhancer = ImageEnhance.Sharpness(img2)
    img2 = enhancer.enhance(3.0)  # Increased sharpness
    enhancer = ImageEnhance.Contrast(img2)
    img2 = enhancer.enhance(2.5)  # Also increase contrast
    img2 = img2.filter(ImageFilter.SHARPEN)
    img2 = img2.filter(ImageFilter.MedianFilter(3))  # Remove noise
    img2 = img2.point(lambda x: 0 if x < 150 else 255, '1')
    methods.append(img2)
    
    # Method 3: Edge enhancement with bilateral filtering (via OpenCV)
    cv_img = np.array(img.convert('RGB'))
    # Convert BGR to RGB if needed
    if len(cv_img.shape) == 3 and cv_img.shape[2] == 3:
        cv_img = cv2.cvtColor(cv_img, cv2.COLOR_RGB2GRAY)
    # Apply bilateral filter to preserve edges while reducing noise
    cv_img = cv2.bilateralFilter(cv_img, 9, 75, 75)
    # Apply adaptive thresholding
    cv_img = cv2.adaptiveThreshold(cv_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                  cv2.THRESH_BINARY, 11, 2)
    img3 = Image.fromarray(cv_img)
    methods.append(img3)
    
    # Method 4: Inverted color scheme for light text on dark background
    img4 = img.copy()
    img4 = img4.convert('L')
    enhancer = ImageEnhance.Contrast(img4)
    img4 = enhancer.enhance(2.5)
    img4 = ImageOps.invert(img4)  # Invert colors
    img4 = img4.point(lambda x: 0 if x < 140 else 255, '1')
    methods.append(img4)
    
    # Method 5: Denoising with morphological operations (via OpenCV)
    cv_img2 = np.array(img.convert('RGB'))
    if len(cv_img2.shape) == 3 and cv_img2.shape[2] == 3:
        cv_img2 = cv2.cvtColor(cv_img2, cv2.COLOR_RGB2GRAY)
    # Apply Gaussian blur to remove noise
    cv_img2 = cv2.GaussianBlur(cv_img2, (5, 5), 0)
    # Apply Otsu's thresholding
    _, cv_img2 = cv2.threshold(cv_img2, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Apply morphological operations to clean up
    kernel = np.ones((2, 2), np.uint8)
    cv_img2 = cv2.morphologyEx(cv_img2, cv2.MORPH_OPEN, kernel)
    img5 = Image.fromarray(cv_img2)
    methods.append(img5)
    
    # Method 6: Color filtering for text enhancement
    img6 = img.copy()
    # Enhance specific color channels if the image is RGB
    if img6.mode == 'RGB':
        r, g, b = img6.split()
        # Enhance the channel with strongest text color contrast
        enhancer = ImageEnhance.Contrast(g)  # Often green has good contrast
        g = enhancer.enhance(2.5)
        img6 = Image.merge('RGB', (r, g, b))
    img6 = img6.convert('L')
    img6 = img6.filter(ImageFilter.EDGE_ENHANCE_MORE)
    img6 = img6.point(lambda x: 0 if x < 155 else 255, '1')
    methods.append(img6)
    
    return methods

def get_current_status():
    """Read the current macro status from the status file"""
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r') as f:
                saved_status = f.read().strip()
                if saved_status in ["running", "paused", "stopped"]:
                    return saved_status
        except Exception as e:
            print(f"Error reading status file: {str(e)}")
    return "stopped"  # Default if file doesn't exist or has invalid content

def is_valid_text(text, min_confidence=40):
    """
    Check if detected text is valid or just random patterns.
    
    Args:
        text (str): The text to validate
        min_confidence (int): Minimum confidence threshold
        
    Returns:
        bool: True if text appears valid, False otherwise
    """
    # Skip empty text
    if not text or text.strip() == "":
        return False
        
    # If text is very short, require higher confidence
    if len(text) <= 3:
        min_confidence = 60
    
    # Check if text contains mostly valid characters (not random symbols)
    valid_chars = sum(c.isalnum() or c.isspace() or c in '.,;:-()[]{}!?"/\'"' for c in text)
    valid_char_ratio = valid_chars / len(text) if text else 0
    
    # Check if text has reasonable word patterns 
    # (most texts have at least some letter sequences that make linguistic sense)
    word_pattern_score = 0
    words = re.split(r'[\s\n\t.,;:!?()\[\]{}]+', text)
    for word in words:
        if len(word) > 1:
            # Look for vowel-consonant patterns that are common in natural language
            vowels = sum(1 for c in word.lower() if c in 'aeiou')
            vowel_ratio = vowels / len(word)
            
            # Words with no vowels or all vowels are less likely to be real words
            if 0.1 <= vowel_ratio <= 0.7:
                word_pattern_score += 1
    
    word_score_ratio = word_pattern_score / len(words) if words else 0
    
    # Check for repeated patterns that suggest noise rather than text
    repeated_chars = 0
    if len(text) > 3:
        prev_char = text[0]
        streak = 1
        for c in text[1:]:
            if c == prev_char:
                streak += 1
                if streak > 2:
                    repeated_chars += 1
            else:
                streak = 1
                prev_char = c
    
    repeated_ratio = repeated_chars / len(text) if text else 0
    
    # Calculate overall confidence score (0-100)
    confidence_score = (
        valid_char_ratio * 50 +          # 0-50 points for valid character ratio
        word_score_ratio * 30 +          # 0-30 points for realistic word patterns
        (1 - repeated_ratio) * 20        # 0-20 points for lack of repetition
    )
    
    # Return True if confidence exceeds threshold
    return confidence_score >= min_confidence

def perform_ocr():
    """Thread function to perform OCR at regular intervals"""
    global stop_ocr_thread
    
    print("OCR thread started - waiting for processing tasks")
    
    while get_current_status() == "running" and not stop_ocr_thread:
        # Check if OCR is enabled and regions are defined
        if not ocr_settings["enabled"]:
            # OCR is disabled but thread is running, just wait
            time.sleep(1)
            continue
            
        if not ocr_settings["regions"]:
            # No regions defined, just wait
            time.sleep(1)
            continue
            
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
                    
                    # Check if the image has enough contrast/detail to contain text
                    img_array = np.array(region_img.convert('L'))
                    std_dev = np.std(img_array)
                    if std_dev < 10:  # Very low variance suggests a plain/empty region
                        print(f"Region '{region_name}' has very low variance (std_dev={std_dev:.2f}), likely no text.")
                        ocr_results[region_name] = "(No text detected)"
                        continue
                    
                    # Always apply upscaling for better OCR results - even for larger regions
                    # Use higher scale factor for smaller regions
                    if width < 100 or height < 30:
                        scale_factor = 4  # Use higher scale factor for very small regions
                    else:
                        scale_factor = 2  # Use moderate scaling for larger regions
                    
                    # Use LANCZOS resampling for better quality
                    region_img = region_img.resize((width * scale_factor, height * scale_factor), Image.LANCZOS)
                    
                    # Apply multiple preprocessing methods
                    processed_imgs = preprocess_image_for_ocr(region_img)
                    
                    # Save debug images
                    for idx, processed_img in enumerate(processed_imgs):
                        debug_file = os.path.join(debug_dir, f"{region_name}_method{idx+1}.png")
                        processed_img.save(debug_file)
                    
                    # Enhanced OCR configurations with different parameters - removed legacy engine modes (--oem 0)
                    ocr_configs = [
                        '--psm 7 --oem 1',  # Single line of text with LSTM engine
                        '--psm 6 --oem 1',  # Assume a single uniform block of text with LSTM engine
                        '--psm 8 --oem 1',  # Single word with LSTM engine
                        '--psm 4 --oem 1',  # Assume single column of text of variable sizes with LSTM engine
                        '--psm 3 --oem 1 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,-:;(){}[]<>!@#$%^&*+=/\\|"\'?_ ',
                        '--psm 6 --oem 3',  # Default mode with both engines
                        '--psm 6 -l eng --oem 1'  # Specify English language explicitly
                    ]
                    
                    # Find the best OCR result
                    best_text = ""
                    best_config = ""
                    best_method = 0
                    best_confidence = 0
                    min_tesseract_conf = 30  # Minimum required Tesseract confidence score
                    
                    for idx, processed_img in enumerate(processed_imgs):
                        for config in ocr_configs:
                            try:
                                # Use image_to_data to get confidence scores
                                data = pytesseract.image_to_data(processed_img, config=config, output_type=pytesseract.Output.DICT)
                                
                                # Get words with their confidences
                                text_candidates = []
                                total_conf = 0
                                valid_words = 0
                                
                                for j in range(len(data['text'])):
                                    conf = int(data['conf'][j])
                                    word = data['text'][j].strip()
                                    
                                    # Only include words with decent confidence
                                    if conf > min_tesseract_conf and word and len(word) > 1:
                                        text_candidates.append(word)
                                        total_conf += conf
                                        valid_words += 1
                                
                                if valid_words > 0:
                                    text = " ".join(text_candidates)
                                    avg_conf = total_conf / valid_words if valid_words > 0 else 0
                                    
                                    # Skip empty results
                                    if not text:
                                        continue
                                    
                                    # Skip if text doesn't pass our validity check
                                    if not is_valid_text(text):
                                        continue
                                    
                                    # Calculate a more sophisticated confidence score
                                    confidence_score = avg_conf * len(text) / 10
                                    
                                    # Check if this text is better than what we have
                                    if confidence_score > best_confidence:
                                        best_text = text
                                        best_config = config
                                        best_method = idx + 1
                                        best_confidence = confidence_score
                            except Exception as e:
                                print(f"Error with OCR config {config} on method {idx+1}: {str(e)}")
                                continue
                    
                    # If no valid text was detected, report it
                    if not best_text:
                        best_text = "(No text detected)"
                        
                    # Log metadata about the detection
                    print(f"OCR Result for {region_name} ({width}x{height}):")
                    print(f"Best method: {best_method}, Config: {best_config}")
                    print(f"Confidence: {best_confidence:.1f}")
                    print(f"Text: {best_text}")
                    print("-" * 40)
                    
                    # Save result
                    ocr_results[region_name] = best_text.strip()
                    
                    # Send webhook for biome regions
                    if "biome" in region_name.lower() and best_text != "(No text detected)" and ocr_settings["webhook"]["enabled"] and ocr_settings["webhook"]["url"]:
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