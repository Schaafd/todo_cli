/**
 * Configuration for Todo CLI PWA
 */

// Environment configuration
const ENV = {
    // Default to current origin for production, allow override for development
    API_BASE_URL: window.location.origin,
    
    // Development settings
    DEBUG: false,
    
    // API endpoints
    API_VERSION: 'v1',
    
    // PWA settings
    APP_NAME: 'Todo CLI Web',
    APP_VERSION: '1.0.0',
    
    // Feature flags
    FEATURES: {
        OFFLINE_MODE: true,
        QUICK_CAPTURE: true,
        KEYBOARD_SHORTCUTS: true,
        DARK_MODE: true,
        NOTIFICATIONS: true
    },
    
    // UI settings
    UI: {
        DEFAULT_VIEW: 'list',
        ANIMATION_DURATION: 300,
        DEBOUNCE_DELAY: 300,
        AUTO_SAVE_DELAY: 1000
    },
    
    // API configuration
    API: {
        TIMEOUT: 10000,
        RETRY_ATTEMPTS: 3,
        RETRY_DELAY: 1000
    }
};

// Allow override via URL parameters (for development)
if (typeof window !== 'undefined') {
    const urlParams = new URLSearchParams(window.location.search);
    
    // Override API base URL
    if (urlParams.get('api_base')) {
        ENV.API_BASE_URL = urlParams.get('api_base');
    }
    
    // Enable debug mode
    if (urlParams.get('debug') === 'true') {
        ENV.DEBUG = true;
    }
}

// Development environment detection
if (typeof window !== 'undefined') {
    // Enable debug mode in development
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        ENV.DEBUG = true;
    }
}

// Console logging for development
if (ENV.DEBUG) {
    console.log('PWA Configuration:', ENV);
}

// Export configuration
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ENV };
} else if (typeof window !== 'undefined') {
    window.ENV = ENV;
}