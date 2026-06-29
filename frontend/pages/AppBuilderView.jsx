import React, { useState } from 'react'
import { Blocks, Play, Download, Eye, FileText, RefreshCw } from 'lucide-react'
import clsx from 'clsx'
import useStore from '../store'
import api from '../utils/api'
import MessageRenderer from '../components/MessageRenderer'

const APP_TYPES = [
  { id:'web',       icon:'🌐', label:'Web App',     desc:'HTML/CSS/JS frontend' },
  { id:'api',       icon:'⚡', label:'REST API',    desc:'FastAPI or Express backend' },
  { id:'fullstack', icon:'🏗️', label:'Full Stack',  desc:'Frontend + Backend + DB' },
  { id:'cli',       icon:'⌨️', label:'CLI Tool',    desc:'Command-line Python/Bash' },
  { id:'script',    icon:'🐍', label:'Script',      desc:'Automation or data script' },
]

export default function AppBuilderView() {
  const { selectedModel } = useStore()
  const [appType, setAppType] = useState('fullstack')
  const [description, setDescription] = useState('')
  const [project, setProject] = useState('')
  const [skipRalph, setSkipRalph] = useState(false)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [previewFile, setPreviewFile] = useState(null)
  const [previewContent, setPreviewContent] = useState('')

  const build = async () => {
    if (!description.trim() || !selectedModel || running) return
    setRunning(true); setResult(null)
    try {
      const r = await api.post('/api/appbuilder/generate', {
        description, model: selectedModel, app_type: appType, project, skip_ralph: skipRalph
      })
      setResult(r)
    } catch(e) { console.error(e) }
    finally { setRunning(false) }
  }

  const preview = async (filename) => {
    const d = await api.get(`/api/appbuilder/preview/${encodeURIComponent(filename)}`)
    setPreviewFile(filename); setPreviewContent(d.content)
  }

  const downloadAll = () => {
    if (!result?.output) return
    const blob = new Blob([result.output], {type:'text/plain'})
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `${project||'app'}_output.md`; a.click()
    URL.revokeObjectURL(url)
  }

  const examples = [
    { desc: 'A todo app with FastAPI backend, SQLite database, and React frontend with add/delete/complete features', type: 'fullstack' },
    { desc: 'A REST API for a blog platform with posts, comments, and user auth using FastAPI and PostgreSQL', type: 'api' },
    { desc: 'A Python CLI tool to convert CSV files to JSON, Excel, or Markdown with filtering options', type: 'cli' },
    { desc: 'A personal finance tracker web app with budget categories, expense entry, and monthly charts', type: 'web' },
  ]

  return (
    <div className="flex h-full">
      {/* Main builder */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-8">
          <div className="flex items-center gap-3 mb-2">
            <Blocks size={20} className="text-accent-green"/>
            <h1 className="text-xl font-bold text-white">App Builder</h1>
          </div>
          <p className="text-slate-500 text-sm mb-6">Describe what you want to build. The Coder agent writes all files, Ralph Loop verifies quality.</p>

          <div className="glass rounded-2xl border border-white/10 p-5 mb-5">
            <div className="grid grid-cols-3 gap-2 mb-4 sm:grid-cols-5">
              {APP_TYPES.map(t => (
                <button key={t.id} onClick={()=>setAppType(t.id)}
                  className={clsx('p-2.5 rounded-xl border text-center transition-all',
                    appType===t.id ? 'border-accent-green/50 bg-accent-green/10' : 'border-white/10 hover:border-white/20')}>
                  <div className="text-xl mb-1">{t.icon}</div>
                  <div className="text-xs font-medium text-white">{t.label}</div>
                </button>
              ))}
            </div>

            <input className="input-base w-full mb-3" placeholder="Project name (optional)"
              value={project} onChange={e=>setProject(e.target.value)}/>

            <textarea value={description} onChange={e=>setDescription(e.target.value)} rows={4}
              placeholder="Describe your app in detail. Include features, tech preferences, and any requirements…"
              className="input-base w-full resize-none mb-3"/>

            <div className="flex justify-between items-center gap-3">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <div onClick={() => setSkipRalph(!skipRalph)}
                  className={`w-8 h-4 rounded-full transition-colors flex-shrink-0 ${skipRalph ? 'bg-slate-600' : 'bg-accent-purple/50'}`}>
                  <div className={`w-3 h-3 rounded-full bg-white mt-0.5 ml-0.5 transition-transform ${skipRalph ? 'translate-x-4' : ''}`}/>
                </div>
                <span className="text-xs text-slate-500">Skip Ralph {skipRalph ? '(fast mode)' : '(quality check on)'}</span>
              </label>
              <button onClick={build} disabled={!description.trim()||!selectedModel||running}
                className="btn-primary flex items-center gap-2 disabled:opacity-30">
                {running ? <><RefreshCw size={14} className="animate-spin"/>Building…</> : <><Play size={14}/>Build App</>}
              </button>
            </div>
          </div>

          {!result && !running && (
            <div className="space-y-2">
              <div className="text-xs text-slate-600 uppercase tracking-wider mb-2">Examples</div>
              {examples.map((ex,i) => (
                <button key={i} onClick={()=>{setDescription(ex.desc);setAppType(ex.type)}}
                  className="w-full text-left glass glass-hover rounded-xl p-3 border border-white/10">
                  <div className="text-xs text-slate-500 mb-0.5">{APP_TYPES.find(t=>t.id===ex.type)?.label}</div>
                  <div className="text-sm text-slate-300">{ex.desc}</div>
                </button>
              ))}
            </div>
          )}

          {running && (
            <div className="glass rounded-xl border border-white/10 p-8 text-center">
              <div className="w-10 h-10 border-2 border-accent-green/30 border-t-accent-green rounded-full animate-spin mx-auto mb-4"/>
              <div className="text-sm text-slate-400">Building your app…</div>
              <div className="text-xs text-slate-600 mt-1">Writing all files + Ralph Loop quality check</div>
            </div>
          )}

          {result && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <div className="text-xs text-slate-600 uppercase tracking-wider">Generated App</div>
                <div className="flex gap-2">
                  {result.ralph && (
                    <span className={clsx('text-xs px-2 py-1 rounded-full',
                      result.ralph.passed ? 'bg-green-500/15 text-green-400' : 'bg-amber-500/15 text-amber-400')}>
                      Ralph: {result.ralph.passed ? '✓ Passed' : `${result.ralph.iterations}x`}
                    </span>
                  )}
                  <button onClick={downloadAll} className="btn-ghost text-xs flex items-center gap-1">
                    <Download size={12}/>Download
                  </button>
                </div>
              </div>

              {result.saved_files?.length > 0 && (
                <div className="glass rounded-xl border border-white/10 p-4 mb-4">
                  <div className="text-xs text-slate-500 mb-2">Files saved to workspace ({result.saved_files.length}):</div>
                  <div className="grid grid-cols-2 gap-1">
                    {result.saved_files.map(f => (
                      <button key={f} onClick={()=>preview(f)}
                        className="flex items-center gap-1.5 text-xs text-accent-green hover:text-white transition-colors text-left">
                        <FileText size={10}/>
                        <span className="font-mono truncate">{f}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <MessageRenderer content={result.output||''} />
            </div>
          )}
        </div>
      </div>

      {/* Preview panel */}
      {previewFile && (
        <div className="w-96 border-l border-white/5 bg-surface-1 flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
            <span className="text-xs font-mono text-white truncate">{previewFile}</span>
            <button onClick={()=>setPreviewFile(null)} className="text-slate-500 hover:text-white text-lg">×</button>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <MessageRenderer content={`\`\`\`${previewFile.split('.').pop()}\n${previewContent}\n\`\`\``} />
          </div>
        </div>
      )}
    </div>
  )
}
