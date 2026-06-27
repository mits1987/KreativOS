import React, { useState, useEffect } from 'react'
import { Database, Plus, Trash2, RefreshCw, FileText, Lightbulb } from 'lucide-react'
import api from '../utils/api'

export default function MemoryView() {
  const [projects, setProjects] = useState([])
  const [selected, setSelected] = useState(null)
  const [memory, setMemory] = useState(null)
  const [note, setNote] = useState('')
  const [newProject, setNewProject] = useState('')

  const load = async () => {
    const d = await api.get('/api/memory/projects')
    setProjects(d.projects||[])
  }

  const loadMemory = async (p) => {
    setSelected(p)
    const d = await api.get(`/api/memory/${encodeURIComponent(p)}`)
    setMemory(d)
  }

  const addNote = async () => {
    if (!note.trim()||!selected) return
    await api.post(`/api/memory/${encodeURIComponent(selected)}/note`, {note})
    setNote(''); loadMemory(selected)
  }

  const deleteProject = async (p) => {
    if (!confirm(`Delete memory for "${p}"?`)) return
    await api.delete(`/api/memory/${encodeURIComponent(p)}`)
    if (selected===p) { setSelected(null); setMemory(null) }
    load()
  }

  useEffect(()=>{ load() },[])

  return (
    <div className="flex h-full">
      <div className="w-64 bg-surface-1 border-r border-white/5 flex flex-col">
        <div className="p-4 border-b border-white/5">
          <div className="flex items-center gap-2 mb-3">
            <Database size={16} className="text-accent-purple"/>
            <span className="text-sm font-semibold text-white">Project Memory</span>
          </div>
          <div className="flex gap-2">
            <input className="input-base flex-1 text-xs" placeholder="New project name…"
              value={newProject} onChange={e=>setNewProject(e.target.value)}
              onKeyDown={e=>{if(e.key==='Enter'&&newProject.trim()){setProjects(p=>[...new Set([...p,newProject.trim()])]);setNewProject('')}}}/>
            <button onClick={()=>{if(newProject.trim()){setProjects(p=>[...new Set([...p,newProject.trim()])]);setNewProject('')}}}
              className="p-2 bg-accent-purple/20 text-accent-purple rounded-lg hover:bg-accent-purple/30 transition-all">
              <Plus size={14}/>
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          {!projects.length && <div className="text-xs text-slate-600 text-center py-8">No projects yet.<br/>Name a project in chat to start tracking memory.</div>}
          {projects.map(p => (
            <div key={p} onClick={()=>loadMemory(p)}
              className={`group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-all ${selected===p?'bg-surface-3 text-white':'text-slate-400 hover:text-white hover:bg-surface-2'}`}>
              <Database size={12}/>
              <span className="text-xs flex-1 truncate">{p}</span>
              <button onClick={e=>{e.stopPropagation();deleteProject(p)}}
                className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-red-400 transition-all">
                <Trash2 size={11}/>
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {!selected ? (
          <div className="flex items-center justify-center h-full text-slate-600 text-sm text-center">
            <div>
              <Database size={40} className="mx-auto mb-3 opacity-20"/>
              <div>Select a project to view its memory</div>
              <div className="text-xs mt-1">Memory helps agents remember decisions across sessions</div>
            </div>
          </div>
        ) : memory && (
          <div className="max-w-2xl">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-bold text-white">{selected}</h2>
              <span className="text-xs text-slate-600">Updated: {memory.updated ? new Date(memory.updated).toLocaleString() : '—'}</span>
            </div>

            {memory.files?.length > 0 && (
              <div className="glass rounded-xl border border-white/10 p-4 mb-4">
                <div className="flex items-center gap-2 mb-2 text-xs text-slate-500 uppercase tracking-wider">
                  <FileText size={12}/> Files created ({memory.files.length})
                </div>
                <div className="flex flex-wrap gap-2">
                  {memory.files.map(f => <span key={f} className="text-xs font-mono bg-surface-3 px-2 py-1 rounded text-accent-green">{f}</span>)}
                </div>
              </div>
            )}

            {memory.decisions?.length > 0 && (
              <div className="glass rounded-xl border border-white/10 p-4 mb-4">
                <div className="flex items-center gap-2 mb-3 text-xs text-slate-500 uppercase tracking-wider">
                  <Lightbulb size={12}/> Key Decisions ({memory.decisions.length})
                </div>
                <div className="space-y-2">
                  {memory.decisions.map((d,i) => (
                    <div key={i} className="flex gap-3 text-xs">
                      <span className="text-slate-600 font-mono whitespace-nowrap">{new Date(d.time).toLocaleTimeString()}</span>
                      <span className="text-xs px-1.5 py-0.5 rounded bg-surface-3 text-accent-purple capitalize">{d.agent}</span>
                      <span className="text-slate-300">{d.text}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {memory.notes?.length > 0 && (
              <div className="glass rounded-xl border border-white/10 p-4 mb-4">
                <div className="text-xs text-slate-500 uppercase tracking-wider mb-3">Notes</div>
                {memory.notes.map((n,i) => (
                  <div key={i} className="text-xs text-slate-300 mb-1.5 flex gap-2">
                    <span className="text-slate-600 font-mono">{new Date(n.time).toLocaleTimeString()}</span>
                    <span>{n.text}</span>
                  </div>
                ))}
              </div>
            )}

            {!memory.decisions?.length && !memory.notes?.length && (
              <div className="text-center py-8 text-slate-600 text-sm">
                No memory recorded yet for this project.<br/>
                <span className="text-xs">Use the project name in Chat or Tasks to start building memory.</span>
              </div>
            )}

            <div className="flex gap-2 mt-4">
              <input className="input-base flex-1 text-sm" placeholder="Add a note to this project…"
                value={note} onChange={e=>setNote(e.target.value)}
                onKeyDown={e=>e.key==='Enter'&&addNote()}/>
              <button onClick={addNote} className="btn-primary text-xs">Add Note</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
