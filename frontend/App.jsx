import React, { useEffect, useState } from 'react'
import ErrorBoundary from './components/ErrorBoundary'
import Sidebar        from './components/Sidebar'
import LoginPage      from './pages/LoginPage'
import DashboardView  from './pages/DashboardView'
import ChatView       from './pages/ChatView'
import TasksView      from './pages/TasksView'
import PipelineView   from './pages/PipelineView'
import CanvasView     from './pages/CanvasView'
import AppBuilderView    from './pages/AppBuilderView'
import OfficeView     from './pages/OfficeView'
import FilesView      from './pages/FilesView'
import MemoryView     from './pages/MemoryView'
import SkillsView     from './pages/SkillsView'
import ModelHubView   from './pages/ModelHubView'
import MCPView        from './pages/MCPView'
import SchedulerView  from './pages/SchedulerView'
import PromptsView    from './pages/PromptsView'
import AuditView      from './pages/AuditView'
import BackupView     from './pages/BackupView'
import TelegramView   from './pages/TelegramView'
import UsersView      from './pages/UsersView'
import SettingsView   from './pages/SettingsView'
import useStore from './store'
import api from './utils/api'
import PermissionDialog from './components/PermissionDialog'
import {
  setupInstallPrompt, triggerInstall, isPWAInstalled,
  setupUpdatePrompt,
} from './pwa.js'
import { Download, RefreshCw, X } from 'lucide-react'

// ── View registry ──────────────────────────────────────────────────────────────
const VIEWS = {
  dashboard:   <DashboardView />,
  chat:        <ChatView />,
  tasks:       <TasksView />,
  pipeline:    <PipelineView />,
  canvas:      <CanvasView />,
  appbuilder:  <AppBuilderView />,
  office:      <OfficeView />,
  files:       <FilesView />,
  memory:      <MemoryView />,
  skills:      <SkillsView />,
  hub:         <ModelHubView />,
  mcp:         <MCPView />,
  scheduler:   <SchedulerView />,
  prompts:     <PromptsView />,
  audit:       <AuditView />,
  backup:      <BackupView />,
  telegram:    <TelegramView />,
  users:       <UsersView />,
  settings:    <SettingsView />,
}

export default function App() {
  const {
    activeView, setModels, setAgents, setOllamaStatus,
    selectedModel, setSelectedModel, conversations, createConversation,
    isAuthenticated, logout,
    pendingPermissions, setPendingPermissions,
    permissionDialog, setPermissionDialog,
  } = useStore()

  const [installReady, setInstallReady] = useState(false)
  const [updateReady,  setUpdateReady]  = useState(false)   // [P1-6] PWA update
  const [installed,    setInstalled]    = useState(isPWAInstalled())
  const [showOnboard,  setShowOnboard]  = useState(false)
  const [reconnecting, setReconnecting] = useState(false)

  // ── Init: load models, agents, health ───────────────────────────────────────
  useEffect(() => {
    const init = async () => {
      try {
        const [mdata, adata, health] = await Promise.all([
          api.models(), api.agents(), api.health(),
        ])
        const models = mdata.models || []
        setModels(models)
        setAgents(adata.agents || [])
        setOllamaStatus(health.ollama === 'connected' ? 'connected' : 'disconnected')

        if (models.length > 0 && !selectedModel) {
          setSelectedModel(models[0])
        }

        // Show onboarding if Ollama disconnected or no models
        if (health.ollama !== 'connected' || models.length === 0) {
          setShowOnboard(true)
        }
      } catch {
        setOllamaStatus('disconnected')
        setShowOnboard(true)
      }
    }
    init()

    // PWA install prompt
    setupInstallPrompt(setInstallReady)

    // [P1-6] PWA update notification — show toast, NOT auto-apply
    setupUpdatePrompt(() => setUpdateReady(true))
  }, [])

  // Create a default conversation if needed
  useEffect(() => {
    if (conversations.length === 0 && activeView === 'chat') {
      createConversation()
    }
  }, [activeView])

  // Reconnect on visibility change
  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        setReconnecting(true)
        useStore.getState().setOllamaStatus('unknown')
        setTimeout(() => setReconnecting(false), 2000)
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [])

  // Handle ?view= shortcut from PWA shortcuts
  useEffect(() => {
    const v = new URLSearchParams(window.location.search).get('view')
    if (v) useStore.getState().setActiveView(v)
  }, [])

  // ── Poll for pending permissions ─────────────────────────────────────────
  useEffect(() => {
    if (!isAuthenticated) return
    const poll = async () => {
      try {
        const data = await api.pendingPermissions()
        setPendingPermissions(data.pending || [])
        if (data.pending?.length > 0 && !permissionDialog) {
          setPermissionDialog(data.pending[0])
        }
      } catch { /* poll errors are expected when no permissions pending */ }
    }
    poll()
    const interval = setInterval(poll, 5000)
    return () => clearInterval(interval)
  }, [isAuthenticated])

  const handleUpdate = () => {
    // Tell the waiting service worker to take control
    if (navigator.serviceWorker?.controller) {
      navigator.serviceWorker.controller.postMessage({ type: 'SKIP_WAITING' })
    }
    window.location.reload()
  }

  // ── Auth gate ──────────────────────────────────────────────────────────────
  if (!isAuthenticated) {
    return (
      <ErrorBoundary>
        <LoginPage />
      </ErrorBoundary>
    )
  }

  return (
    <ErrorBoundary>
      <div className="flex h-screen overflow-hidden bg-surface-0">
        <Sidebar />

        <main className="flex-1 flex flex-col overflow-hidden relative">
          {/* Onboarding banner */}
          {showOnboard && (
            <div className="flex items-center justify-between px-4 py-2.5 bg-amber-500/10 border-b border-amber-500/20 flex-shrink-0">
              <div className="flex items-center gap-2 text-sm text-amber-300">
                <span>⚠️</span>
                <span>
                  Ollama not detected. Make sure it's running, then go to{' '}
                  <button
                    onClick={() => useStore.getState().setActiveView('settings')}
                    className="underline hover:text-white transition-colors"
                  >
                    Settings
                  </button>{' '}
                  to connect, or install a model via{' '}
                  <button
                    onClick={() => useStore.getState().setActiveView('hub')}
                    className="underline hover:text-white transition-colors"
                  >
                    Model Hub
                  </button>.
                </span>
              </div>
              <button
                onClick={() => setShowOnboard(false)}
                className="text-amber-500 hover:text-white transition-colors ml-4"
              >
                <X size={14} />
              </button>
            </div>
          )}

          {/* [P1-6] PWA update notification toast */}
          {updateReady && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 glass border border-accent-purple/30 rounded-xl px-4 py-3 shadow-xl animate-fade-in">
              <RefreshCw size={14} className="text-accent-purple" />
              <span className="text-sm text-white">Update available</span>
              <button
                onClick={handleUpdate}
                className="btn-primary text-xs py-1 px-3"
              >
                Reload to apply
              </button>
              <button
                onClick={() => setUpdateReady(false)}
                className="text-slate-500 hover:text-white transition-colors"
              >
                <X size={13} />
              </button>
            </div>
          )}

          {/* Reconnecting toast */}
          {reconnecting && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 glass border border-accent-purple/30 rounded-xl px-4 py-3 shadow-xl animate-fade-in">
              <RefreshCw size={14} className="animate-spin text-accent-purple" />
              <span className="text-sm text-white">Reconnecting…</span>
            </div>
          )}

          {/* Current view */}
          <ErrorBoundary>
            {VIEWS[activeView] ?? <DashboardView />}
          </ErrorBoundary>

          {/* PWA install prompt */}
          {installReady && !installed && (
            <div className="absolute bottom-4 right-4 glass border border-accent-purple/30 rounded-xl px-4 py-3 flex items-center gap-3 shadow-xl z-50 animate-fade-in">
              <span className="text-xl">📱</span>
              <div>
                <div className="text-xs font-medium text-white">Install KreativOS</div>
                <div className="text-xs text-slate-500">Add to home screen</div>
              </div>
              <button
                onClick={async () => {
                  const ok = await triggerInstall()
                  if (ok) setInstalled(true)
                }}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-accent-purple text-white rounded-lg text-xs font-medium"
              >
                <Download size={12} /> Install
              </button>
              <button
                onClick={() => setInstallReady(false)}
                className="text-slate-600 hover:text-white text-xl"
              >
                ×
              </button>
            </div>
          )}
        </main>
      </div>
      {permissionDialog && <PermissionDialog />}
    </ErrorBoundary>
  )
}
