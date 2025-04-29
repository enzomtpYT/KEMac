// Theme management functionality

// Set theme (dark or light)
function setTheme(isDark) {
    if (isDark) {
        document.documentElement.setAttribute('data-theme', 'dark');
        document.getElementById('theme-toggle-checkbox').checked = true;
    } else {
        document.documentElement.removeAttribute('data-theme');
        document.getElementById('theme-toggle-checkbox').checked = false;
    }
    // Store the preference
    localStorage.setItem('dark-theme', isDark ? 'true' : 'false');
}

// Initialize theme based on stored preference or default to dark
function initializeTheme() {
    // Get stored preference or default to true (dark theme)
    const preferDark = localStorage.getItem('dark-theme') !== 'false';
    setTheme(preferDark);
}

// Add event listeners when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Toggle theme when the switch is clicked
    const themeToggle = document.getElementById('theme-toggle-checkbox');
    if (themeToggle) {
        themeToggle.addEventListener('change', function() {
            setTheme(this.checked);
        });
    }
});