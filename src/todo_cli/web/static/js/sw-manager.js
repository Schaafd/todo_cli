/**
 * Service Worker Manager for Todo CLI PWA
 * 
 * Handles service worker communication, offline detection, and cache management.
 */

class ServiceWorkerManager {
    constructor() {
        this.isOnline = navigator.onLine;
        this.serviceWorker = null;
        this.retryQueue = [];
        this.listeners = new Map();
        
        this.init();
    }
    
    async init() {
        if ('serviceWorker' in navigator) {
            try {
                const registration = await navigator.serviceWorker.register('/static/sw.js');
                this.serviceWorker = registration;
                
                console.log('[SW Manager] Service worker registered:', registration.scope);
                
                // Listen for service worker messages
                navigator.serviceWorker.addEventListener('message', (event) => {
                    this.handleServiceWorkerMessage(event.data);
                });
                
                // Handle service worker updates
                registration.addEventListener('updatefound', () => {
                    console.log('[SW Manager] Service worker update found');
                    this.showUpdateNotification();
                });
                
            } catch (error) {
                console.error('[SW Manager] Service worker registration failed:', error);
            }
        }
        
        // Set up online/offline detection
        window.addEventListener('online', () => {
            this.setOnlineStatus(true);
        });
        
        window.addEventListener('offline', () => {
            this.setOnlineStatus(false);
        });
        
        // Monitor API responses for offline indicators
        this.interceptFetch();
    }
    
    handleServiceWorkerMessage(data) {
        console.log('[SW Manager] Message from service worker:', data);
        
        switch (data.type) {
            case 'ONLINE':
                this.setOnlineStatus(true);
                this.showNotification('Connection restored', 'success');
                this.processRetryQueue();
                break;
                
            case 'SYNC_FAILED':
                this.showNotification(`Sync failed: ${data.error}`, 'error');
                break;
                
            case 'CACHE_UPDATED':
                this.showNotification('App updated - refresh to see changes', 'info', 10000);
                break;
        }
        
        // Emit to listeners
        if (this.listeners.has(data.type)) {
            this.listeners.get(data.type).forEach(callback => callback(data));
        }
    }
    
    setOnlineStatus(online) {
        if (this.isOnline !== online) {
            this.isOnline = online;
            console.log('[SW Manager] Network status changed:', online ? 'online' : 'offline');
            
            // Update UI
            this.updateOnlineIndicator();
            
            // Emit event
            this.emit('connection-changed', { online });
            
            if (online) {
                this.processRetryQueue();
            } else {
                this.showOfflineNotification();
            }
        }
    }
    
    updateOnlineIndicator() {
        // Add or remove offline indicator
        let indicator = document.getElementById('offline-indicator');
        
        if (!this.isOnline) {
            if (!indicator) {
                indicator = document.createElement('div');
                indicator.id = 'offline-indicator';
                indicator.className = 'offline-indicator';
                indicator.innerHTML = `
                    <div class="offline-message">
                        <span>⚠️ You're offline - some features may not work</span>
                        <button onclick="swManager.checkConnection()" class="retry-btn">Retry</button>
                    </div>
                `;
                document.body.appendChild(indicator);
            }
        } else if (indicator) {
            indicator.remove();
        }
    }
    
    showOfflineNotification() {
        if (typeof ui !== 'undefined') {
            ui.showWarning('You are now offline. Some features may be limited.', 8000);
        }
    }
    
    showUpdateNotification() {
        if (typeof ui !== 'undefined') {
            const updateBtn = document.createElement('button');
            updateBtn.textContent = 'Update Now';
            updateBtn.onclick = () => this.updateServiceWorker();
            
            ui.showToast('A new version is available!', 'info', 0);
        }
    }
    
    showNotification(message, type, duration = 5000) {
        if (typeof ui !== 'undefined') {
            ui.showToast(message, type, duration);
        } else {
            console.log(`[SW Manager] ${type.toUpperCase()}: ${message}`);
        }
    }
    
    async updateServiceWorker() {
        if (this.serviceWorker) {
            const newWorker = this.serviceWorker.waiting;
            if (newWorker) {
                newWorker.postMessage({ type: 'SKIP_WAITING' });
                window.location.reload();
            }
        }
    }
    
    async checkConnection() {
        try {
            const response = await fetch('/health', { 
                cache: 'no-cache',
                signal: AbortSignal.timeout(5000)
            });
            
            this.setOnlineStatus(response.ok);
            return response.ok;
        } catch (error) {
            this.setOnlineStatus(false);
            return false;
        }
    }
    
    // Cache management methods
    async clearCache(type = 'all') {
        if (!navigator.serviceWorker.controller) return;
        
        const messageType = type === 'api' ? 'CACHE_API_CLEAR' : 'CACHE_CLEAR';
        navigator.serviceWorker.controller.postMessage({ type: messageType });
        
        this.showNotification(`${type} cache cleared`, 'success');
    }
    
    async refreshCache() {
        if (!navigator.serviceWorker.controller) return;
        
        navigator.serviceWorker.controller.postMessage({ type: 'CACHE_STATIC_REFRESH' });
        this.showNotification('Cache refreshed', 'success');
    }
    
    async getCacheStatus() {
        return new Promise((resolve) => {
            if (!navigator.serviceWorker.controller) {
                resolve(null);
                return;
            }
            
            const channel = new MessageChannel();
            channel.port1.onmessage = (event) => {
                resolve(event.data);
            };
            
            navigator.serviceWorker.controller.postMessage(
                { type: 'GET_CACHE_STATUS' },
                [channel.port2]
            );
        });
    }
    
    // Retry queue for failed requests when offline
    addToRetryQueue(requestFn, description = 'Request') {
        this.retryQueue.push({ requestFn, description });
        console.log(`[SW Manager] Added to retry queue: ${description}`);
    }
    
    async processRetryQueue() {
        if (this.retryQueue.length === 0) return;
        
        console.log(`[SW Manager] Processing ${this.retryQueue.length} queued requests`);
        
        const results = await Promise.allSettled(
            this.retryQueue.map(({ requestFn, description }) => 
                requestFn().then(() => ({ success: true, description }))
                         .catch(error => ({ success: false, description, error }))
            )
        );
        
        const successful = results.filter(r => r.status === 'fulfilled' && r.value.success);
        const failed = results.filter(r => r.status === 'rejected' || !r.value.success);
        
        if (successful.length > 0) {
            this.showNotification(`${successful.length} queued operations completed`, 'success');
        }
        
        if (failed.length > 0) {
            console.warn('[SW Manager] Some queued operations failed:', failed);
        }
        
        // Clear the queue
        this.retryQueue = [];
    }
    
    // Event system
    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, []);
        }
        this.listeners.get(event).push(callback);
    }
    
    off(event, callback) {
        if (this.listeners.has(event)) {
            const callbacks = this.listeners.get(event);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        }
    }
    
    emit(event, data) {
        if (this.listeners.has(event)) {
            this.listeners.get(event).forEach(callback => callback(data));
        }
    }
    
    // Intercept fetch to detect offline/cached responses
    interceptFetch() {
        if (typeof window !== 'undefined' && 'fetch' in window) {
            const originalFetch = window.fetch;
            
            window.fetch = async (...args) => {
                try {
                    const response = await originalFetch(...args);
                    
                    // Check if response came from service worker cache
                    if (response.headers.get('sw-served-from-cache')) {
                        console.log('[SW Manager] Response served from cache due to network error');
                        this.setOnlineStatus(false);
                    } else if (response.headers.get('sw-offline-fallback')) {
                        console.log('[SW Manager] Offline fallback response served');
                        this.setOnlineStatus(false);
                    } else if (!this.isOnline) {
                        // We got a real response, so we must be online
                        this.setOnlineStatus(true);
                    }
                    
                    return response;
                } catch (error) {
                    console.log('[SW Manager] Fetch failed:', error.message);
                    this.setOnlineStatus(false);
                    throw error;
                }
            };
        }
    }
}

// Create global service worker manager instance
const swManager = new ServiceWorkerManager();

// Export for potential module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ServiceWorkerManager, swManager };
}