import React, { useState, useEffect } from 'react'
import { Star, TrendingUp, TrendingDown, Minus, RefreshCw, Award, BookOpen, Zap } from 'lucide-react'
import clsx from 'clsx'
import api from '../utils/api'

const AGENT_META = {
  coder:        { icon:'💻', color:'#10b981' },
  researcher:   { icon:'🔍', color:'#f59e0b' },
  architect:    { icon:'🏗️', color:'#8b5cf6' },
  devops:       { icon:'⚙️', color:'#06b6d4' },
  orchestrator: { icon:'🎯', color:'#ef4444' },
  general:      { icon:'🤖', color:'#6366f1' },
}

const SOURCE_BADGE = {
  opencode: { label: 'OpenCode', color: '#10b981' },
  builtin:  { label: 'Built-in', color: '#6366f1' },
}

function ScoreBar({ score, color }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-surface-3 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500"
          style={{ width:`${(score/10)*100}%`, background: color }}/>
      </div>
      <span className="text-sm font-bold text-white w-8">{score}</span>
    </div>
  )
}

function TrendIcon({ trend }) {
  if (trend === 'improving') return <TrendingUp  size={14} className="text-accent-green"/>
  if (trend === 'declining') return <TrendingDown size={14} className="text-red-400"/>
  return <Minus size={14} className="text-slate-500"/>
}

function SkillCard({ skill }) {
  const [expanded, setExpanded] = useState(false)
  const badge = SOURCE_BADGE[skill.source] || SOURCE_BADGE.builtin
  return (
    <div className="glass rounded-xl border border-white/10 p-4 hover:border-white/20 transition-all cursor-pointer"
      onClick={() => setExpanded(e => !e)}>
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: badge.color + '20' }}>
          <Zap size={14} style={{ color: badge.color }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-semibold text-white">{skill.name}</span>
            <span className="text-xs px-1.5 py-0.5 rounded-full font-medium"
              style={{ background: badge.color + '20', color: badge.color }}>
              {badge.label}
            </span>
          </div>
          <p className="text-xs text-slate-500 leading-relaxed">{skill.description}</p>
          {expanded && skill.preview && (
            <pre className="mt-3 text-xs text-slate-400 bg-surface-3 rounded-lg p-3 whitespace-pre-wrap leading-relaxed border border-white/5">
              {skill.preview}
            </pre>
          )}
        </div>
      </div>
    </div>
  )
}

export default function SkillsView() {
  const [tab,      setTab]     = useState('catalog')
  const [lb,       setLb]      = useState([])
  const [catalog,  setCatalog] = useState([])
  const [detail,   setDetail]  = useState(null)
  const [loading,  setLoading] = useState(true)
  const [catError, setCatError] = useState(null)

  const loadLeaderboard = async () => {
    try {
      const d = await api.get('/api/skills/leaderboard')
      setLb(d.leaderboard || [])
    } catch(e) { console.error(e) }
  }

  const loadCatalog = async () => {
    setCatError(null)
    try {
      const d = await api.get('/api/skills/catalog')
      setCatalog(d.catalog || [])
    } catch(e) {
      setCatError(e?.message || String(e))
    }
  }

  const load = async () => {
    setLoading(true)
    await Promise.all([loadLeaderboard(), loadCatalog()])
    setLoading(false)
  }

  const loadDetail = async (agent) => {
    const d = await api.get(`/api/skills/${agent}`)
    setDetail({ agent, ...d })
  }

  useEffect(() => { load() }, [])

  return (
    <div className="flex h-full">
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <Star size={20} className="text-accent-amber"/>
              <h1 className="text-xl font-bold text-white">Skills</h1>
            </div>
            <button onClick={load} className="btn-ghost text-xs flex items-center gap-1.5">
              <RefreshCw size={12} className={loading ? 'animate-spin' : ''}/> Refresh
            </button>
          </div>

          {/* Tab switcher */}
          <div className="flex gap-1 p-1 bg-surface-2 rounded-xl mb-6 border border-white/5">
            {[
              { id:'catalog',     label:'Skills Catalog', icon:BookOpen },
              { id:'leaderboard', label:'Leaderboard',    icon:Award    },
            ].map(({ id, label, icon:Icon }) => (
              <button key={id} onClick={() => setTab(id)}
                className={clsx('flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-all',
                  tab === id ? 'bg-surface-3 text-white' : 'text-slate-500 hover:text-white')}>
                <Icon size={13}/> {label}
              </button>
            ))}
          </div>

          {/* Catalog tab */}
          {tab === 'catalog' && (
            <div className="space-y-3">
              {catError && (
                <div className="glass rounded-xl border border-red-500/20 p-4 text-center">
                  <div className="text-red-400 text-sm font-medium mb-1">Failed to load skills catalog</div>
                  <div className="text-red-500/70 text-xs font-mono mb-3">{catError}</div>
                  <div className="text-slate-500 text-xs">Restart the backend server, then click Refresh.</div>
                </div>
              )}
              {!catError && catalog.length === 0 && !loading && (
                <div className="glass rounded-2xl border border-white/10 p-10 text-center">
                  <BookOpen size={36} className="mx-auto mb-4 text-slate-700"/>
                  <div className="text-slate-500 text-sm">No skills found.</div>
                </div>
              )}
              {['opencode', 'builtin'].map(src => {
                const group = catalog.filter(s => s.source === src)
                if (!group.length) return null
                const badge = SOURCE_BADGE[src]
                return (
                  <div key={src}>
                    <div className="text-xs uppercase tracking-widest mb-2 font-medium"
                      style={{ color: badge.color }}>
                      {badge.label} Skills ({group.length})
                    </div>
                    <div className="space-y-2">
                      {group.map(skill => <SkillCard key={skill.id} skill={skill}/>)}
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* Leaderboard tab */}
          {tab === 'leaderboard' && (
            <>
              {lb.length === 0 && !loading && (
                <div className="glass rounded-2xl border border-white/10 p-10 text-center">
                  <Award size={40} className="mx-auto mb-4 text-slate-700"/>
                  <div className="text-slate-500 text-sm">No skill scores yet.</div>
                  <div className="text-slate-600 text-xs mt-1">
                    Scores appear here after agent runs via the Orchestrator.
                  </div>
                </div>
              )}

              {lb.length >= 3 && (
                <div className="flex items-end justify-center gap-4 mb-8 pt-4">
                  {[lb[1], lb[0], lb[2]].map((a, pos) => {
                    const heights = ['h-24','h-32','h-20']
                    const medals  = ['🥈','🥇','🥉']
                    const meta    = AGENT_META[a?.agent] || { icon:'🤖', color:'#6366f1' }
                    return a ? (
                      <div key={a.agent} className="flex flex-col items-center gap-2 cursor-pointer"
                        onClick={() => loadDetail(a.agent)}>
                        <div className="text-2xl">{meta.icon}</div>
                        <div className="text-xs text-white font-medium capitalize">{a.agent}</div>
                        <div className={clsx('w-20 rounded-t-xl flex items-center justify-center', heights[pos])}
                          style={{background:meta.color+'33', border:`1px solid ${meta.color}44`}}>
                          <div className="text-center">
                            <div className="text-xs">{medals[pos]}</div>
                            <div className="text-lg font-bold text-white">{a.avg_score}</div>
                          </div>
                        </div>
                      </div>
                    ) : null
                  })}
                </div>
              )}

              <div className="space-y-3">
                {lb.map((a, i) => {
                  const meta = AGENT_META[a.agent] || { icon:'🤖', color:'#6366f1' }
                  return (
                    <div key={a.agent} onClick={() => loadDetail(a.agent)}
                      className="glass rounded-xl border border-white/10 p-4 cursor-pointer hover:border-white/20 transition-all">
                      <div className="flex items-center gap-3 mb-2">
                        <span className="text-slate-600 text-sm font-mono w-4">#{i+1}</span>
                        <span className="text-base">{meta.icon}</span>
                        <span className="text-sm font-medium text-white capitalize flex-1">{a.agent}</span>
                        <TrendIcon trend={a.trend}/>
                        <span className="text-xs text-slate-500">{a.total_runs} runs</span>
                        <span className="text-xs text-slate-500">best {a.best_score}/10</span>
                      </div>
                      <ScoreBar score={a.avg_score} color={meta.color}/>
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Detail panel */}
      {detail && (
        <div className="w-80 border-l border-white/5 bg-surface-1 flex flex-col">
          <div className="flex items-center justify-between p-4 border-b border-white/5">
            <div className="flex items-center gap-2">
              <span className="text-lg">{AGENT_META[detail.agent]?.icon || '🤖'}</span>
              <span className="text-sm font-semibold text-white capitalize">{detail.agent}</span>
            </div>
            <button onClick={() => setDetail(null)} className="text-slate-500 hover:text-white text-lg">×</button>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <div className="text-xs text-slate-500 uppercase tracking-wider mb-3">Recent runs</div>
            {(detail.runs || []).slice(0, 20).map((r, i) => (
              <div key={i} className="mb-3 pb-3 border-b border-white/5 last:border-0">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    {Array.from({length:10}).map((_,j) => (
                      <div key={j} className="w-1.5 h-3 rounded-sm transition-all"
                        style={{background: j < r.score
                          ? (AGENT_META[detail.agent]?.color || '#6366f1')
                          : '#2a2a3f'}}/>
                    ))}
                    <span className="text-xs text-white ml-1">{r.score}/10</span>
                  </div>
                  <span className="text-xs text-slate-700">{new Date(r.timestamp).toLocaleDateString()}</span>
                </div>
                <div className="text-xs text-slate-500 truncate">{r.task}</div>
                {r.feedback && <div className="text-xs text-slate-400 mt-0.5 italic">{r.feedback}</div>}
              </div>
            ))}
            {!detail.runs?.length && (
              <div className="text-center py-8 text-slate-600 text-xs">No runs recorded yet</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
