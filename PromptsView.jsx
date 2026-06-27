import React, { useEffect, useState } from 'react'
import Sidebar        from './components/Sidebar'
import DashboardView  from './pages/DashboardView'
import ChatView       from './pages/ChatView'
import TasksView      from './pages/TasksView'
import PipelineView   from './pages/PipelineView'
import CanvasView     from './pages/CanvasView'
import AppBuilderView from './pages/AppBuilderView'
import OfficeView     from './pages/OfficeView'
import CodeReviewView from './pages/CodeReviewView'
import FilesView      from './pages/FilesView'
import MemoryView     from './pages/MemoryView'
import SkillsView     from './pages/SkillsView'
import ModelHubView   from './pages/ModelHubView'
import SchedulerView  from './pages/SchedulerView'
import PromptsView    from './pages/PromptsView'
import AuditView      from './pages/AuditView'
import BackupView     from './pages/BackupView'
import TelegramView   from './pages/TelegramView'
import UsersView      from './pages/UsersView'
import SettingsView   from './pages/SettingsView'
import useStore from './store'
import api from './utils/api'
import { setupInstallPrompt, triggerInstall, isPWAInstalled } from './pwa.js'
import { Download } from 'lucide-react'

export default function App() {
  const {
    activeView, setModels, setAgents, setOllamaStatus,
    selectedModel, setSelectedModel, conversations, createConversation,
  } = useStore()
  const [installReady, setInstallReady] = useState(false)
  const [installed, setInstalled]       = useState(isPWAInstalled())

  useEffect(() => {
    const init = async () => {
      try {
        const [mdata, adata, health] = await Promise.all([
          api.models(), api.agents(), api.health()
        ])
        setModels(mdata.models || [])
        setAgents(adata.agents || [])
        setOllamaStatus(health.ollama === 'connected' ? 'connected' : 'disconnected')
        if (mdata.models?.length > 0 && !selectedModel) setSelectedModel(mdata.models[0])
      } catch { setOllamaStatus('disconnected') }
    }
    init()
    setupInstallPrompt(setInstallReady)
  }, [])

  useEffect(() => {
    if (conversations.length === 0 && activeView === 'chat') createConversation()
  }, [activeView])

  // Handle PWA shortcut ?view= param
  useEffect(() => {
    const v = new URLSearchParams(window.location.search).get('view')
    if (v) useStore.getState().setActiveView(v)
  }, [])

  const views = {
    dashboard:   <DashboardView />,
    chat:        <ChatView />,
    tasks:       <TasksView />,
    pipeline:    <PipelineView />,
    canvas:      <CanvasView />,
    appbuilder:  <AppBuilderView />,
    office:      <OfficeView />,
    codereview:  <CodeReviewView />,
    files:       <FilesView />,
    memory:      <MemoryView />,
    skills:      <SkillsView />,
    hub:         <ModelHubView />,
    scheduler:   <SchedulerView />,
    prompts:     <PromptsView />,
    audit:       <AuditView />,
    backup:      <BackupView />,
    telegram:    <TelegramView />,
    users:       <UsersView />,
    settings:    <SettingsView />,
  }

  return (
    <div className="flex h-screen overflow-hidden bg-surface-0">
      <Sidebar />
      <main className="flex-1 flex flex-col overflow-hidden relative">
        {views[activeView] || <DashboardView />}
        {installReady && !installed && (
          <div className="absolute bottom-4 right-4 glass border border-accent-purple/30 rounded-xl px-4 py-3 flex items-center gap-3 shadow-xl z-50 animate-fade-in">
            <span className="text-xl">📱</span>
            <div>
              <div className="text-xs font-medium text-white">Install KrestivOS</div>
              <div className="text-xs text-slate-500">Add to home screen</div>
            </div>
            <button onClick={async()=>{ const ok=await triggerInstall(); if(ok)setInstalled(true) }}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-accent-purple text-white rounded-lg text-xs font-medium">
              <Download size={12}/> Install
            </button>
            <button onClick={()=>setInstallReady(false)} className="text-slate-600 hover:text-white text-xl">×</button>
          </div>
        )}
      </main>
    </div>
  )
}
