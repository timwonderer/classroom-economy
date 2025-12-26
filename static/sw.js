const CACHE_NAME = 'classroom-token-hub-v7';
const STATIC_ASSETS = [
  '/static/manifest.json',
  '/static/images/icon-192.png',
  '/static/images/icon-512.png',
  '/static/js/timezone-utils.js',
  '/static/css/style.css',
  '/offline'
];

// CDN resources - use network-first strategy
const CDN_RESOURCES = [
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js'
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      // Cache static assets with error handling
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('Failed to cache some assets during install:', err);
        // Continue installation even if some assets fail
      });
    }).then(() => {
      // Activate immediately without waiting
      return self.skipWaiting();
    })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      // Take control of all clients immediately
      return self.clients.claim();
    })
  );
});

// Fetch event - handle requests with appropriate strategies
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip caching for authenticated routes (multi-tenancy safety)
  const authRoutes = ['/admin', '/student', '/system-admin', '/api'];
  if (authRoutes.some((route) => url.pathname.startsWith(route))) {
    // Network-only for authenticated routes
    return;
  }

  // Handle navigation requests (page loads)
  if (event.request.mode === 'navigate') {
    event.respondWith(handleNavigation(event));
    return;
  }

  // Let browser handle Google Fonts natively - DO NOT intercept
  // Service Worker interception was breaking font loading in PWA mode
  if (url.hostname === 'fonts.googleapis.com' ||
      url.hostname === 'fonts.gstatic.com') {
    return; // Don't intercept - browser handles fonts correctly on its own
  }

  // Handle CDN resources - network-first strategy
  if (CDN_RESOURCES.some((cdn) => event.request.url.startsWith(cdn))) {
    event.respondWith(networkFirst(event));
    return;
  }

  // Handle static assets - cache-first strategy
  event.respondWith(cacheFirst(event));
});

async function handleNavigation(event) {
  try {
    return await fetch(event.request);
  } catch (error) {
    console.log('Fetch failed for navigation; returning offline page.', error);
    const cache = await caches.open(CACHE_NAME);
    return await cache.match('/offline');
  }
}

function shouldCache(request) {
  // Don't cache chrome-extension requests or non-http(s) schemes
  if (!request || !request.url || !request.url.startsWith('http')) {
    return false;
  }

  // Don't cache POST/PUT/DELETE requests
  if (request.method !== 'GET') {
    return false;
  }

  return true;
}

async function networkFirst(event) {
  const { request } = event;

  if (!shouldCache(request)) {
    return fetch(request);
  }

  try {
    const networkResponse = await fetch(request);

    // Clone the response before consuming it to avoid "body already used" errors
    if (networkResponse && networkResponse.status === 200) {
      const responseToCache = networkResponse.clone();
      event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
          return cache.put(request, responseToCache);
        })
      );
    }

    return networkResponse;
  } catch (error) {
    console.log('Network request failed, trying cache.', error);
    return await caches.match(request);
  }
}

async function cacheFirst(event) {
  const { request } = event;

  if (!shouldCache(request)) {
    return fetch(request);
  }

  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    return cachedResponse;
  }

  try {
    const networkResponse = await fetch(request);

    // Clone the response before consuming it to avoid "body already used" errors
    if (networkResponse && networkResponse.status === 200) {
      const responseToCache = networkResponse.clone();
      event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
          return cache.put(request, responseToCache);
        })
      );
    }

    return networkResponse;
  } catch (error) {
    console.error('Fetch failed for cache-first resource:', error);
    throw error;
  }
}
