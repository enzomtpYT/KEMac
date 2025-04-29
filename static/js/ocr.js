// OCR Settings and functionality
let ocrSettings = {
    enabled: false,
    regions: []
};

// Handle toggle OCR setting
document.addEventListener('DOMContentLoaded', function() {
    const ocrEnabledToggle = document.getElementById('ocr-enabled');
    if (ocrEnabledToggle) {
        ocrEnabledToggle.addEventListener('change', function() {
            ocrSettings.enabled = this.checked;
            
            fetch('/ocr_settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(ocrSettings)
            })
            .then(response => response.json())
            .then(data => {
                console.log('OCR settings updated:', data);
            });
        });
    }
});

// Function to load OCR settings
function loadOcrSettings() {
    fetch('/ocr_settings')
        .then(response => response.json())
        .then(data => {
            ocrSettings = data;
            document.getElementById('ocr-enabled').checked = ocrSettings.enabled;
            renderRegionsList();
        });
}

// Function to take screenshot (for region selection)
function takeScreenshot() {
    fetch('/screenshot')
        .then(response => response.json())
        .then(data => {
            currentScreenshot = data.screenshot;
            const img = document.getElementById('screenshotImg');
            img.src = 'data:image/png;base64,' + data.screenshot;
            
            // Enable selection after screenshot is loaded
            img.onload = function() {
                setupScreenshotSelection();
            };
        });
}

// Function to set up screenshot selection
function setupScreenshotSelection() {
    const container = document.getElementById('screenshotContainer');
    const img = document.getElementById('screenshotImg');
    const selectionBox = document.getElementById('selectionBox');
    
    // Remove previous listeners if any
    container.onmousedown = null;
    container.onmousemove = null;
    container.onmouseup = null;
    document.removeEventListener('mouseup', handleMouseUp);
    
    // Create a transparent overlay for capturing events
    let overlay = document.getElementById('selection-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'selection-overlay';
        overlay.style.position = 'absolute';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100%';
        overlay.style.height = '100%';
        overlay.style.zIndex = '10';
        container.appendChild(overlay);
    }
    
    // Handle mouse down
    overlay.onmousedown = function(e) {
        e.preventDefault(); // Prevent default browser behavior
        isSelecting = true;
        
        // Get coordinates relative to the container
        const rect = container.getBoundingClientRect();
        startX = e.clientX - rect.left;
        startY = e.clientY - rect.top;
        
        // Position the selection box
        selectionBox.style.left = startX + 'px';
        selectionBox.style.top = startY + 'px';
        selectionBox.style.width = '0px';
        selectionBox.style.height = '0px';
        selectionBox.style.display = 'block';
    };
    
    // Handle mouse move
    overlay.onmousemove = function(e) {
        if (!isSelecting) return;
        e.preventDefault(); // Prevent default browser behavior
        
        const rect = container.getBoundingClientRect();
        const currentX = e.clientX - rect.left;
        const currentY = e.clientY - rect.top;
        
        // Calculate dimensions
        const width = currentX - startX;
        const height = currentY - startY;
        
        // Update selection box
        if (width > 0) {
            selectionBox.style.width = width + 'px';
        } else {
            selectionBox.style.left = currentX + 'px';
            selectionBox.style.width = (startX - currentX) + 'px';
        }
        
        if (height > 0) {
            selectionBox.style.height = height + 'px';
        } else {
            selectionBox.style.top = currentY + 'px';
            selectionBox.style.height = (startY - currentY) + 'px';
        }
    };
    
    function handleMouseUp(e) {
        if (!isSelecting) return;
        e.preventDefault(); // Prevent default browser behavior
        
        // Only process if the event happened in the overlay
        const rect = container.getBoundingClientRect();
        if (e.clientX < rect.left || e.clientX > rect.right || 
            e.clientY < rect.top || e.clientY > rect.bottom) {
            // Click outside the container, cancel selection
            selectionBox.style.display = 'none';
            isSelecting = false;
            return;
        }
        
        isSelecting = false;
        
        const currentX = e.clientX - rect.left;
        const currentY = e.clientY - rect.top;
        
        // Calculate actual coordinates (adjust for negative selections)
        let x1 = Math.min(startX, currentX);
        let y1 = Math.min(startY, currentY);
        let x2 = Math.max(startX, currentX);
        let y2 = Math.max(startY, currentY);
        
        // Calculate width and height
        const width = x2 - x1;
        const height = y2 - y1;
        
        // Check if region is too small
        const MIN_SIZE = 10;
        if (width < MIN_SIZE || height < MIN_SIZE) {
            alert(`Region is too small (${width}x${height} pixels). Please select a region at least ${MIN_SIZE}x${MIN_SIZE} pixels.`);
            selectionBox.style.display = 'none';
            return;
        }
        
        // Show form to save the region
        document.getElementById('region-form').style.display = 'block';
        document.getElementById('selection-coords').innerText = 
            `Coordinates: (${Math.round(x1)}, ${Math.round(y1)}) to (${Math.round(x2)}, ${Math.round(y2)})`;
        document.getElementById('selection-coords').innerHTML += `<br>Size: ${Math.round(width)}x${Math.round(height)} pixels`;
        
        // Calculate scaling factor between displayed image and actual screenshot
        const scaleX = img.naturalWidth / img.clientWidth;
        const scaleY = img.naturalHeight / img.clientHeight;
        
        // Store actual screen coordinates (adjust for image scaling)
        document.getElementById('region-form').dataset.x1 = Math.round(x1 * scaleX);
        document.getElementById('region-form').dataset.y1 = Math.round(y1 * scaleY);
        document.getElementById('region-form').dataset.x2 = Math.round(x2 * scaleX);
        document.getElementById('region-form').dataset.y2 = Math.round(y2 * scaleY);
    }
    
    // Handle mouse up both on the overlay and globally to catch dragging outside
    overlay.onmouseup = handleMouseUp;
    document.addEventListener('mouseup', handleMouseUp);
}

// Function to save the selected region
function saveRegion() {
    const form = document.getElementById('region-form');
    const name = document.getElementById('region-name').value || 'Unnamed Region';
    
    const region = {
        name: name,
        x1: parseInt(form.dataset.x1),
        y1: parseInt(form.dataset.y1),
        x2: parseInt(form.dataset.x2),
        y2: parseInt(form.dataset.y2)
    };
    
    fetch('/add_ocr_region', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(region)
    })
    .then(response => response.json())
    .then(data => {
        console.log('Region saved:', data);
        ocrSettings = data.settings;
        renderRegionsList();
        
        // Reset the form
        document.getElementById('region-form').style.display = 'none';
        document.getElementById('region-name').value = '';
        document.getElementById('selectionBox').style.display = 'none';
        
        // Request a new screenshot via WebSocket to show the new region
        if (socket && socket.connected) {
            socket.emit('request_screenshot');
        }
    });
}

// Function to delete a region
function deleteRegion(index) {
    fetch('/delete_ocr_region', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ index: index })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Region deleted:', data);
        ocrSettings = data.settings;
        renderRegionsList();
        
        // Request a new screenshot via WebSocket to reflect the deleted region
        if (socket && socket.connected) {
            socket.emit('request_screenshot');
        }
    });
}

// Function to render the list of regions
function renderRegionsList() {
    const list = document.getElementById('regions-list');
    list.innerHTML = '';
    
    if (ocrSettings.regions.length === 0) {
        list.innerHTML = '<p>No OCR regions defined. Take a screenshot and select a region.</p>';
        return;
    }
    
    ocrSettings.regions.forEach((region, index) => {
        const item = document.createElement('div');
        item.className = 'region-item';
        
        const info = document.createElement('div');
        info.innerHTML = `
            <strong>${region.name}</strong>
            <div class="coordinates">
                (${region.x1}, ${region.y1}) to (${region.x2}, ${region.y2})
            </div>
        `;
        
        const deleteBtn = document.createElement('span');
        deleteBtn.className = 'region-delete';
        deleteBtn.innerText = 'Delete';
        deleteBtn.onclick = function() {
            deleteRegion(index);
        };
        
        item.appendChild(info);
        item.appendChild(deleteBtn);
        list.appendChild(item);
    });
}

// Function to verify Tesseract installation
function verifyTesseract() {
    const statusDiv = document.getElementById('tesseract-status');
    statusDiv.innerHTML = "Checking Tesseract installation...";
    statusDiv.style.display = "block";
    statusDiv.style.backgroundColor = "#f8f9fa";
    
    fetch('/verify_tesseract')
        .then(response => response.json())
        .then(data => {
            let statusHtml = '';
            
            if (data.installed && data.test_passed) {
                statusHtml = `
                    <div style="color: green; font-weight: bold;">✓ Tesseract is properly installed</div>
                    <div>Path: ${data.path}</div>
                    <div>Version: ${data.version}</div>
                    <div style="margin-top: 10px;">OCR functionality is working correctly.</div>
                `;
                statusDiv.style.backgroundColor = "#e7f7e7";
            } else {
                statusHtml = `
                    <div style="color: red; font-weight: bold;">✗ Tesseract installation issue detected</div>
                `;
                
                if (data.path) {
                    statusHtml += `<div>Configured path: ${data.path}</div>`;
                }
                
                if (data.error) {
                    statusHtml += `<div>Error: ${data.error}</div>`;
                }
                
                if (data.installed && !data.test_passed && data.test_error) {
                    statusHtml += `<div>Tesseract is installed but the test failed: ${data.test_error}</div>`;
                }
                
                statusHtml += `
                    <div style="margin-top: 10px;">
                        <strong>Troubleshooting steps:</strong>
                        <ol>
                            <li>Ensure Tesseract OCR is installed on your system</li>
                            <li>Make sure the path in the code matches your installation path</li>
                            <li>Verify that you have the necessary language data files installed</li>
                            <li>Try restarting the application</li>
                        </ol>
                    </div>
                `;
                statusDiv.style.backgroundColor = "#ffebee";
            }
            
            statusDiv.innerHTML = statusHtml;
        })
        .catch(error => {
            statusDiv.style.backgroundColor = "#ffebee";
            statusDiv.innerHTML = `<div style="color: red;">Error checking Tesseract: ${error}</div>`;
        });
}