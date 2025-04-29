// Webhook management functionality

// Function to load webhook settings
function loadWebhookSettings() {
    fetch('/webhook_settings')
        .then(response => response.json())
        .then(data => {
            // Load basic settings
            document.getElementById('webhook-enabled').checked = data.enabled;
            document.getElementById('webhook-url').value = data.url || '';
            document.getElementById('biome-notifications').checked = data.biome_notifications;
            document.getElementById('user-id').value = data.user_id || '';
            
            // Load and render keywords
            renderKeywords(data.keywords || []);
            
            console.log('Webhook settings loaded successfully', data);
        })
        .catch(error => console.error('Error loading webhook settings:', error));
}

// Function to save webhook settings
function saveWebhookSettings() {
    fetch('/webhook_settings')
        .then(response => response.json())
        .then(data => {
            // Keep existing keywords
            const updatedSettings = {
                enabled: document.getElementById('webhook-enabled').checked,
                url: document.getElementById('webhook-url').value.trim(),
                biome_notifications: document.getElementById('biome-notifications').checked,
                user_id: document.getElementById('user-id').value.trim(),
                keywords: data.keywords || [] // Preserve existing keywords
            };
            
            return fetch('/webhook_settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updatedSettings)
            });
        })
        .then(response => response.json())
        .then(data => {
            alert('Webhook settings saved successfully!');
            console.log('Webhook settings updated:', data);
        })
        .catch(error => {
            alert('Error saving webhook settings. Please try again.');
            console.error('Error saving webhook settings:', error);
        });
}

// Function to test webhook
function testWebhook() {
    const webhookUrl = document.getElementById('webhook-url').value.trim();
    const resultDiv = document.getElementById('webhook-test-result');
    
    if (!webhookUrl) {
        resultDiv.style.display = 'block';
        resultDiv.style.backgroundColor = '#ffebee';
        resultDiv.innerHTML = '<div style="color: red;">Please enter a webhook URL first.</div>';
        return;
    }
    
    resultDiv.style.display = 'block';
    resultDiv.style.backgroundColor = '#f8f9fa';
    resultDiv.innerHTML = '<div>Sending test webhook...</div>';
    
    // Send test request to our server endpoint instead of directly to webhook URL
    fetch('/test_webhook', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ url: webhookUrl })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            resultDiv.style.backgroundColor = '#e7f7e7';
            resultDiv.innerHTML = `
                <div style="color: green; font-weight: bold;">✓ Webhook test successful!</div>
                <div>Response status: ${data.status_code}</div>
                <div>Test message sent to: ${webhookUrl}</div>
            `;
        } else {
            resultDiv.style.backgroundColor = '#ffebee';
            resultDiv.innerHTML = `
                <div style="color: red; font-weight: bold;">✗ Webhook test failed</div>
                <div>Error: ${data.message}</div>
                ${data.response ? `<div>Response: ${data.response}</div>` : ''}
                <div>Please check that your webhook URL is correct and the server is running.</div>
            `;
        }
    })
    .catch(error => {
        resultDiv.style.backgroundColor = '#ffebee';
        resultDiv.innerHTML = `
            <div style="color: red; font-weight: bold;">✗ Webhook test failed</div>
            <div>Error: ${error.message}</div>
            <div>There was a problem with the webhook test. Please try again.</div>
        `;
    });
}

// Function to render keywords list in the table
function renderKeywords(keywords) {
    const tableBody = document.getElementById('keywords-table-body');
    const noKeywordsMsg = document.getElementById('no-keywords-message');
    const keywordsTable = document.getElementById('keywords-table');
    
    // Clear the table
    tableBody.innerHTML = '';
    
    if (!keywords || keywords.length === 0) {
        noKeywordsMsg.style.display = 'block';
        keywordsTable.style.display = 'none';
        return;
    }
    
    // Hide the "no keywords" message and show the table
    noKeywordsMsg.style.display = 'none';
    keywordsTable.style.display = 'table';
    
    // Add each keyword to the table
    keywords.forEach((keyword, index) => {
        const row = document.createElement('tr');
        
        // Keyword text cell
        const textCell = document.createElement('td');
        textCell.style.padding = '8px';
        textCell.style.borderBottom = '1px solid #ddd';
        textCell.textContent = keyword.text;
        
        // Enabled toggle cell
        const enabledCell = document.createElement('td');
        enabledCell.style.padding = '8px';
        enabledCell.style.borderBottom = '1px solid #ddd';
        enabledCell.style.textAlign = 'center';
        
        const enabledLabel = document.createElement('label');
        enabledLabel.className = 'toggle';
        enabledLabel.style.margin = '0 auto';
        
        const enabledInput = document.createElement('input');
        enabledInput.type = 'checkbox';
        enabledInput.checked = keyword.enabled !== false; // Default to true if undefined
        enabledInput.onchange = function() {
            updateKeywordProperty(index, 'enabled', this.checked);
        };
        
        const enabledSlider = document.createElement('span');
        enabledSlider.className = 'slider';
        
        enabledLabel.appendChild(enabledInput);
        enabledLabel.appendChild(enabledSlider);
        enabledCell.appendChild(enabledLabel);
        
        // Ping toggle cell
        const pingCell = document.createElement('td');
        pingCell.style.padding = '8px';
        pingCell.style.borderBottom = '1px solid #ddd';
        pingCell.style.textAlign = 'center';
        
        const pingLabel = document.createElement('label');
        pingLabel.className = 'toggle';
        pingLabel.style.margin = '0 auto';
        
        const pingInput = document.createElement('input');
        pingInput.type = 'checkbox';
        pingInput.checked = keyword.ping === true;
        pingInput.onchange = function() {
            updateKeywordProperty(index, 'ping', this.checked);
        };
        
        const pingSlider = document.createElement('span');
        pingSlider.className = 'slider';
        
        pingLabel.appendChild(pingInput);
        pingLabel.appendChild(pingSlider);
        pingCell.appendChild(pingLabel);
        
        // Actions cell
        const actionsCell = document.createElement('td');
        actionsCell.style.padding = '8px';
        actionsCell.style.borderBottom = '1px solid #ddd';
        actionsCell.style.textAlign = 'center';
        
        const deleteButton = document.createElement('button');
        deleteButton.className = 'region-delete';
        deleteButton.textContent = 'Remove';
        deleteButton.onclick = function() {
            deleteKeyword(index);
        };
        
        actionsCell.appendChild(deleteButton);
        
        // Add all cells to the row
        row.appendChild(textCell);
        row.appendChild(enabledCell);
        row.appendChild(pingCell);
        row.appendChild(actionsCell);
        
        // Add the row to the table
        tableBody.appendChild(row);
    });
}

// Function to add a new keyword
function addKeyword() {
    const keywordInput = document.getElementById('new-keyword');
    const keywordText = keywordInput.value.trim();
    
    if (!keywordText) {
        alert('Please enter a keyword first.');
        return;
    }
    
    // Get current keywords from webhook settings
    fetch('/webhook_settings')
        .then(response => response.json())
        .then(data => {
            const keywords = data.keywords || [];
            
            // Check if keyword already exists
            const exists = keywords.some(k => k.text.toLowerCase() === keywordText.toLowerCase());
            if (exists) {
                alert('This keyword already exists.');
                return;
            }
            
            // Add the new keyword
            keywords.push({
                text: keywordText,
                enabled: true,
                ping: false
            });
            
            // Update webhook settings with new keywords
            const updatedSettings = {
                ...data,
                keywords: keywords
            };
            
            return fetch('/webhook_settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updatedSettings)
            });
        })
        .then(response => response.json())
        .then(data => {
            // Clear the input field
            keywordInput.value = '';
            
            // Render the updated keywords list
            renderKeywords(data.webhook.keywords);
        })
        .catch(error => {
            console.error('Error adding keyword:', error);
            alert('Error adding keyword. Please try again.');
        });
}

// Function to delete a keyword
function deleteKeyword(index) {
    fetch('/webhook_settings')
        .then(response => response.json())
        .then(data => {
            const keywords = data.keywords || [];
            
            if (index >= 0 && index < keywords.length) {
                // Remove the keyword at the specified index
                keywords.splice(index, 1);
                
                // Update webhook settings without the deleted keyword
                const updatedSettings = {
                    ...data,
                    keywords: keywords
                };
                
                return fetch('/webhook_settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(updatedSettings)
                });
            }
        })
        .then(response => response.json())
        .then(data => {
            // Render the updated keywords list
            renderKeywords(data.webhook.keywords);
        })
        .catch(error => {
            console.error('Error deleting keyword:', error);
            alert('Error deleting keyword. Please try again.');
        });
}

// Function to update a keyword property (enabled or ping)
function updateKeywordProperty(index, property, value) {
    fetch('/webhook_settings')
        .then(response => response.json())
        .then(data => {
            const keywords = data.keywords || [];
            
            if (index >= 0 && index < keywords.length) {
                // Update the specified property of the keyword
                keywords[index][property] = value;
                
                // Update webhook settings with the modified keyword
                const updatedSettings = {
                    ...data,
                    keywords: keywords
                };
                
                return fetch('/webhook_settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(updatedSettings)
                });
            }
        })
        .then(response => response.json())
        .then(data => {
            // No need to re-render since the toggles update visually
        })
        .catch(error => {
            console.error(`Error updating keyword ${property}:`, error);
            alert(`Error updating keyword. Please try again.`);
        });
}