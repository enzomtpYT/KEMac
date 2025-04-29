// Main initialization and utility functions
let socket;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeTheme();
    loadWebhookSettings();
});

// Connect to WebSocket server when page loads
window.onload = function() {
    initializeTheme(); // Also initialize theme on window load
    connectWebSocket();
    loadOcrSettings();
};

// Function to connect to WebSocket
function connectWebSocket() {
    // Connect to the same host that served this page
    socket = io();
    
    // Socket connection events
    socket.on('connect', function() {
        console.log('Connected to server');
        updateConnectionStatus(true);
    });
    
    socket.on('disconnect', function() {
        console.log('Disconnected from server');
        updateConnectionStatus(false);
    });
    
    socket.on('connect_error', function(err) {
        console.error('Connection error:', err);
        updateConnectionStatus(false);
    });
    
    // Listen for status updates
    socket.on('status_update', function(data) {
        updateStatusDisplay(data.status);
    });
    
    // Listen for OCR results updates
    socket.on('ocr_update', function(data) {
        updateOcrResults(data.results);
        if (data.timestamp) {
            document.getElementById('timestamp-display').innerText = 'Last updated: ' + data.timestamp;
        }
    });
    
    // Listen for screenshot updates
    socket.on('screenshot_update', function(data) {
        updateScreenshot(data.screenshot);
    });
    
    // Listen for settings updates
    socket.on('settings_update', function(data) {
        ocrSettings = data.settings;
        document.getElementById('ocr-enabled').checked = ocrSettings.enabled;
        renderRegionsList();
    });
    
    // Listen for error messages with enhanced display
    socket.on('error', function(data) {
        console.error('Server error:', data.message);
        // Display error notification to the user
        showNotification(data.message, 'error');
    });

    // Listen for webhook settings updates via WebSocket
    socket.on('webhook_update', function(data) {
        document.getElementById('webhook-enabled').checked = data.webhook.enabled;
        document.getElementById('webhook-url').value = data.webhook.url;
        document.getElementById('biome-notifications').checked = data.webhook.biome_notifications;
        document.getElementById('user-id').value = data.webhook.user_id || '';
        renderKeywords(data.webhook.keywords || []);
    });
}

// Show notification to user
function showNotification(message, type = 'info') {
    // Check if notification container exists, if not, create it
    let notificationContainer = document.getElementById('notification-container');
    if (!notificationContainer) {
        notificationContainer = document.createElement('div');
        notificationContainer.id = 'notification-container';
        notificationContainer.style.position = 'fixed';
        notificationContainer.style.top = '20px';
        notificationContainer.style.left = '50%';
        notificationContainer.style.transform = 'translateX(-50%)';
        notificationContainer.style.zIndex = '1000';
        notificationContainer.style.width = '80%';
        notificationContainer.style.maxWidth = '500px';
        document.body.appendChild(notificationContainer);
    }
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = 'notification ' + type;
    notification.style.padding = '12px 20px';
    notification.style.margin = '10px 0';
    notification.style.borderRadius = '5px';
    notification.style.boxShadow = '0 2px 4px rgba(0,0,0,0.2)';
    notification.style.position = 'relative';
    notification.style.opacity = '0';
    notification.style.transition = 'opacity 0.3s ease-in-out';
    
    // Style based on type
    if (type === 'error') {
        notification.style.backgroundColor = '#ffebee';
        notification.style.color = '#d32f2f';
        notification.style.border = '1px solid #ffcdd2';
    } else {
        notification.style.backgroundColor = '#e8f5e9';
        notification.style.color = '#388e3c';
        notification.style.border = '1px solid #c8e6c9';
    }
    
    // Add message
    notification.textContent = message;
    
    // Add close button
    const closeButton = document.createElement('span');
    closeButton.innerHTML = '&times;';
    closeButton.style.position = 'absolute';
    closeButton.style.right = '10px';
    closeButton.style.top = '10px';
    closeButton.style.cursor = 'pointer';
    closeButton.style.fontWeight = 'bold';
    closeButton.onclick = function() {
        notificationContainer.removeChild(notification);
    };
    notification.appendChild(closeButton);
    
    // Add to container
    notificationContainer.appendChild(notification);
    
    // Animate in
    setTimeout(() => {
        notification.style.opacity = '1';
    }, 10);
    
    // Remove after 5 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => {
            try {
                notificationContainer.removeChild(notification);
            } catch (e) {
                // Notification might have been manually closed
            }
        }, 300);
    }, 5000);
}

// Function to update connection status display
function updateConnectionStatus(connected) {
    const indicator = document.getElementById('connection-indicator');
    const text = document.getElementById('connection-text');
    
    if (connected) {
        indicator.className = 'connected';
        text.innerText = 'Connected';
    } else {
        indicator.className = 'disconnected';
        text.innerText = 'Disconnected';
    }
}

// Function to request a fresh screenshot
function requestScreenshot() {
    if (!socket || !socket.connected) {
        console.error('Not connected to server');
        return;
    }
    
    // Show loading indicator
    document.getElementById('screenshot-loading').style.display = 'flex';
    
    // Request screenshot via WebSocket
    socket.emit('request_screenshot');
}

// Function to request current OCR results
function requestOcrResults() {
    if (!socket || !socket.connected) {
        console.error('Not connected to server');
        return;
    }
    
    socket.emit('request_ocr_results');
}

// Function to update the screenshot display
function updateScreenshot(base64Image) {
    const img = document.getElementById('live-screenshot');
    img.src = 'data:image/png;base64,' + base64Image;
    
    // Hide loading after image loads
    img.onload = function() {
        document.getElementById('screenshot-loading').style.display = 'none';
    };
}

// Function to switch tabs
function switchTab(tabId) {
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    
    if (tabId === 'control') {
        document.querySelector('.tab:nth-child(1)').classList.add('active');
        document.getElementById('control-tab').classList.add('active');
        // Refresh data when switching to control tab
        requestScreenshot();
        requestOcrResults();
    } else if (tabId === 'ocr-settings') {
        document.querySelector('.tab:nth-child(2)').classList.add('active');
        document.getElementById('ocr-settings-tab').classList.add('active');
    } else if (tabId === 'webhook-settings') {
        document.querySelector('.tab:nth-child(3)').classList.add('active');
        document.getElementById('webhook-settings-tab').classList.add('active');
    }
}

// Function to update status display
function updateStatusDisplay(status) {
    const statusDisplay = document.getElementById('status-display');
    statusDisplay.className = 'status ' + status;
    statusDisplay.innerText = 'Status: ' + status.charAt(0).toUpperCase() + status.slice(1);
    
    // Update button states
    updateButtonStates(status);
}

// Function to update button states based on macro status
function updateButtonStates(status) {
    const startBtn = document.getElementById('start-btn');
    const pauseBtn = document.getElementById('pause-btn');
    const stopBtn = document.getElementById('stop-btn');
    
    switch(status) {
        case 'stopped':
            startBtn.disabled = false;
            pauseBtn.disabled = true;
            stopBtn.disabled = true;
            break;
        case 'running':
            startBtn.disabled = true;
            pauseBtn.disabled = false;
            stopBtn.disabled = false;
            break;
        case 'paused':
            startBtn.disabled = false;
            pauseBtn.disabled = true;
            stopBtn.disabled = false;
            break;
    }
}

// Function to update OCR results display
function updateOcrResults(results) {
    const container = document.getElementById('ocr-results-container');
    const noResultsMsg = document.getElementById('no-results-message');
    const resultsList = document.getElementById('results-list');
    
    container.style.display = 'block';
    resultsList.innerHTML = '';
    
    const resultsArray = Object.entries(results);
    
    if (resultsArray.length === 0) {
        noResultsMsg.style.display = 'block';
    } else {
        noResultsMsg.style.display = 'none';
        
        resultsArray.forEach(([regionName, text]) => {
            const resultItem = document.createElement('div');
            resultItem.className = 'result-item';
            
            const nameElement = document.createElement('div');
            nameElement.className = 'result-name';
            nameElement.innerText = regionName;
            
            const textElement = document.createElement('div');
            textElement.className = 'result-text';
            textElement.innerText = text || '(No text detected)';
            
            resultItem.appendChild(nameElement);
            resultItem.appendChild(textElement);
            resultsList.appendChild(resultItem);
        });
    }
}

// Function to control the macro
function controlMacro(action) {
    const formData = new FormData();
    formData.append('action', action);
    
    fetch('/control', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        console.log(data.message);
    });
}