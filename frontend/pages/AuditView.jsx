import React, { useState, useEffect } from 'react'
import { Shield, Search, RefreshCw, Activity } from 'lucide-react'
import api from '../utils/api'

const ACTION_COLORS = {
  chat:'#6366f1', task_start:'#f59e0b', task_done:'#10b981',
  file_saved:'#06b6d4', code_exec:'#8b5cf6', ralph_loop:'#ec4899',
  office_generate:'#ef4444', backup_create:'#84cc16', skill_graded:'#f97316',
  pipeline_start:'#a78bfa', scheduler_auto_ran:'#34d399',
}

export default function AuditView() {
  const [entries, setEntries] = useState([])
  const [stats,   setStats]   = useState({})
  const [query,   setQuery]   = useState('')
  const [loading, setLoading] = useState(true)

  const load = async (q='') => {
    setLoading(true)
    try {
      const d = await api.get(`/api/audit?n=200${q?`&q=${encodeURIComponent(q)}`:''}`)
      setEntries(d.entries||[])
      if (d.stats) setStats(d.stats)
    } catch(e) { console.error(e) }
    finally { setLoading(false) }
  }

  useEffect(()=>{ load() },[])

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Shield size={20} className="text-accent-green"/>
            <h1 className="text-xl font-bold text-white">Audit Trail</h1>
          </div>
          <button onClick={()=>load(query)} className="btn-ghost text-xs flex items-center gap-1.5">
            <RefreshCw size={12} className={loading?'animate-spin':''}/> Refresh
          </button>
        </div>

        {/* Stats */}
        {stats.total_entries > 0 && (
          <div className="grid grid-cols-2 gap-3 mb-5 sm:grid-cols-4">
            <div className="glass rounded-xl border border-white/10 p-3">
              <div className="text-xs text-slate-500">Total events</div>
              <div className="text-xl font-bold text-white">{stats.total_entries}</div>
            </div>
            {Object.entries(stats.top_actions||{}).slice(0,3).map(([action,count])=>(
              <div key={action} className="glass rounded-xl border border-white/10 p-3">
                <div className="text-xs text-slate-500 truncate">{action.replace(/_/g,' ')}</div>
                <div className="text-xl font-bold text-white">{count}</div>
              </div>
            ))}
          </div>
        )}

        {/* Search */}
        <div className="flex gap-2 mb-5">
          <div className="relative flex-1">
            <Search size={13} className="absolute left-3 top-3 text-slate-500"/>
            <input className="input-base w-full pl-9 text-sm" placeholder="Search events, agents, actions…"
              value={query} onChange={e=>setQuery(e.target.value)}
              onKeyDown={e=>e.key==='Enter'&&load(query)}/>
          </div>
          <button onClick={()=>load(query)} className="btn-primary text-xs px-4">Search</button>
          {query && <button onClick={()=>{setQuery('');load('')}} className="btn-ghost text-xs">Clear</button>}
        </div>

        {/* Entries */}
        {entries.length === 0 && !loading && (
          <div className="glass rounded-2xl border border-white/10 p-10 text-center">
            <Activity size={36} className="mx-auto mb-3 text-slate-700"/>
            <div className="text-slate-500 text-sm">No audit entries yet.</div>
            <div className="text-slate-600 text-xs mt-1">All actions will appear here as you use KreativOS.</div>
          </div>
        )}

        <div className="space-y-1">
          {entries.map((e,i)=>{
            const color = ACTION_COLORS[e.action] || '#64748b'
            return (
              <div key={i} className="flex items-start gap-3 py-2.5 border-b border-white/5 last:border-0 hover:bg-white/3 rounded-lg px-2 transition-all">
                <div className="w-2 h-2 rounded-full flex-shrink-0 mt-1.5" style={{background:color}}/>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-medium text-white">{e.action.replace(/_/g,' ')}</span>
                    {e.agent && <span className="text-xs px-1.5 py-0.5 rounded bg-surface-3 text-slate-400 capitalize">{e.agent}</span>}
                    {e.detail && <span className="text-xs text-slate-500 truncate">{e.detail}</span>}
                  </div>
                </div>
                <span className="text-xs text-slate-700 font-mono flex-shrink-0 whitespace-nowrap">
                  {new Date(e.ts).toLocaleTimeString()}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
