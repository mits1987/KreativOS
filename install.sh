import React, { useState, useEffect } from 'react'
import { Settings, CheckCircle, XCircle, RefreshCw, Trash2, Server, Brain, Database } from 'lucide-react'
import useStore from '../store'
import api from '../utils/api'

function StatusBadge({ status }) {
  if (status === 'connected') return (
    <span className="flex items-center gap-1 text-xs text-accent-green">
      <CheckCircle size={12} /> Connected
    </span>
  )
  if (status === 'disconnected') return (
    <span className="flex items-center gap-1 text-xs text-red-400">
      <XCircle size={12} /> Disconnected
    </span>
  )
  return <span className="text-xs text-slate-500">Checking…</span>
}

export default function SettingsView() {
  const {
    backendUrl, setBackendUrl, selectedModel, setSelectedModel,
    models, setModels, ollamaStatus, setOllamaStatus,
    clearConversations, conversations, setAgents, agents,
  } = useStore()

  const [urlInput, setUrlInput] = useState(backendUrl)
  const [health, setHealth] = useState(null)
  const [checking, setChecking] = useState(false)
  const [saved, setSaved] = useState(false)

  const checkHealth = async () => {
    setChecking(true)
    try {
      const h = await api.health()
      setHealth(h)
      setOllamaStatus(h.ollama === 'connected' ? 'connected' : 'disconnected')
      // Reload models
      const mdata = await api.models()
      setModels(mdata.models || [])
      if (mdata.models?.length > 0 && !selectedModel) {
        setSelectedModel(mdata.models[0])
      }
      // Reload agents
      const adata = await api.agents()
      setAgents(adata.agents || [])
    } catch (e) {
      setOllamaStatus('disconnected')
      setHealth(null)
    } finally {
      setChecking(false)
    }
  }

  const saveUrl = () => {
    setBackendUrl(urlInput.replace(/\/$/, ''))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  useEffect(() => { checkHealth() }, [])

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto px-6 py-8 space-y-6">
        <div className="flex items-center gap-3 mb-2">
          <Settings size={22} className="text-slate-400" />
          <h1 className="text-xl font-bold text-white">Settings</h1>
        </div>

        {/* Backend Connection */}
        <div className="glass rounded-2xl border border-white/10 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Server size={16} className="text-accent-blue" />
            <h2 className="font-semibold text-white">Backend Connection</h2>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-xs text-slate-500 uppercase tracking-wider mb-2 block">KrestivOS Backend URL</label>
              <div className="flex gap-2">
                <input
                  className="input-base flex-1 font-mono text-xs"
                  value={urlInput}
                  onChange={e => setUrlInput(e.target.value)}
                  placeholder="http://localhost:8000"
                />
                <button onClick={saveUrl} className="btn-primary text-xs px-4">
                  {saved ? '✓ Saved' : 'Save'}
                </button>
              </div>
              <p className="text-xs text-slate-600 mt-1">
                This is the URL of your FastAPI backend running on the Oracle VM.
              </p>
            </div>

            <div className="flex items-center justify-between p-3 bg-surface-2 rounded-xl">
              <div>
                <div className="text-sm text-white">Backend Status</div>
                <StatusBadge status={ollamaStatus === 'connected' ? 'connected' : health === null ? 'disconnected' : 'connected'} />
              </div>
              <button onClick={checkHealth} disabled={checking}
                className="btn-ghost flex items-center gap-1.5 text-xs">
                <RefreshCw size={12} className={checking ? 'animate-spin' : ''} />
                Check
              </button>
            </div>

            {health && (
              <div className="p-3 bg-surface-2 rounded-xl text-xs space-y-1 font-mono">
                <div className="flex justify-between">
                  <span className="text-slate-500">Ollama</span>
                  <span className={health.ollama === 'connected' ? 'text-accent-green' : 'text-red-400'}>{health.ollama}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Workspace</span>
                  <span className="text-slate-300 truncate ml-4">{health.workspace}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Last checked</span>
                  <span className="text-slate-400">{new Date(health.timestamp).toLocaleTimeString()}</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Model Selection */}
        <div className="glass rounded-2xl border border-white/10 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Brain size={16} className="text-accent-purple" />
            <h2 className="font-semibold text-white">Default Model</h2>
          </div>

          {models.length > 0 ? (
            <div className="space-y-2">
              {models.map(m => (
                <button key={m}
                  onClick={() => setSelectedModel(m)}
                  className={`w-full text-left px-4 py-3 rounded-xl border transition-all font-mono text-sm ${
                    selectedModel === m
                      ? 'border-accent-purple/50 bg-accent-purple/10 text-white'
                      : 'border-white/10 text-slate-400 hover:border-white/20 hover:text-white'
                  }`}>
                  {m}
                  {selectedModel === m && <span className="ml-2 text-accent-purple text-xs">● selected</span>}
                </button>
              ))}
            </div>
          ) : (
            <div className="text-center py-6 text-slate-500 text-sm">
              No models found. Make sure Ollama is running and connected.
            </div>
          )}
        </div>

        {/* Agents */}
        <div className="glass rounded-2xl border border-white/10 p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-base">🤖</span>
            <h2 className="font-semibold text-white">Available Agents</h2>
          </div>
          <div className="space-y-2">
            {agents.map(agent => (
              <div key={agent.id} className="flex items-center gap-3 p-3 bg-surface-2 rounded-xl">
                <span className="text-xl">{agent.icon}</span>
                <div>
                  <div className="text-sm text-white font-medium">{agent.name}</div>
                  <div className="text-xs text-slate-500 capitalize">{agent.id}</div>
                </div>
                <div className="ml-auto w-2 h-2 rounded-full" style={{ backgroundColor: agent.color }} />
              </div>
            ))}
          </div>
        </div>

        {/* Data */}
        <div className="glass rounded-2xl border border-white/10 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Database size={16} className="text-red-400" />
            <h2 className="font-semibold text-white">Data Management</h2>
          </div>
          <div className="flex items-center justify-between p-3 bg-surface-2 rounded-xl">
            <div>
              <div className="text-sm text-white">Chat History</div>
              <div className="text-xs text-slate-500">{conversations.length} conversation{conversations.length !== 1 ? 's' : ''} stored locally</div>
            </div>
            <button
              onClick={() => { if (confirm('Clear all chat history?')) clearConversations() }}
              className="flex items-center gap-1.5 text-xs text-red-400 hover:text-red-300 transition-colors">
              <Trash2 size={12} />
              Clear All
            </button>
          </div>
        </div>

        {/* Setup Guide */}
        <div className="glass rounded-2xl border border-white/10 p-6">
          <h2 className="font-semibold text-white mb-3">Quick Setup Reminder</h2>
          <div className="space-y-2 text-xs text-slate-400">
            {[
              'Start backend: cd backend && uvicorn main:app --host 0.0.0.0 --port 8000',
              'Start frontend: cd frontend && npm run dev',
              'Make sure Ollama is running: ollama serve',
              'Set Backend URL above to your Oracle VM IP: http://YOUR_IP:8000',
            ].map((step, i) => (
              <div key={i} className="flex gap-3 p-2 bg-surface-2 rounded-lg">
                <span className="text-accent-purple font-bold">{i + 1}.</span>
                <code className="font-mono text-xs text-slate-300 break-all">{step}</code>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
