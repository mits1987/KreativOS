import React, { useState, useEffect } from 'react'
import { BookOpen, Plus, Trash2, Copy, Check, Send } from 'lucide-react'
import clsx from 'clsx'
import useStore from '../store'
import api from '../utils/api'

const CATS = ['all','general','coder','researcher','architect','devops']
const CAT_ICONS = { general:'🤖', coder:'💻', researcher:'🔍', architect:'🏗️', devops:'⚙️' }

export default function PromptsView() {
  const { setActiveView, setSelectedAgent } = useStore()
  const [prompts, setPrompts] = useState([])
  const [cat, setCat]         = useState('all')
  const [showAdd, setShowAdd] = useState(false)
  const [copied, setCopied]   = useState(null)
  const [form, setForm]       = useState({ name:'', category:'general', prompt:'' })

  const load = async () => {
    const d = await api.get('/api/prompts')
    setPrompts(d.prompts||[])
  }

  const add = async () => {
    if (!form.name.trim()||!form.prompt.trim()) return
    await api.post('/api/prompts', form)
    setForm({ name:'', category:'general', prompt:'' }); setShowAdd(false); load()
  }

  const del = async (id) => {
    await api.delete(`/api/prompts/${id}`); load()
  }

  const copy = async (text, id) => {
    await navigator.clipboard.writeText(text)
    setCopied(id); setTimeout(()=>setCopied(null), 2000)
  }

  const usePrompt = (p) => {
    // Navigate to chat with this prompt pre-filled
    setSelectedAgent(p.category)
    setActiveView('chat')
    // Store prompt for chat to pick up
    localStorage.setItem('pending_prompt', p.prompt)
    window.dispatchEvent(new CustomEvent('use_prompt', { detail: p.prompt }))
  }

  useEffect(()=>{ load() },[])

  const filtered = prompts.filter(p => cat==='all' || p.category===cat)

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <BookOpen size={20} className="text-accent-amber"/>
            <h1 className="text-xl font-bold text-white">Prompt Library</h1>
          </div>
          <button onClick={()=>setShowAdd(!showAdd)} className="btn-primary text-xs flex items-center gap-1.5">
            <Plus size={12}/> Add Prompt
          </button>
        </div>

        {showAdd && (
          <div className="glass rounded-2xl border border-white/10 p-5 mb-5">
            <div className="text-sm font-medium text-white mb-4">New Prompt</div>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <input className="input-base" placeholder="Prompt name" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/>
                <select className="input-base" value={form.category} onChange={e=>setForm({...form,category:e.target.value})}>
                  {CATS.filter(c=>c!=='all').map(c=><option key={c} value={c}>{CAT_ICONS[c]} {c}</option>)}
                </select>
              </div>
              <textarea className="input-base w-full resize-none" rows={4}
                placeholder="The prompt text… use [PLACEHOLDER] for variable parts"
                value={form.prompt} onChange={e=>setForm({...form,prompt:e.target.value})}/>
              <div className="flex gap-2">
                <button onClick={add} className="btn-primary text-xs">Save</button>
                <button onClick={()=>setShowAdd(false)} className="btn-ghost text-xs">Cancel</button>
              </div>
            </div>
          </div>
        )}

        {/* Category filter */}
        <div className="flex gap-1 mb-5 overflow-x-auto pb-1">
          {CATS.map(c=>(
            <button key={c} onClick={()=>setCat(c)}
              className={clsx('px-3 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap',
                cat===c ? 'bg-surface-3 text-white' : 'text-slate-500 hover:text-white')}>
              {c==='all' ? '✨ All' : `${CAT_ICONS[c]} ${c}`}
              <span className="ml-1.5 text-slate-600">
                {c==='all' ? prompts.length : prompts.filter(p=>p.category===c).length}
              </span>
            </button>
          ))}
        </div>

        <div className="space-y-3">
          {filtered.map(p=>(
            <div key={p.id} className="glass rounded-xl border border-white/10 p-4 group hover:border-white/20 transition-all">
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-base">{CAT_ICONS[p.category]||'🤖'}</span>
                  <span className="text-sm font-semibold text-white">{p.name}</span>
                  <span className="text-xs px-1.5 py-0.5 rounded bg-surface-3 text-slate-500 capitalize">{p.category}</span>
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all">
                  <button onClick={()=>copy(p.prompt, p.id)}
                    className="p-1.5 text-slate-500 hover:text-white hover:bg-surface-3 rounded-lg transition-all">
                    {copied===p.id ? <Check size={13} className="text-accent-green"/> : <Copy size={13}/>}
                  </button>
                  <button onClick={()=>usePrompt(p)}
                    className="p-1.5 text-slate-500 hover:text-accent-purple hover:bg-surface-3 rounded-lg transition-all">
                    <Send size={13}/>
                  </button>
                  {!p.id.startsWith('pl_') && (
                    <button onClick={()=>del(p.id)}
                      className="p-1.5 text-slate-600 hover:text-red-400 hover:bg-surface-3 rounded-lg transition-all">
                      <Trash2 size={13}/>
                    </button>
                  )}
                </div>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed line-clamp-3">{p.prompt}</p>
            </div>
          ))}
          {!filtered.length && (
            <div className="text-center py-10 text-slate-600 text-sm">No prompts in this category.</div>
          )}
        </div>
      </div>
    </div>
  )
}
