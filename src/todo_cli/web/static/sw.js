/**
 * Service Worker for Todo CLI PWA
 * 
 * Provides offline functionality and caching for the Todo CLI web application.
 */

// Version the cache based on deployment/build
const CACHE_VERSION = '1.1.0';
const CACHE_NAME = `todo-cli-static-v${CACHE_VERSION}`;
const API_CACHE_NAME = `todo-cli-api-v${CACHE_VERSION}`;
const OFFLINE_CACHE_NAME = `todo-cli-offline-v${CACHE_VERSION}`;

// Resources to precache for offline use
const STATIC_RESOURCES = [
    '/',
    '/static/css/main.css',
    '/static/css/enhancements.css',
    '/static/js/config.js',
    '/static/js/api.js',
    '/static/js/data-loader.js',
    '/static/js/ui.js',
    '/static/js/app.js',
    '/static/manifest.json'
];

// API endpoints that can be cached for offline fallback
const CACHEABLE_API_PATTERNS = [
    '/api/tasks',
    '/api/contexts',
    '/api/tags'
];

// API endpoints that should NEVER be cached (always fresh)
const NON_CACHEABLE_API_PATTERNS = [
    '/api/tasks/',  // Individual task operations
    '/api/backups', // Backup operations
    '/health'       // Health checks
];

// Maximum age for API cache (in milliseconds)
const API_CACHE_MAX_AGE = 5 * 60 * 1000; // 5 minutes

// Install event - cache static resources
self.addEventListener('install', (event) => {
    console.log('[Service Worker] Installing...');
    
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[Service Worker] Caching static resources');
            return cache.addAll(STATIC_RESOURCES);
        }).catch((error) => {
            console.error('[Service Worker] Failed to cache resources:', error);
        })
    );
    
    // Skip waiting to activate immediately
    self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    console.log('[Service Worker] Activating...');
    
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    // Keep only current version caches
                    const currentCaches = [CACHE_NAME, API_CACHE_NAME, OFFLINE_CACHE_NAME];
                    if (!currentCaches.includes(cacheName)) {
                        console.log('[Service Worker] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    
    // Take control of all clients immediately
    event.waitUntil(self.clients.claim());
});

// Fetch event - handle network requests
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);
    
    // Handle API requests
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(handleApiRequest(request));
        return;
    }
    
    // Handle static resources
    event.respondWith(handleStaticRequest(request));
});

// Handle API requests with enhanced network-first strategy
async function handleApiRequest(request) {
    const url = new URL(request.url);
    const pathname = url.pathname;
    
    // Always try network first for API requests to prevent stale data
    try {
        console.log('[Service Worker] Trying network for API:', pathname);
        const networkResponse = await fetch(request);
        
        // Only cache successful GET responses for cacheable endpoints
        if (request.method === 'GET' && 
            networkResponse.ok && 
            networkResponse.status >= 200 && 
            networkResponse.status < 300 &&
            isCacheableApiRequest(pathname) &&
            !isNonCacheableApiRequest(pathname)) {
            
            console.log('[Service Worker] Caching successful API response:', pathname);
            const cache = await caches.open(API_CACHE_NAME);
            
            // Add timestamp to cached response for expiration
            const responseToCache = networkResponse.clone();
            const headers = new Headers(responseToCache.headers);
            headers.set('sw-cached-at', Date.now().toString());
            
            const cachedResponse = new Response(responseToCache.body, {
                status: responseToCache.status,
                statusText: responseToCache.statusText,
                headers: headers
            });
            
            await cache.put(request, cachedResponse);
        }
        
        return networkResponse;
        
    } catch (networkError) {
        console.log('[Service Worker] Network failed for API:', pathname, networkError.message);
        
        // Only fallback to cache for GET requests on cacheable endpoints
        if (request.method === 'GET' && isCacheableApiRequest(pathname)) {
            const cachedResponse = await getCachedApiResponse(request);
            
            if (cachedResponse) {
                console.log('[Service Worker] Serving stale API data from cache:', pathname);
                
                // Add header to indicate this is cached data
                const headers = new Headers(cachedResponse.headers);
                headers.set('sw-served-from-cache', 'true');
                headers.set('sw-network-error', networkError.message);
                
                return new Response(cachedResponse.body, {
                    status: cachedResponse.status,
                    statusText: cachedResponse.statusText,
                    headers: headers
                });
            }
            
            // Return structured offline response for specific endpoints
            return getOfflineApiResponse(pathname);
        }
        
        // For non-GET requests or non-cacheable endpoints, return error
        return new Response(JSON.stringify({
            detail: `Network error: ${networkError.message}. Operation not available offline.`,
            type: 'network_error',
            offline: true
        }), {
            status: 503,
            headers: { 
                'Content-Type': 'application/json',
                'sw-network-error': 'true'
            }
        });
    }
}

// Get cached API response with expiration check
async function getCachedApiResponse(request) {
    const cache = await caches.open(API_CACHE_NAME);
    const cachedResponse = await cache.match(request);
    
    if (!cachedResponse) {
        return null;
    }
    
    // Check if cached response has expired
    const cachedAt = cachedResponse.headers.get('sw-cached-at');
    if (cachedAt) {
        const age = Date.now() - parseInt(cachedAt);
        if (age > API_CACHE_MAX_AGE) {
            console.log('[Service Worker] Cached API response expired, removing:', request.url);
            await cache.delete(request);
            return null;
        }
    }
    
    return cachedResponse;
}

// Generate appropriate offline responses for different API endpoints
function getOfflineApiResponse(pathname) {
    const offlineResponse = {
        '/api/tasks': [],
        '/api/contexts': [],
        '/api/tags': [],
    };
    
    const responseData = offlineResponse[pathname] || {
        detail: 'This endpoint is not available offline',
        type: 'offline_error'
    };
    
    return new Response(JSON.stringify(responseData), {
        status: pathname in offlineResponse ? 200 : 503,
        headers: { 
            'Content-Type': 'application/json',
            'sw-offline-fallback': 'true'
        }
    });
}

// Handle static requests with cache-first strategy
async function handleStaticRequest(request) {
    // Try cache first
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
        console.log('[Service Worker] Serving from cache:', request.url);
        return cachedResponse;
    }
    
    // If not in cache, go to network
    try {
        const networkResponse = await fetch(request);
        
        // Cache successful responses
        if (networkResponse.ok && shouldCacheRequest(request)) {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, networkResponse.clone());
        }
        
        return networkResponse;
        
    } catch (error) {
        console.error('[Service Worker] Network request failed:', request.url);
        
        // For the root document, return a basic offline page
        if (request.mode === 'navigate') {
            return new Response(`
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Todo CLI - Offline</title>
                    <style>
                        body { 
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            background: #1a1a1a;
                            color: #ffffff;
                            text-align: center;
                            padding: 50px;
                        }
                        .offline-message {
                            max-width: 600px;
                            margin: 0 auto;
                        }
                        .retry-btn {
                            background: #007acc;
                            color: white;
                            padding: 10px 20px;
                            border: none;
                            border-radius: 5px;
                            margin-top: 20px;
                            cursor: pointer;
                        }
                    </style>
                </head>
                <body>
                    <div class="offline-message">
                        <h1>Todo CLI</h1>
                        <h2>You're offline</h2>
                        <p>Please check your internet connection and try again.</p>
                        <button class="retry-btn" onclick="location.reload()">Retry</button>
                    </div>
                </body>
                </html>
            `, {
                headers: { 'Content-Type': 'text/html' }
            });
        }
        
        throw error;
    }
}

// Helper functions
function isCacheableApiRequest(pathname) {
    return CACHEABLE_API_PATTERNS.some(pattern => 
        pathname === pattern || pathname.startsWith(pattern + '?')
    );
}

function isNonCacheableApiRequest(pathname) {
    return NON_CACHEABLE_API_PATTERNS.some(pattern => 
        pathname.startsWith(pattern)
    );
}

function shouldCacheRequest(request) {
    const url = new URL(request.url);
    
    // Cache static resources
    if (STATIC_RESOURCES.some(resource => url.pathname.endsWith(resource))) {
        return true;
    }
    
    // Cache CSS, JS, and other static assets
    if (url.pathname.match(/\.(css|js|png|jpg|jpeg|gif|svg|ico|woff|woff2)$/)) {
        return true;
    }
    
    return false;
}

// Background sync for when the app comes back online
self.addEventListener('sync', (event) => {
    console.log('[Service Worker] Background sync:', event.tag);
    
    if (event.tag === 'background-sync') {
        event.waitUntil(doBackgroundSync());
    }
});

async function doBackgroundSync() {
    console.log('[Service Worker] Performing background sync...');
    
    try {
        // Test network connectivity
        const healthCheck = await fetch('/health');
        if (!healthCheck.ok) {
            throw new Error('Server not available');
        }
        
        // Clear expired API cache entries to ensure fresh data
        const apiCache = await caches.open(API_CACHE_NAME);
        const keys = await apiCache.keys();
        
        for (const request of keys) {
            const response = await apiCache.match(request);
            if (response) {
                const cachedAt = response.headers.get('sw-cached-at');
                if (cachedAt) {
                    const age = Date.now() - parseInt(cachedAt);
                    if (age > API_CACHE_MAX_AGE) {
                        console.log('[Service Worker] Removing expired cache entry:', request.url);
                        await apiCache.delete(request);
                    }
                }
            }
        }
        
        // Notify all clients that we're back online
        const clients = await self.clients.matchAll();
        clients.forEach(client => {
            client.postMessage({
                type: 'ONLINE',
                message: 'Connection restored'
            });
        });
        
        console.log('[Service Worker] Background sync completed');
    } catch (error) {
        console.error('[Service Worker] Background sync failed:', error);
        
        // Notify clients about sync failure
        const clients = await self.clients.matchAll();
        clients.forEach(client => {
            client.postMessage({
                type: 'SYNC_FAILED',
                error: error.message
            });
        });
    }
}

// Handle push notifications (future enhancement)
self.addEventListener('push', (event) => {
    console.log('[Service Worker] Push received:', event);
    
    if (event.data) {
        const data = event.data.json();
        const options = {
            body: data.body || 'You have new todo updates',
            icon: '/static/icons/icon-192.png',
            badge: '/static/icons/icon-192.png',
            tag: 'todo-notification',
            renotify: true,
            requireInteraction: false
        };
        
        event.waitUntil(
            self.registration.showNotification(data.title || 'Todo CLI', options)
        );
    }
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
    console.log('[Service Worker] Notification clicked');
    
    event.notification.close();
    
    event.waitUntil(
        self.clients.openWindow('/')
    );
});

// Message handler for communication with the main app
self.addEventListener('message', (event) => {
    console.log('[Service Worker] Message received:', event.data);
    
    const { type, data } = event.data;
    
    switch (type) {
        case 'SKIP_WAITING':
            self.skipWaiting();
            break;
            
        case 'CACHE_CLEAR':
            event.waitUntil(clearAllCaches());
            break;
            
        case 'CACHE_API_CLEAR':
            event.waitUntil(clearApiCache());
            break;
            
        case 'CACHE_STATIC_REFRESH':
            event.waitUntil(refreshStaticCache());
            break;
            
        case 'GET_CACHE_STATUS':
            event.waitUntil(getCacheStatus().then(status => {
                event.ports[0].postMessage(status);
            }));
            break;
    }
});

// Cache management functions
async function clearAllCaches() {
    const cacheNames = await caches.keys();
    await Promise.all(cacheNames.map(name => caches.delete(name)));
    console.log('[Service Worker] All caches cleared');
}

async function clearApiCache() {
    await caches.delete(API_CACHE_NAME);
    console.log('[Service Worker] API cache cleared');
}

async function refreshStaticCache() {
    const cache = await caches.open(CACHE_NAME);
    await Promise.all(STATIC_RESOURCES.map(url => 
        fetch(url).then(response => {
            if (response.ok) {
                return cache.put(url, response);
            }
        }).catch(error => {
            console.warn(`[Service Worker] Failed to refresh ${url}:`, error);
        })
    ));
    console.log('[Service Worker] Static cache refreshed');
}

async function getCacheStatus() {
    const cacheNames = await caches.keys();
    const status = {
        version: CACHE_VERSION,
        caches: {},
        total_size: 0
    };
    
    for (const cacheName of cacheNames) {
        const cache = await caches.open(cacheName);
        const keys = await cache.keys();
        status.caches[cacheName] = {
            entries: keys.length,
            keys: keys.map(req => req.url)
        };
    }
    
    return status;
}
