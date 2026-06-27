import React, { useState, useEffect } from 'react'
import { HardDrive, Download, Trash2, RotateCcw, Plus, RefreshCw, CheckCircle } from 'lucide-react'
import clsx from 'clsx'
import api from '../utils/api'

export default function BackupView() {
  const [backups, setBackups]     = useState([])
  const [creating, setCreating]   = useState(false)
  const [restoring, setRestoring] = useState(null)
  const [msg, setMsg]             = useState(null)
  const BASE = () => localStorage.getItem('backendUrl') || 'http://localhost:8000'

  const load = async () => {
    const d = await api.get('/api/backup/list')
    setBackups(d.backups||[])
  }

  const create = async () => {
    setCreating(true); setMsg(null)
    try {
      const r = await api.post('/api/backup/create', {})
      setMsg({ type:'success', text:`✅ Backup created: ${r.filename} (${r.size_mb}MB)` })
      load()
    } catch(e) { setMsg({ type:'error', text:`❌ ${e.message}` }) }
    finally { setCreating(false) }
  }

  const del = async (filename) => {
    if (!confirm(`Delete backup ${filename}?`)) return
    await api.delete(`/api/backup/${filename}`)
    load()
  }

  const restore = async (filename) => {
    if (!confirm(`⚠️ Restore from ${filename}?\n\nThis will overwrite your current workspace. Current data will be lost if not backed up.`)) return
    setRestoring(filename)
    try {
      await api.post(`/api/backup/restore/${filename}`, {})
      setMsg({ type:'success', text:'✅ Workspace restored. Refresh the page.' })
    } catch(e) { setMsg({ type:'error', text:`❌ ${e.message}` }) }
    finally { setRestoring(null) }
  }

  const download = (filename) => {
    window.open(`${BASE()}/api/backup/download/${filename}`, '_blank')
  }

  useEffect(()=>{ load() },[])

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <HardDrive size={20} className="text-accent-cyan"/>
            <h1 className="text-xl font-bold text-white">Backup & Restore</h1>
          </div>
          <button onClick={create} disabled={creating}
            className="btn-primary flex items-center gap-2 disabled:opacity-50">
            {creating ? <><RefreshCw size={14} className="animate-spin"/>Creating…</> : <><Plus size={14}/>Create Backup</>}
          </button>
        </div>

        {msg && (
          <div className={clsx('mb-4 px-4 py-3 rounded-xl border text-sm',
            msg.type==='success' ? 'bg-green-500/10 border-green-500/20 text-green-400' : 'bg-red-500/10 border-red-500/20 text-red-400')}>
            {msg.text}
          </div>
        )}

        <div className="glass rounded-xl border border-white/10 p-4 mb-5 text-xs text-slate-400">
          <div className="flex items-start gap-2">
            <HardDrive size={13} className="text-accent-cyan mt-0.5 flex-shrink-0"/>
            <div>
              Backups include: all workspace files, project memory, scheduled tasks, prompt library, workflows, and skill scores.
              They do <strong className="text-white">not</strong> include model files (those stay in Ollama) or user passwords.
              Backups are stored on your Oracle VM at <code className="bg-surface-3 px-1 rounded">workspace/.backups/</code>
            </div>
          </div>
        </div>

        {backups.length === 0 && (
          <div className="glass rounded-2xl border border-white/10 p-10 text-center">
            <HardDrive size={40} className="mx-auto mb-3 text-slate-700"/>
            <div className="text-slate-500 text-sm">No backups yet.</div>
            <div className="text-slate-600 text-xs mt-1">Click "Create Backup" to make your first snapshot.</div>
          </div>
        )}

        <div className="space-y-3">
          {backups.map(b => (
            <div key={b.filename} className="glass rounded-xl border border-white/10 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-mono text-white truncate">{b.filename}</div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
                    <span>💾 {b.size_mb}MB</span>
                    <span>📅 {new Date(b.created).toLocaleString()}</span>
                  </div>
                </div>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button onClick={()=>download(b.filename)}
                    className="p-1.5 text-slate-400 hover:text-white hover:bg-surface-3 rounded-lg transition-all" title="Download">
                    <Download size={14}/>
                  </button>
                  <button onClick={()=>restore(b.filename)} disabled={restoring===b.filename}
                    className="p-1.5 text-slate-400 hover:text-accent-amber hover:bg-surface-3 rounded-lg transition-all" title="Restore">
                    {restoring===b.filename ? <RefreshCw size={14} className="animate-spin"/> : <RotateCcw size={14}/>}
                  </button>
                  <button onClick={()=>del(b.filename)}
                    className="p-1.5 text-slate-600 hover:text-red-400 hover:bg-surface-3 rounded-lg transition-all" title="Delete">
                    <Trash2 size={14}/>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
