import React, { useState } from 'react'
import { FileText, Table, Presentation, Download, RefreshCw, Sparkles } from 'lucide-react'
import clsx from 'clsx'
import useStore from '../store'
import api from '../utils/api'
import MessageRenderer from '../components/MessageRenderer'

const FORMATS = [
  { id:'pptx', icon:'📊', label:'PowerPoint', desc:'Slide deck with KreativOS branding', color:'#ef4444' },
  { id:'docx', icon:'📝', label:'Word Doc',   desc:'Formatted document with headings',  color:'#2563eb' },
  { id:'xlsx', icon:'📈', label:'Excel',       desc:'Spreadsheet with styled table',      color:'#16a34a' },
]

const EXAMPLES = [
  { prompt:'Create a 10-slide presentation on the future of AI agents in enterprise software', format:'pptx', title:'AI Agents in Enterprise 2024' },
  { prompt:'Write a technical project proposal for building a microservices architecture', format:'docx', title:'Microservices Project Proposal' },
  { prompt:'Create a comparison table of the top 10 JavaScript frameworks with ratings for performance, learning curve, ecosystem, and use cases', format:'xlsx', title:'JS Framework Comparison' },
  { prompt:'Build a 8-slide pitch deck for a SaaS startup that sells AI writing tools to marketing teams', format:'pptx', title:'AI Writing SaaS Pitch' },
  { prompt:'Write a comprehensive REST API documentation template with sections for authentication, endpoints, errors, and examples', format:'docx', title:'API Documentation' },
  { prompt:'Generate a monthly budget tracker with categories: Salary, Rent, Food, Transport, Entertainment, Savings for 12 months', format:'xlsx', title:'Monthly Budget 2024' },
]

export default function OfficeView() {
  const { selectedModel } = useStore()
  const [format, setFormat]   = useState('pptx')
  const [prompt, setPrompt]   = useState('')
  const [title,  setTitle]    = useState('')
  const [running, setRunning] = useState(false)
  const [result,  setResult]  = useState(null)
  const [error,   setError]   = useState('')

  const generate = async () => {
    if (!prompt.trim() || !selectedModel || running) return
    setRunning(true); setResult(null); setError('')
    try {
      const r = await api.post('/api/office/generate', {
        prompt, model: selectedModel, format, title: title || prompt.slice(0,60)
      })
      setResult(r)
    } catch(e) { setError(e.message) }
    finally { setRunning(false) }
  }

  const download = () => {
    if (!result?.filename) return
    window.open(`${localStorage.getItem('backendUrl')||'http://localhost:8000'}/api/office/download/${encodeURIComponent(result.filename)}`, '_blank')
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8">
        <div className="flex items-center gap-3 mb-2">
          <Sparkles size={20} className="text-accent-amber"/>
          <h1 className="text-xl font-bold text-white">Office File Generator</h1>
        </div>
        <p className="text-slate-500 text-sm mb-6">
          Describe what you need — the AI writes the content and generates a real downloadable file.
        </p>

        <div className="glass rounded-2xl border border-white/10 p-5 mb-5">
          {/* Format selector */}
          <div className="grid grid-cols-3 gap-3 mb-4">
            {FORMATS.map(f => (
              <button key={f.id} onClick={() => setFormat(f.id)}
                className={clsx('p-3 rounded-xl border text-left transition-all',
                  format===f.id ? 'border-white/30 bg-surface-3' : 'border-white/10 hover:border-white/20')}>
                <div className="text-2xl mb-1">{f.icon}</div>
                <div className="text-xs font-semibold text-white">{f.label}</div>
                <div className="text-xs text-slate-500 mt-0.5">{f.desc}</div>
                {format===f.id && <div className="w-2 h-2 rounded-full mt-2" style={{background:f.color}}/>}
              </button>
            ))}
          </div>

          <input className="input-base w-full mb-3" placeholder="Document title (optional)"
            value={title} onChange={e=>setTitle(e.target.value)}/>

          <textarea value={prompt} onChange={e=>setPrompt(e.target.value)} rows={4}
            placeholder={`Describe the ${FORMATS.find(f=>f.id===format)?.label} content you need…`}
            className="input-base w-full resize-none mb-3"/>

          {error && <div className="mb-3 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs">{error}</div>}

          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-600 font-mono">{selectedModel||'no model selected'}</span>
            <button onClick={generate} disabled={!prompt.trim()||!selectedModel||running}
              className="btn-primary flex items-center gap-2 disabled:opacity-30">
              {running
                ? <><RefreshCw size={14} className="animate-spin"/>Generating…</>
                : <><Sparkles size={14}/>Generate {FORMATS.find(f=>f.id===format)?.label}</>}
            </button>
          </div>
        </div>

        {/* Examples */}
        {!result && !running && (
          <div className="mb-6">
            <div className="text-xs text-slate-600 uppercase tracking-wider mb-3">Examples</div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {EXAMPLES.map((ex,i) => (
                <button key={i} onClick={()=>{setPrompt(ex.prompt);setFormat(ex.format);setTitle(ex.title)}}
                  className="glass glass-hover rounded-xl p-3 border border-white/10 text-left transition-all">
                  <div className="flex items-center gap-2 mb-1">
                    <span>{FORMATS.find(f=>f.id===ex.format)?.icon}</span>
                    <span className="text-xs font-medium text-white">{ex.title}</span>
                  </div>
                  <div className="text-xs text-slate-500 line-clamp-2">{ex.prompt}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Result */}
        {result && (
          <div className="glass rounded-2xl border border-accent-green/20 p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <span className="text-2xl">{FORMATS.find(f=>f.id===result.format)?.icon}</span>
                <div>
                  <div className="text-sm font-semibold text-white">{result.title}</div>
                  <div className="text-xs text-slate-500 font-mono">{result.filename}</div>
                </div>
              </div>
              <button onClick={download}
                className="flex items-center gap-2 px-4 py-2 bg-accent-green/20 text-accent-green hover:bg-accent-green/30 rounded-lg text-sm font-medium transition-all">
                <Download size={14}/> Download
              </button>
            </div>
            <div className="border-t border-white/10 pt-4">
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-3">AI Content Preview</div>
              <div className="max-h-80 overflow-y-auto">
                <MessageRenderer content={result.ai_output||''} />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
