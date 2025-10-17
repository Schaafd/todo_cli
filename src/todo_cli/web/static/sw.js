/**
 * Service Worker for Todo CLI PWA
 * 
 * Provides offline functionality and caching for the Todo CLI web application.
 */

const CACHE_NAME = 'todo-cli-pwa-v1.0.0';
const API_CACHE_NAME = 'todo-cli-api-v1.0.0';

// Resources to cache for offline use
const STATIC_RESOURCES = [
    '/',
    '/static/css/main.css',
    '/static/js/api.js',
    '/static/js/ui.js',
    '/static/js/app.js',
    '/static/manifest.json'
];

// API endpoints to cache
const CACHEABLE_API_PATTERNS = [
    '/api/tasks',
    '/api/contexts',
    '/api/tags',
    '/api/health'
];

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
                    if (cacheName !== CACHE_NAME && cacheName !== API_CACHE_NAME) {
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

// Handle API requests with network-first strategy
async function handleApiRequest(request) {
    const url = new URL(request.url);
    
    // For GET requests that are cacheable, use network-first strategy
    if (request.method === 'GET' && isCacheableApiRequest(url.pathname)) {
        try {
            // Try network first
            const networkResponse = await fetch(request);
            
            if (networkResponse.ok) {
                // Cache successful responses
                const cache = await caches.open(API_CACHE_NAME);
                cache.put(request, networkResponse.clone());
                return networkResponse;
            }
            
            // If network fails, try cache
            const cachedResponse = await caches.match(request);
            if (cachedResponse) {
                console.log('[Service Worker] Serving API from cache:', url.pathname);
                return cachedResponse;
            }
            
            return networkResponse;
            
        } catch (error) {
            console.log('[Service Worker] Network failed, trying cache:', url.pathname);
            
            // Network failed, try cache
            const cachedResponse = await caches.match(request);
            if (cachedResponse) {
                return cachedResponse;
            }
            
            // Return offline response for tasks
            if (url.pathname === '/api/tasks') {
                return new Response(JSON.stringify([]), {
                    status: 200,
                    headers: { 'Content-Type': 'application/json' }
                });
            }
            
            // Return empty arrays for other list endpoints
            if (url.pathname === '/api/contexts' || url.pathname === '/api/tags') {
                return new Response(JSON.stringify([]), {
                    status: 200,
                    headers: { 'Content-Type': 'application/json' }
                });
            }
            
            // For other API requests, throw the error
            throw error;
        }
    }
    
    // For non-GET requests or non-cacheable requests, always go to network
    try {
        return await fetch(request);
    } catch (error) {
        // For write operations when offline, we could implement a queue
        // For now, just return an error response
        return new Response(JSON.stringify({
            detail: 'Operation not available offline'
        }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' }
        });
    }
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
    return CACHEABLE_API_PATTERNS.some(pattern => pathname.startsWith(pattern));
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
    // Here you could implement queued operations that failed while offline
    // For example, sync pending task changes
    console.log('[Service Worker] Performing background sync...');
    
    try {
        // Clear old API cache to ensure fresh data
        const apiCache = await caches.open(API_CACHE_NAME);
        await apiCache.delete('/api/tasks');
        await apiCache.delete('/api/contexts');
        await apiCache.delete('/api/tags');
        
        console.log('[Service Worker] Background sync completed');
    } catch (error) {
        console.error('[Service Worker] Background sync failed:', error);
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
    
    if (event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
    
    if (event.data.type === 'CACHE_CLEAR') {
        event.waitUntil(
            caches.keys().then((cacheNames) => {
                return Promise.all(
                    cacheNames.map((cacheName) => {
                        return caches.delete(cacheName);
                    })
                );
            })
        );
    }
});