/**
 * Phase 10: PWA registration + install prompt
 */

// Register service worker
export function registerSW() {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', async () => {
      try {
        const reg = await navigator.serviceWorker.register('/sw.js')
        console.log('KreativOS SW registered:', reg.scope)
      } catch (e) {
        console.warn('SW registration failed:', e)
      }
    })
  }
}

// Install prompt handling
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
  return window.matchMedia('(display-mode: standalone)').matches ||
         window.navigator.standalone === true
}

// Request notification permission for scheduled tasks
export async function requestNotificationPermission() {
  if (!('Notification' in window)) return false
  const perm = await Notification.requestPermission()
  return perm === 'granted'
}
