import React, { useState } from 'react'
import { Eye, Upload, RefreshCw, AlertTriangle, Info, CheckCircle } from 'lucide-react'
import useStore from '../store'
import api from '../utils/api'
import MessageRenderer from '../components/MessageRenderer'

const LANGS = ['python','javascript','typescript','bash','go','rust','java','cpp','sql','yaml']

export default function CodeReviewView() {
  const { selectedModel } = useStore()
  const [code, setCode] = useState('')
  const [language, setLanguage] = useState('python')
  const [filename, setFilename] = useState('')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)

  const review = async () => {
    if (!code.trim() || !selectedModel || running) return
    setRunning(true); setResult(null)
    try {
      const r = await api.post('/api/review', { code, language, model: selectedModel, filename })
      setResult(r)
    } catch(e) { console.error(e) }
    finally { setRunning(false) }
  }

  const loadFile = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    const text = await file.text()
    setCode(text)
    setFilename(file.name)
    const ext = file.name.split('.').pop().toLowerCase()
    const langMap = {py:'python',js:'javascript',ts:'typescript',sh:'bash',go:'go',rs:'rust',java:'java',cpp:'cpp',sql:'sql',yml:'yaml',yaml:'yaml'}
    if (langMap[ext]) setLanguage(langMap[ext])
  }

  const exampleCode = `def calculate_discount(price, discount_percent, user):
    # Apply discount
    if discount_percent > 0:
        discounted = price - (price * discount_percent / 100)
        query = f"UPDATE orders SET price={discounted} WHERE user='{user}'"
        db.execute(query)
        return discounted`

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8">
        <div className="flex items-center gap-3 mb-2">
          <Eye size={20} className="text-orange-400"/>
          <h1 className="text-xl font-bold text-white">Code Review</h1>
        </div>
        <p className="text-slate-500 text-sm mb-6">Paste code or upload a file. The Code Reviewer agent finds bugs, security issues, and suggests improvements.</p>

        <div className="glass rounded-2xl border border-white/10 p-5 mb-5">
          <div className="flex items-center gap-3 mb-3">
            <select value={language} onChange={e=>setLanguage(e.target.value)} className="input-base text-xs">
              {LANGS.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
            <input className="input-base flex-1 text-xs" placeholder="filename (optional)"
              value={filename} onChange={e=>setFilename(e.target.value)}/>
            <label className="btn-ghost text-xs flex items-center gap-1 cursor-pointer">
              <Upload size={12}/>Upload
              <input type="file" className="hidden" onChange={loadFile} accept=".py,.js,.ts,.sh,.go,.rs,.java,.cpp,.sql,.yml,.yaml,.txt"/>
            </label>
          </div>

          <textarea value={code} onChange={e=>setCode(e.target.value)} rows={10}
            placeholder={`Paste your ${language} code here…`}
            className="input-base w-full resize-none font-mono text-xs leading-relaxed mb-3"/>

          <div className="flex items-center justify-between">
            <button onClick={()=>setCode(exampleCode)} className="text-xs text-slate-600 hover:text-slate-400 transition-colors">
              Load example (has SQL injection bug)
            </button>
            <button onClick={review} disabled={!code.trim()||!selectedModel||running}
              className="btn-primary flex items-center gap-2 disabled:opacity-30">
              {running ? <><RefreshCw size={14} className="animate-spin"/>Reviewing…</> : <><Eye size={14}/>Review Code</>}
            </button>
          </div>
        </div>

        {running && (
          <div className="glass rounded-xl border border-white/10 p-8 text-center">
            <div className="w-8 h-8 border-2 border-orange-400/30 border-t-orange-400 rounded-full animate-spin mx-auto mb-3"/>
            <div className="text-sm text-slate-400">Reviewing your code…</div>
          </div>
        )}

        {result && (
          <div>
            <div className="text-xs text-slate-600 uppercase tracking-wider mb-3">Review Results</div>
            <MessageRenderer content={result.review||''} />
          </div>
        )}
      </div>
    </div>
  )
}
