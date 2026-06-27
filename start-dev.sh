const CACHE_NAME = 'krestivos-v3'
const STATIC_ASSETS = ['/', '/index.html', '/manifest.json']

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(STATIC_ASSETS)))
  self.skipWaiting()
})
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
  ))
  self.clients.claim()
})
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url)
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/ws')) {
    e.respondWith(fetch(e.request).catch(() =>
      new Response(JSON.stringify({error:'Offline'}), {headers:{'Content-Type':'application/json'},status:503})
    ))
    return
  }
  e.respondWith(caches.match(e.request).then(cached => cached || fetch(e.request)))
})
self.addEventListener('push', (e) => {
  const data = e.data?.json() || {title:'KrestivOS',body:'Task completed'}
  e.waitUntil(self.registration.showNotification(data.title, {body:data.body,icon:'/icon-192.png'}))
})
