import os
import io
import threading
import time
import datetime
import base64
from PIL import ImageGrab, Image, ImageEnhance, ImageFilter, ImageDraw
import pytesseract

from app.config import socketio, ocr_settings, ocr_results, macro_status, stop_ocr_thread, MIN_OCR_WIDTH, MIN_OCR_HEIGHT, settings_dir
from app.webhook.webhook_handler import send_webhook

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
    global stop_ocr_thread
    
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