import React, { useState, useEffect } from 'react'
import { Clock, Plus, Trash2, Play, ToggleLeft, ToggleRight, RefreshCw, CheckCircle } from 'lucide-react'
import clsx from 'clsx'
import useStore from '../store'
import api from '../utils/api'

const AGENTS = [
  {id:'researcher',icon:'🔍',label:'Researcher'},
  {id:'coder',    icon:'💻',label:'Coder'},
  {id:'general',  icon:'🤖',label:'General'},
  {id:'devops',   icon:'⚙️',label:'DevOps'},
]

const INTERVALS = ['hourly','daily','weekly']

function timeUntil(iso) {
  if (!iso) return '—'
  const diff = new Date(iso) - new Date()
  if (diff < 0) return 'overdue'
  const h = Math.floor(diff/3600000), m = Math.floor((diff%3600000)/60000)
  if (h > 24) return `${Math.floor(h/24)}d`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

export default function SchedulerView() {
  const { selectedModel, models } = useStore()
  const [tasks, setTasks] = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [running, setRunning] = useState(false)
  const [form, setForm] = useState({ name:'', prompt:'', agent:'researcher', interval:'daily', hour:9 })

  const load = async () => {
    const d = await api.get('/api/scheduler/tasks')
    setTasks(d.tasks||[])
  }

  useEffect(() => { load() }, [])

  const add = async () => {
    if (!form.name.trim()||!form.prompt.trim()||!selectedModel) return
    await api.post('/api/scheduler/tasks', { ...form, model: selectedModel })
    setForm({ name:'', prompt:'', agent:'researcher', interval:'daily', hour:9 })
    setShowAdd(false); load()
  }

  const del = async (id) => { await api.delete(`/api/scheduler/tasks/${id}`); load() }

  const toggle = async (id) => { await api.post(`/api/scheduler/tasks/${id}/toggle`); load() }

  const runDue = async () => {
    setRunning(true)
    try { await api.post('/api/scheduler/run-due', {}); load() }
    finally { setRunning(false) }
  }

  const examples = [
    { name:'Morning AI News', prompt:'Search and summarise the top AI news from the last 24 hours. Save as a markdown report.', agent:'researcher', interval:'daily', hour:8 },
    { name:'Weekly Code Audit', prompt:'Review all Python files in the workspace for security issues and code quality. Report findings.', agent:'coder', interval:'weekly', hour:9 },
    { name:'Daily System Check', prompt:'Check the workspace directory. List all files created today. Summarise recent project activity.', agent:'general', interval:'daily', hour:7 },
  ]

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <Clock size={20} className="text-accent-cyan"/>
            <h1 className="text-xl font-bold text-white">Scheduled Tasks</h1>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={runDue} disabled={running}
              className="btn-ghost text-xs flex items-center gap-1.5">
              <RefreshCw size={12} className={running?'animate-spin':''}/> Run Due Now
            </button>
            <button onClick={()=>setShowAdd(!showAdd)} className="btn-primary text-xs flex items-center gap-1.5">
              <Plus size={12}/> Add Task
            </button>
          </div>
        </div>
        <p className="text-slate-500 text-sm mb-6">Agents run automatically on a schedule. Files are saved to workspace automatically.</p>

        {showAdd && (
          <div className="glass rounded-2xl border border-white/10 p-5 mb-5">
            <div className="text-sm font-medium text-white mb-4">New Scheduled Task</div>
            <div className="space-y-3">
              <input className="input-base w-full" placeholder="Task name (e.g. Daily AI News)" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/>
              <textarea className="input-base w-full resize-none" rows={3}
                placeholder="What should the agent do? Be specific." value={form.prompt} onChange={e=>setForm({...form,prompt:e.target.value})}/>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs text-slate-500 mb-1 block">Agent</label>
                  <select className="input-base w-full text-xs" value={form.agent} onChange={e=>setForm({...form,agent:e.target.value})}>
                    {AGENTS.map(a => <option key={a.id} value={a.id}>{a.icon} {a.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-slate-500 mb-1 block">Frequency</label>
                  <select className="input-base w-full text-xs" value={form.interval} onChange={e=>setForm({...form,interval:e.target.value})}>
                    {INTERVALS.map(i => <option key={i} value={i}>{i}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-slate-500 mb-1 block">Hour (24h)</label>
                  <input type="number" min={0} max={23} className="input-base w-full text-xs"
                    value={form.hour} onChange={e=>setForm({...form,hour:parseInt(e.target.value)||0})}/>
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={add} className="btn-primary text-xs">Save Task</button>
                <button onClick={()=>setShowAdd(false)} className="btn-ghost text-xs">Cancel</button>
              </div>
            </div>
          </div>
        )}

        {!tasks.length && !showAdd && (
          <div>
            <div className="text-xs text-slate-600 uppercase tracking-wider mb-2">Examples — click to use</div>
            {examples.map((ex,i) => (
              <button key={i} onClick={()=>{setForm({...ex});setShowAdd(true)}}
                className="w-full text-left glass glass-hover rounded-xl p-3 border border-white/10 mb-2">
                <div className="flex items-center gap-2 mb-1">
                  <span>{AGENTS.find(a=>a.id===ex.agent)?.icon}</span>
                  <span className="text-sm font-medium text-white">{ex.name}</span>
                  <span className="text-xs text-slate-500 ml-auto">{ex.interval} @ {ex.hour}:00</span>
                </div>
                <div className="text-xs text-slate-400">{ex.prompt}</div>
              </button>
            ))}
          </div>
        )}

        {tasks.length > 0 && (
          <div className="space-y-3">
            {tasks.map(t => (
              <div key={t.id} className={clsx('glass rounded-xl border p-4 transition-all',
                t.enabled ? 'border-white/10' : 'border-white/5 opacity-50')}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-base">{AGENTS.find(a=>a.id===t.agent)?.icon||'🤖'}</span>
                      <span className="text-sm font-medium text-white">{t.name}</span>
                      {t.enabled && <span className="w-2 h-2 rounded-full bg-accent-green agent-pulse"/>}
                    </div>
                    <div className="text-xs text-slate-500 mb-2 line-clamp-2">{t.prompt}</div>
                    <div className="flex items-center gap-4 text-xs text-slate-600">
                      <span>🔁 {t.interval}</span>
                      <span>⏰ {t.hour}:00</span>
                      <span>▶️ {t.run_count} runs</span>
                      <span>⏳ Next: {timeUntil(t.next_run)}</span>
                      {t.last_run && <span>✓ Last: {new Date(t.last_run).toLocaleDateString()}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button onClick={()=>toggle(t.id)} className="p-1.5 text-slate-400 hover:text-white transition-all" title={t.enabled?'Disable':'Enable'}>
                      {t.enabled ? <ToggleRight size={18} className="text-accent-green"/> : <ToggleLeft size={18}/>}
                    </button>
                    <button onClick={()=>del(t.id)} className="p-1.5 text-slate-600 hover:text-red-400 transition-all">
                      <Trash2 size={14}/>
                    </button>
                  </div>
                </div>
                {t.last_output && (
                  <div className="mt-2 pt-2 border-t border-white/10 text-xs text-slate-600 line-clamp-2 font-mono">
                    Last output: {t.last_output}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
