/**
 * Phase 1 Fix: PWA registration + install prompt + update notification
 *
 * Key fix: skipWaiting() is no longer called automatically.
 * The old behaviour silently replaced the active SW mid-session, which
 * could corrupt streaming state. Now we show a toast and only call
 * skipWaiting() when the user explicitly clicks "Reload to apply".
 */

// ── Service Worker registration ────────────────────────────────────────────────
export function registerSW() {
  if (!('serviceWorker' in navigator)) return

  window.addEventListener('load', async () => {
    try {
      const reg = await navigator.serviceWorker.register('/sw.js')
      console.log('[KreativOS SW] registered:', reg.scope)

      // Listen for updates that arrive after initial registration
      reg.addEventListener('updatefound', () => {
        const newWorker = reg.installing
        if (!newWorker) return
        newWorker.addEventListener('statechange', () => {
          if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
            // A new SW is waiting — trigger the update UI callback
            _onUpdateReady?.()
          }
        })
      })
    } catch (e) {
      console.warn('[KreativOS SW] registration failed:', e)
    }
  })

  // Handle the case where the SW is already waiting when the page loads
  navigator.serviceWorker.ready.then(reg => {
    if (reg.waiting && navigator.serviceWorker.controller) {
      _onUpdateReady?.()
    }
  })
}

// ── Update notification ────────────────────────────────────────────────────────
let _onUpdateReady = null

/**
 * Call this in App.jsx to register a callback when an update is available.
 * The callback should show a toast with a "Reload" button.
 * Only call skipWaiting() from the reload handler (triggered by user action).
 */
export function setupUpdatePrompt(onReady) {
  _onUpdateReady = onReady
}

// ── Install prompt ─────────────────────────────────────────────────────────────
let deferredPrompt = null

export function setupInstallPrompt(onReady) {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault()
    deferredPrompt = e
    onReady?.(true)
  })
  window.addEventListener('appinstalled', () => {
    deferredPrompt = null
    onReady?.(false)
  })
}

export async function triggerInstall() {
  if (!deferredPrompt) return false
  deferredPrompt.prompt()
  const { outcome } = await deferredPrompt.userChoice
  deferredPrompt = null
  return outcome === 'accepted'
}

export function isPWAInstalled() {
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true
  )
}

// ── Notification permission ────────────────────────────────────────────────────
export async function requestNotificationPermission() {
  if (!('Notification' in window)) return false
  const perm = await Notification.requestPermission()
  return perm === 'granted'
}
