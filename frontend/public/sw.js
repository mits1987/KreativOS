/**
 * Phase 1 Fix: Service Worker
 *
 * Key fix: removed self.skipWaiting() from the install handler.
 * The old version called skipWaiting() immediately, silently replacing
 * the active SW mid-session and potentially corrupting streaming state.
 *
 * Now: the new SW waits. When the user clicks "Reload to apply" in the
 * update toast, App.jsx posts a SKIP_WAITING message, THEN reloads.
 */
const CACHE_NAME    = 'kreavitos-v3'
const STATIC_ASSETS = ['/manifest.json']

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(c => c.addAll(STATIC_ASSETS))
  )
})

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  )
  self.clients.claim()
})

// Handle explicit skip from App.jsx update toast
self.addEventListener('message', (e) => {
  if (e.data?.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url)

  // Never cache API or WebSocket traffic
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/ws')) {
    e.respondWith(
      fetch(e.request).catch(() =>
        new Response(
          JSON.stringify({ error: 'Offline — KreativOS backend not reachable' }),
          { headers: { 'Content-Type': 'application/json' }, status: 503 }
        )
      )
    )
    return
  }

  // Network-first for everything else — KreativOS is a local app,
  // caching HTML/assets causes stale-after-rebuild issues
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  )
})

self.addEventListener('push', (e) => {
  const data = e.data?.json() || { title: 'KreativOS', body: 'Task completed' }
  e.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/icon-192.png',
    })
  )
})
