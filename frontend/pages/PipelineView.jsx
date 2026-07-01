import React, { useState, useEffect } from 'react'
import { GitBranch, Play, CheckCircle, Clock, ChevronDown, ChevronRight, RotateCcw, X, Save } from 'lucide-react'
import clsx from 'clsx'
import useStore from '../store'
import api from '../utils/api'
import MessageRenderer from '../components/MessageRenderer'

const BUILTIN_TEMPLATES = {
  full_app:       { label: '🚀 Full App',        desc: 'Architect → Coder → DevOps', steps: ['Design Architecture','Write Code','Write Deployment'] },
  research_build: { label: '🔍 Research & Build', desc: 'Researcher → Architect → Coder', steps: ['Research Topic','Design Solution','Implement'] },
  code_only:      { label: '💻 Code & Deploy',    desc: 'Coder → DevOps', steps: ['Write Code','Package & Deploy'] },
  research_only:  { label: '📚 Research & Plan',  desc: 'Researcher → Orchestrator', steps: ['Research','Summarise & Plan'] },
}

const AGENT_COLORS = { architect:'#8b5cf6', coder:'#10b981', devops:'#06b6d4', researcher:'#f59e0b', orchestrator:'#ef4444' }

function PhaseCard({ phase, total }) {
  const [open, setOpen] = useState(phase.phase === total)
  return (
    <div className="border border-white/10 rounded-xl overflow-hidden">
      <div onClick={() => setOpen(!open)} className="flex items-center gap-3 p-4 cursor-pointer hover:bg-white/5 transition-all">
        <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white"
          style={{ background: AGENT_COLORS[phase.agent] || '#6366f1' }}>
          {phase.phase}
        </div>
        <div className="flex-1">
          <div className="text-sm font-medium text-white">{phase.label}</div>
          <div className="text-xs text-slate-500 capitalize">{phase.agent} agent</div>
        </div>
        {phase.ralph && (
          <span className={clsx('text-xs px-2 py-0.5 rounded-full', phase.ralph.passed ? 'bg-green-500/15 text-green-400' : 'bg-amber-500/15 text-amber-400')}>
            <RotateCcw size={10} className="inline mr-1"/>Ralph {phase.ralph.passed ? '✓' : `${phase.ralph.iterations}x`}
          </span>
        )}
        {phase.saved_files?.length > 0 && (
          <span className="text-xs text-accent-green">💾 {phase.saved_files.length} files</span>
        )}
        {open ? <ChevronDown size={14} className="text-slate-500"/> : <ChevronRight size={14} className="text-slate-500"/>}
      </div>
      {open && (
        <div className="border-t border-white/10 p-4 bg-surface-1/50">
          <MessageRenderer content={phase.output || ''} />
          {phase.saved_files?.length > 0 && (
            <div className="mt-3 pt-3 border-t border-white/10 space-y-1">
              {phase.saved_files.map(f => <div key={f} className="text-xs font-mono text-accent-green">💾 {f}</div>)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function PipelineView() {
  const { selectedModel } = useStore()
  const [task, setTask] = useState('')
  const [template, setTemplate] = useState('full_app')
  const [project, setProject] = useState('')
  const [skipRalph, setSkipRalph] = useState(false)
  const [running, setRunning] = useState(false)
  const [results, setResults] = useState([])
  const [progress, setProgress] = useState(null)
  const [userTemplates, setUserTemplates] = useState({})
  const [saveName, setSaveName] = useState('')
  const [showSave, setShowSave] = useState(false)
  const [saving, setSaving] = useState(false)

  const allTemplates = { ...BUILTIN_TEMPLATES, ...Object.fromEntries(
    Object.entries(userTemplates).map(([k, phases]) => [
      k, { label: `📋 ${k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}`,
           desc: `${phases.length} phase(s)`, steps: (phases || []).map(p => p.label), isUser: true }
    ])
  )}

  useEffect(() => {
    api.pipelines().then(data => setUserTemplates(data)).catch(() => {})
  }, [])

  const run = async () => {
    if (!task.trim() || !selectedModel || running) return
    setRunning(true); setProgress('Starting pipeline…'); setResults([])
    try {
      for await (const event of api.streamPipeline(task, selectedModel, template, project, skipRalph)) {
        if (event.type === 'start') {
          setProgress(`Running ${event.total} phases…`)
        } else if (event.type === 'phase_start') {
          setProgress(`Phase ${event.phase}: ${event.label}…`)
        } else if (event.type === 'phase_done') {
          setResults(prev => [...prev, event.phase])
          setProgress(null)
        }
      }
    } catch(e) { setProgress('Error: ' + e.message) }
    finally { setRunning(false); setProgress(null) }
  }

  const saveCurrentTemplate = async () => {
    if (!saveName.trim()) return
    setSaving(true)
    try {
      const t = allTemplates[template]
      if (!t) return
      const phases = t.steps.map((label, i) => ({ phase: i + 1, agent: 'coder', label }))
      await api.savePipeline(saveName.trim(), phases)
      const data = await api.pipelines()
      setUserTemplates(data)
      setShowSave(false)
      setSaveName('')
    } catch(e) { setProgress('Save error: ' + e.message) }
    finally { setSaving(false) }
  }

  const deleteUserTemplate = async (name) => {
    try {
      await api.deletePipeline(name)
      const data = await api.pipelines()
      setUserTemplates(data)
      if (template === name) setTemplate('full_app')
    } catch(e) { setProgress('Delete error: ' + e.message) }
  }

  const examples = [
    { task: 'Build a URL shortener web app with FastAPI and SQLite', template: 'full_app' },
    { task: 'Research best practices for building a RAG system and implement one', template: 'research_build' },
    { task: 'Create a Python CLI tool to batch rename files with regex patterns', template: 'code_only' },
    { task: 'Research the current state of AI agents in 2024 and create a detailed report', template: 'research_only' },
  ]

  const entries = Object.entries(allTemplates)

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8">
        <div className="flex items-center gap-3 mb-2">
          <GitBranch size={20} className="text-accent-purple"/>
          <h1 className="text-xl font-bold text-white">Multi-Agent Pipeline</h1>
        </div>
        <p className="text-slate-500 text-sm mb-6">Agents chain together automatically. Each phase feeds its output into the next.</p>

        <div className="glass rounded-2xl border border-white/10 p-5 mb-6">
          <div className="grid grid-cols-2 gap-2 mb-4 sm:grid-cols-4">
            {entries.map(([id, t]) => (
              <div key={id} className="relative group">
                <button onClick={() => setTemplate(id)}
                  className={clsx('w-full p-3 rounded-xl border text-left transition-all text-xs',
                    template===id ? 'border-accent-purple/50 bg-accent-purple/10' : 'border-white/10 hover:border-white/20')}>
                  <div className="font-medium text-white mb-1">{t.label}</div>
                  <div className="text-slate-500">{t.desc}</div>
                </button>
                {t.isUser && (
                  <button onClick={() => deleteUserTemplate(id)}
                    className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500/80 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Delete template">
                    <X size={10} />
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Pipeline preview */}
          <div className="flex items-center gap-1 mb-4 overflow-x-auto pb-1">
            {allTemplates[template]?.steps.map((s, i) => (
              <React.Fragment key={i}>
                <div className="flex-shrink-0 px-2.5 py-1 rounded-lg bg-surface-3 text-xs text-slate-300 whitespace-nowrap">{s}</div>
                {i < allTemplates[template].steps.length-1 && <div className="text-slate-600 flex-shrink-0">→</div>}
              </React.Fragment>
            ))}
          </div>

          <input className="input-base w-full mb-3" placeholder="Project name (optional — enables memory)" value={project} onChange={e=>setProject(e.target.value)}/>
          <textarea value={task} onChange={e=>setTask(e.target.value)} rows={3}
            placeholder="Describe what you want to build…"
            className="input-base w-full resize-none mb-3"/>
          <div className="flex justify-between items-center">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <div onClick={() => setSkipRalph(!skipRalph)}
                className={`w-8 h-4 rounded-full transition-colors ${skipRalph ? 'bg-slate-600' : 'bg-accent-purple/50'}`}>
                <div className={`w-3 h-3 rounded-full bg-white mt-0.5 ml-0.5 transition-transform ${skipRalph ? 'translate-x-4' : ''}`}/>
              </div>
              <span className="text-xs text-slate-500">Skip Ralph Loop {skipRalph ? '(faster, less refined)' : '(on)'}</span>
            </label>
            <div className="flex items-center gap-2">
              {showSave ? (
                <div className="flex items-center gap-1">
                  <input value={saveName} onChange={e=>setSaveName(e.target.value)} placeholder="Template name"
                    className="input-base text-xs w-32 py-1.5" autoFocus onKeyDown={e => e.key==='Enter' && saveCurrentTemplate()}/>
                  <button onClick={saveCurrentTemplate} disabled={saving || !saveName.trim()} className="btn-primary text-xs py-1.5 px-2">Save</button>
                  <button onClick={() => setShowSave(false)} className="btn-ghost text-xs py-1.5 px-2">Cancel</button>
                </div>
              ) : (
                <button onClick={() => setShowSave(true)} className="btn-ghost text-xs flex items-center gap-1">
                  <Save size={12}/> Save Template
                </button>
              )}
              <button onClick={run} disabled={!task.trim()||!selectedModel||running}
                className="btn-primary flex items-center gap-2 disabled:opacity-30">
                <Play size={14}/>{running?'Running pipeline…':'Run Pipeline'}
              </button>
            </div>
          </div>
        </div>

        {!results.length && !running && (
          <div className="space-y-2">
            <div className="text-xs text-slate-600 uppercase tracking-wider mb-2">Examples</div>
            {examples.map((ex,i) => (
              <button key={i} onClick={()=>{setTask(ex.task);setTemplate(ex.template)}}
                className="w-full text-left glass glass-hover rounded-xl p-3 border border-white/10">
                <div className="text-xs text-slate-500 mb-0.5">{BUILTIN_TEMPLATES[ex.template]?.label}</div>
                <div className="text-sm text-slate-300">{ex.task}</div>
              </button>
            ))}
          </div>
        )}

        {running && (
          <div className="glass rounded-xl border border-white/10 p-6 text-center">
            <div className="w-8 h-8 border-2 border-accent-purple/30 border-t-accent-purple rounded-full animate-spin mx-auto mb-3"/>
            <div className="text-sm text-slate-400">{progress || 'Agents working…'}</div>
            <div className="text-xs text-slate-600 mt-1">Each agent completes its phase before the next starts</div>
          </div>
        )}

        {results.length > 0 && (
          <div className="space-y-3">
            <div className="text-xs text-slate-600 uppercase tracking-wider">Pipeline Results</div>
            {results.map(p => <PhaseCard key={p.phase} phase={p} total={results.length}/>)}
          </div>
        )}
      </div>
    </div>
  )
}
