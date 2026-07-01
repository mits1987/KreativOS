import React, { useState, useEffect } from 'react'
import { Settings, CheckCircle, XCircle, RefreshCw, Trash2, Server, Brain, Database } from 'lucide-react'
import useStore from '../store'
import api from '../utils/api'

function AgentModelsSection({ models, agents }) {
  const [overrides, setOverrides] = useState({})
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    api.getAgentModels().then(data => { setOverrides(data); setLoaded(true) }).catch(() => setLoaded(true))
  }, [])

  const setOverride = async (agent, model) => {
    const next = { ...overrides, [agent]: model }
    if (!model) delete next[agent]
    setOverrides(next)
    await api.setAgentModels(next)
  }

  if (!loaded) return <div className="text-xs text-slate-500 py-2">Loading...</div>

  return (
    <div className="space-y-2">
      {agents.filter(a => a.id !== 'general').map(agent => (
        <div key={agent.id} className="flex items-center gap-3 p-3 bg-surface-2 rounded-xl">
          <span className="text-base">{agent.icon}</span>
          <div className="flex-1">
            <div className="text-sm text-white font-medium">{agent.name}</div>
            <div className="text-xs text-slate-500 capitalize">{agent.id}</div>
          </div>
          <select
            value={overrides[agent.id] || ''}
            onChange={e => setOverride(agent.id, e.target.value)}
            className="text-xs bg-surface-3 border border-white/10 rounded-lg px-2 py-1.5 text-slate-300 max-w-36">
            <option value="">Use default</option>
            {models.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
      ))}
    </div>
  )
}

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
  const [checking, setChecking] = useState(false)
  const [saved, setSaved] = useState(false)

  const [agentPrompts, setAgentPrompts] = useState({})
  const [selectedAgent, setSelectedAgent] = useState('')
  const [promptText, setPromptText] = useState('')

  const [mcpServers, setMcpServers] = useState([])
  const [expandedServer, setExpandedServer] = useState('')
  const [serverTools, setServerTools] = useState({})

  const checkHealth = async () => {
    setChecking(true)
    try {
      const h = await api.health()
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
    } finally {
      setChecking(false)
    }
  }

  const savePrompt = async () => {
    if (!selectedAgent) return
    await api.post(`/api/settings/agent-prompts/${selectedAgent}`, { prompt: promptText })
    setAgentPrompts(prev => ({ ...prev, [selectedAgent]: { system: promptText } }))
  }

  const resetPrompt = async (agent) => {
    await api.delete(`/api/settings/agent-prompts/${agent}`)
    setAgentPrompts(prev => { const n = { ...prev }; delete n[agent]; return n })
    if (selectedAgent === agent) setPromptText('')
  }

  const fetchServerTools = async (name) => {
    if (serverTools[name]) return
    try {
      const data = await api.get(`/api/mcp/servers/${encodeURIComponent(name)}/tools`)
      setServerTools(prev => ({ ...prev, [name]: data.tools || [] }))
    } catch {
      setServerTools(prev => ({ ...prev, [name]: [] }))
    }
  }

  const saveUrl = () => {
    setBackendUrl(urlInput.replace(/\/$/, ''))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  useEffect(() => { checkHealth() }, [])

  useEffect(() => {
    api.get('/api/settings/agent-prompts').then(setAgentPrompts).catch(() => {})
  }, [])

  useEffect(() => {
    api.get('/api/mcp/servers').then(data => setMcpServers(data.servers || [])).catch(() => {})
  }, [])

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
              <label className="text-xs text-slate-500 uppercase tracking-wider mb-2 block">KreativOS Backend URL</label>
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
                <StatusBadge status={ollamaStatus} />
              </div>
              <button onClick={checkHealth} disabled={checking}
                className="btn-ghost flex items-center gap-1.5 text-xs">
                <RefreshCw size={12} className={checking ? 'animate-spin' : ''} />
                Check
              </button>
            </div>


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

        {/* Agent Models */}
        <div className="glass rounded-2xl border border-white/10 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Brain size={16} className="text-accent-purple" />
            <h2 className="font-semibold text-white">Agent Models</h2>
          </div>
          <p className="text-xs text-slate-500 mb-4">Override the default model per agent. Each agent will use its assigned model instead of the default.</p>
          <AgentModelsSection models={models} agents={agents} />
        </div>

        {/* Agent Prompts */}
        <div className="glass rounded-2xl border border-white/10 p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-base">📝</span>
            <h2 className="font-semibold text-white">Agent Prompts</h2>
          </div>
          <p className="text-xs text-slate-500 mb-4">Override system prompts per agent. Leave empty to use defaults.</p>
          <div className="space-y-3">
            <select
              value={selectedAgent}
              onChange={e => {
                setSelectedAgent(e.target.value)
                setPromptText(agentPrompts[e.target.value]?.system || '')
              }}
              className="w-full text-sm bg-surface-3 border border-white/10 rounded-xl px-3 py-2 text-slate-300">
              <option value="">Select an agent…</option>
              {agents.filter(a => a.id !== 'general').map(a => (
                <option key={a.id} value={a.id}>{a.name} ({a.id})</option>
              ))}
            </select>
            {selectedAgent && (
              <>
                <textarea
                  value={promptText}
                  onChange={e => setPromptText(e.target.value)}
                  rows={8}
                  className="w-full text-xs font-mono bg-surface-3 border border-white/10 rounded-xl px-3 py-2 text-slate-300 resize-y"
                  placeholder={`Default prompt for ${selectedAgent}…`}
                />
                <div className="flex gap-2">
                  <button onClick={savePrompt} className="btn-primary text-xs px-4 py-2">
                    Save Override
                  </button>
                  <button
                    onClick={() => resetPrompt(selectedAgent)}
                    className="btn-ghost text-xs px-4 py-2 text-red-400 hover:text-red-300">
                    Reset to Default
                  </button>
                </div>
                {agentPrompts[selectedAgent] && (
                  <div className="text-xs text-accent-green">✓ Custom prompt saved</div>
                )}
              </>
            )}
          </div>
        </div>

        {/* MCP Servers */}
        <div className="glass rounded-2xl border border-white/10 p-6">
          <div className="flex items-center gap-2 mb-4">
            <Server size={16} className="text-accent-cyan" />
            <h2 className="font-semibold text-white">MCP Servers</h2>
          </div>
          {mcpServers.length > 0 ? (
            <div className="space-y-2">
              {mcpServers.map(server => (
                <div key={server.name} className="bg-surface-2 rounded-xl overflow-hidden">
                  <button
                    onClick={() => {
                      if (expandedServer === server.name) {
                        setExpandedServer('')
                        return
                      }
                      setExpandedServer(server.name)
                      fetchServerTools(server.name)
                    }}
                    className="w-full flex items-center gap-3 p-3 text-left">
                    <div className={`w-2 h-2 rounded-full ${server.status === 'connected' ? 'bg-accent-green' : 'bg-red-400'}`} />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-white font-medium">{server.name}</div>
                      <div className="text-xs text-slate-500 truncate">{server.url}</div>
                    </div>
                    <span className="text-xs text-slate-400">{server.tools} tool{server.tools !== 1 ? 's' : ''}</span>
                  </button>
                  {expandedServer === server.name && (
                    <div className="px-3 pb-3 space-y-1">
                      {serverTools[server.name]?.length > 0 ? (
                        serverTools[server.name].map(tool => (
                          <div key={tool.name} className="text-xs bg-surface-3 rounded-lg p-2">
                            <span className="text-accent-purple font-mono">{tool.name}</span>
                            {tool.description && <p className="text-slate-500 mt-0.5">{tool.description}</p>}
                          </div>
                        ))
                      ) : (
                        <div className="text-xs text-slate-500 py-2 text-center">No tools available</div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-6 text-slate-500 text-sm">
              No MCP servers configured.
            </div>
          )}
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
