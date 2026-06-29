import React, { useState, useEffect } from 'react'
import { Network, Plus, Trash2, RefreshCw, ChevronDown, ChevronRight, CheckCircle, XCircle, Circle } from 'lucide-react'
import clsx from 'clsx'
import api from '../utils/api'

function StatusBadge({ status }) {
  if (status === 'connected')    return <span className="flex items-center gap-1 text-xs text-emerald-400"><CheckCircle size={11}/>Connected</span>
  if (status === 'error')        return <span className="flex items-center gap-1 text-xs text-red-400"><XCircle size={11}/>Offline</span>
  return <span className="flex items-center gap-1 text-xs text-slate-500"><Circle size={11}/>Unknown</span>
}

const EMPTY = { name: '', url: '', description: '', enabled: true }

export default function MCPView() {
  const [servers,  setServers]  = useState([])
  const [loading,  setLoading]  = useState(true)
  const [adding,   setAdding]   = useState(false)
  const [form,     setForm]     = useState(EMPTY)
  const [statuses, setStatuses] = useState({})   // name → {status, tools}
  const [expanded, setExpanded] = useState({})

  const load = async () => {
    setLoading(true)
    try {
      const d = await api.get('/api/mcp/servers')
      setServers(d.servers || [])
    } catch(e) { console.error(e) }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const test = async (server) => {
    setStatuses(s => ({ ...s, [server.name]: { status: 'checking', tools: [] } }))
    try {
      const d = await api.get(`/api/mcp/servers/${encodeURIComponent(server.name)}/tools`)
      setStatuses(s => ({ ...s, [server.name]: { status: 'connected', tools: d.tools || [] } }))
    } catch {
      setStatuses(s => ({ ...s, [server.name]: { status: 'error', tools: [] } }))
    }
  }

  const add = async () => {
    if (!form.name || !form.url) return
    try {
      await api.post('/api/mcp/servers', form)
      setAdding(false)
      setForm(EMPTY)
      load()
    } catch(e) { alert(e.message) }
  }

  const remove = async (name) => {
    if (!confirm(`Remove "${name}"?`)) return
    await api.delete(`/api/mcp/servers/${encodeURIComponent(name)}`)
    load()
  }

  const toggle = (name) => setExpanded(e => ({ ...e, [name]: !e[name] }))

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Network size={20} className="text-accent-purple"/>
            <h1 className="text-xl font-bold text-white">MCP Servers</h1>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={load} className="btn-ghost text-xs flex items-center gap-1.5">
              <RefreshCw size={12} className={loading ? 'animate-spin' : ''}/>Refresh
            </button>
            <button onClick={() => setAdding(a => !a)} className="btn-primary text-xs flex items-center gap-1.5">
              <Plus size={12}/>Add Server
            </button>
          </div>
        </div>

        {/* Add form */}
        {adding && (
          <div className="glass rounded-xl border border-accent-purple/20 p-4 mb-4 space-y-3">
            <div className="text-xs font-semibold text-white mb-2">New MCP Server</div>
            {[
              ['name',        'Name (e.g. open-design)',          'text'],
              ['url',         'URL (e.g. http://localhost:7456/mcp)', 'text'],
              ['description', 'Description (optional)',           'text'],
            ].map(([key, placeholder]) => (
              <input key={key} className="input-base w-full text-xs" placeholder={placeholder}
                value={form[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}/>
            ))}
            <div className="flex gap-2 justify-end">
              <button onClick={() => { setAdding(false); setForm(EMPTY) }} className="btn-ghost text-xs">Cancel</button>
              <button onClick={add} disabled={!form.name || !form.url} className="btn-primary text-xs disabled:opacity-40">Add</button>
            </div>
          </div>
        )}

        {/* Server list */}
        {!loading && servers.length === 0 && (
          <div className="glass rounded-2xl border border-white/10 p-10 text-center">
            <Network size={36} className="mx-auto mb-4 text-slate-700"/>
            <div className="text-slate-500 text-sm">No MCP servers configured.</div>
            <div className="text-slate-600 text-xs mt-1">Add Open Design or any other MCP server above.</div>
          </div>
        )}

        <div className="space-y-2">
          {servers.map(srv => {
            const st = statuses[srv.name]
            const isExpanded = expanded[srv.name]
            return (
              <div key={srv.name} className="glass rounded-xl border border-white/10 overflow-hidden">
                <div className="flex items-center gap-3 p-4">
                  <button onClick={() => toggle(srv.name)} className="text-slate-500 hover:text-white transition-colors">
                    {isExpanded ? <ChevronDown size={14}/> : <ChevronRight size={14}/>}
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-white">{srv.name}</span>
                      {!srv.enabled && <span className="text-xs text-slate-600 bg-surface-3 px-1.5 py-0.5 rounded">disabled</span>}
                    </div>
                    <div className="text-xs text-slate-500 font-mono truncate mt-0.5">{srv.url}</div>
                    {srv.description && <div className="text-xs text-slate-600 mt-0.5">{srv.description}</div>}
                  </div>
                  <StatusBadge status={st?.status}/>
                  <button onClick={() => test(srv)}
                    disabled={st?.status === 'checking'}
                    className="btn-ghost text-xs flex items-center gap-1 disabled:opacity-40">
                    {st?.status === 'checking'
                      ? <RefreshCw size={11} className="animate-spin"/>
                      : <RefreshCw size={11}/>}
                    Test
                  </button>
                  <button onClick={() => remove(srv.name)} className="text-slate-600 hover:text-red-400 transition-colors p-1">
                    <Trash2 size={13}/>
                  </button>
                </div>

                {isExpanded && (
                  <div className="border-t border-white/5 bg-surface-2/50 p-4">
                    {!st && <div className="text-xs text-slate-500">Click Test to discover available tools.</div>}
                    {st?.status === 'error' && (
                      <div className="text-xs text-red-400">Server unreachable. Check that it's running at <code className="font-mono">{srv.url}</code></div>
                    )}
                    {st?.tools?.length > 0 && (
                      <div>
                        <div className="text-xs text-slate-500 uppercase tracking-widest mb-2">{st.tools.length} tools available</div>
                        <div className="space-y-1.5">
                          {st.tools.map(t => (
                            <div key={t.name} className="text-xs">
                              <span className="text-accent-purple font-mono">{t.name}</span>
                              {t.description && <span className="text-slate-500 ml-2">— {t.description}</span>}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {st?.status === 'connected' && st.tools.length === 0 && (
                      <div className="text-xs text-slate-500">Connected but no tools exposed.</div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Usage hint */}
        <div className="mt-6 glass rounded-xl border border-white/5 p-4 text-xs text-slate-600 space-y-1">
          <div className="text-slate-400 font-medium mb-2">Using MCP tools in agents</div>
          <div>Orchestrator agents can call MCP tools automatically. In Chat, try:</div>
          <code className="block bg-surface-3 rounded px-2 py-1 mt-1 text-slate-300">"Using open-design, generate a prototype for a SaaS dashboard"</code>
          <div className="mt-2">Or start Open Design daemon: <code className="text-slate-300">od mcp install claude</code></div>
        </div>
      </div>
    </div>
  )
}
