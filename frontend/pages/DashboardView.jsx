import React, { useState, useEffect, useCallback } from 'react'
import {
  Activity, Zap, FileText, Terminal, RefreshCw,
  Brain, CheckCircle, RotateCcw, Clock, TrendingUp
} from 'lucide-react'
import api from '../utils/api'
import useStore from '../store'

const AGENT_ICONS = { coder:'💻', researcher:'🔍', architect:'🏗️', orchestrator:'🎯', devops:'⚙️', general:'🤖' }

function StatCard({ icon: Icon, label, value, color, sub }) {
  return (
    <div style={{ borderColor: color + '22' }}
      className="glass rounded-2xl border p-5 flex items-start gap-4">
      <div className="p-2 rounded-xl" style={{ background: color + '18' }}>
        <Icon size={20} style={{ color }} />
      </div>
      <div>
        <div className="text-2xl font-bold text-white">{value ?? '—'}</div>
        <div className="text-xs text-slate-500 mt-0.5">{label}</div>
        {sub && <div className="text-xs text-slate-600 mt-1">{sub}</div>}
      </div>
    </div>
  )
}

function ActivityFeed({ items }) {
  const icons = {
    chat:              '💬',
    task_start:        '⚡',
    task_done:         '✅',
    file_saved:        '💾',
    code_exec:         '▶️',
    ralph_loop_start:  '🔄',
    ralph_iteration:   '🔁',
    ralph_loop_pass:   '✅',
    ralph_fix_applied: '🔧',
  }
  if (!items?.length) return (
    <div className="text-center py-10 text-slate-600 text-sm">No activity yet. Start a chat or run a task.</div>
  )
  return (
    <div className="space-y-1">
      {items.map((a, i) => (
        <div key={i} className="flex items-center gap-3 py-2 border-b border-white/5 last:border-0">
          <span className="text-base w-6 text-center">{icons[a.event] || '•'}</span>
          <div className="flex-1 min-w-0">
            <span className="text-xs text-slate-300 font-medium">{a.event.replace(/_/g, ' ')}</span>
            {a.detail && <span className="text-xs text-slate-600 ml-2 truncate">{a.detail}</span>}
          </div>
          <span className="text-xs text-slate-700 font-mono flex-shrink-0">{a.time}</span>
        </div>
      ))}
    </div>
  )
}

function AgentBar({ tasksBy }) {
  const agents = Object.entries(tasksBy || {})
  if (!agents.length) return <div className="text-xs text-slate-600 py-4 text-center">No tasks run yet</div>
  const max = Math.max(...agents.map(([,v]) => v), 1)
  return (
    <div className="space-y-3">
      {agents.sort((a,b) => b[1]-a[1]).map(([agent, count]) => (
        <div key={agent} className="flex items-center gap-3">
          <span className="text-sm w-5">{AGENT_ICONS[agent] || '🤖'}</span>
          <span className="text-xs text-slate-400 w-24 capitalize">{agent}</span>
          <div className="flex-1 bg-surface-3 rounded-full h-2">
            <div className="h-2 rounded-full bg-accent-purple transition-all"
              style={{ width: `${(count/max)*100}%` }} />
          </div>
          <span className="text-xs text-slate-500 w-6 text-right">{count}</span>
        </div>
      ))}
    </div>
  )
}

function UptimeDisplay({ seconds }) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  return <span>{h > 0 ? `${h}h ` : ''}{m > 0 ? `${m}m ` : ''}{s}s</span>
}

export default function DashboardView() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState(null)
  const { ollamaStatus, models, selectedModel } = useStore()

  const load = useCallback(async () => {
    try {
      const d = await api.get('/api/dashboard')
      setData(d)
      setLastRefresh(new Date())
    } catch (e) {
      console.error('Dashboard load failed', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, 10000)
    return () => clearInterval(t)
  }, [load])

  const s = data?.stats || {}
  const uptime = s.uptime_seconds || 0

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 py-8">

        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <div className="flex items-center gap-3">
              <Brain size={24} className="text-accent-purple" />
              <h1 className="text-2xl font-bold text-white">KreativOS Dashboard</h1>
              <span className="tag bg-accent-purple/20 text-accent-purple text-xs px-2 py-0.5 rounded-full">v2.0</span>
            </div>
            <p className="text-slate-500 text-sm mt-1">
              System overview · Auto-refreshes every 10s
              {lastRefresh && <span className="ml-2 text-slate-700">Last: {lastRefresh.toLocaleTimeString()}</span>}
            </p>
          </div>
          <button onClick={load} className="btn-ghost flex items-center gap-2">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        {/* System status row */}
        <div className="grid grid-cols-2 gap-3 mb-6 sm:grid-cols-4">
          <div className={`glass rounded-xl p-4 border flex items-center gap-3 ${ollamaStatus === 'connected' ? 'border-green-500/20' : 'border-red-500/20'}`}>
            <div className={`w-2.5 h-2.5 rounded-full ${ollamaStatus === 'connected' ? 'bg-accent-green' : 'bg-red-500'}`} />
            <div>
              <div className="text-xs text-slate-500">Ollama</div>
              <div className="text-sm font-medium text-white capitalize">{ollamaStatus}</div>
            </div>
          </div>
          <div className="glass rounded-xl p-4 border border-white/10 flex items-center gap-3">
            <Brain size={16} className="text-accent-purple" />
            <div>
              <div className="text-xs text-slate-500">Model</div>
              <div className="text-sm font-mono text-white truncate">{selectedModel || '—'}</div>
            </div>
          </div>
          <div className="glass rounded-xl p-4 border border-white/10 flex items-center gap-3">
            <FileText size={16} className="text-accent-amber" />
            <div>
              <div className="text-xs text-slate-500">Models available</div>
              <div className="text-sm font-bold text-white">{models.length}</div>
            </div>
          </div>
          <div className="glass rounded-xl p-4 border border-white/10 flex items-center gap-3">
            <Clock size={16} className="text-accent-cyan" />
            <div>
              <div className="text-xs text-slate-500">Uptime</div>
              <div className="text-sm font-mono text-white"><UptimeDisplay seconds={uptime} /></div>
            </div>
          </div>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-2 gap-4 mb-6 sm:grid-cols-3">
          <StatCard icon={Activity}    label="Total messages"     value={s.total_messages}      color="#6366f1" />
          <StatCard icon={Zap}         label="Tasks run"          value={s.total_tasks}          color="#f59e0b" />
          <StatCard icon={FileText}    label="Files in workspace" value={s.workspace_files}      color="#10b981" />
          <StatCard icon={RotateCcw}   label="Ralph Loops run"    value={s.ralph_loops_run}      color="#8b5cf6" sub="Auto quality checks" />
          <StatCard icon={CheckCircle} label="Auto-fixes applied" value={s.ralph_fixes_applied}  color="#ec4899" sub="By self-critic + QA" />
          <StatCard icon={Terminal}    label="Code executions"    value={s.code_executions}      color="#06b6d4" />
        </div>

        {/* Bottom row: agent usage + activity feed */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="glass rounded-2xl border border-white/10 p-5">
            <div className="flex items-center gap-2 mb-4">
              <TrendingUp size={16} className="text-accent-purple" />
              <span className="text-sm font-medium text-white">Agent usage</span>
            </div>
            <AgentBar tasksBy={s.tasks_by_agent} />
          </div>

          <div className="glass rounded-2xl border border-white/10 p-5">
            <div className="flex items-center gap-2 mb-4">
              <Activity size={16} className="text-accent-green" />
              <span className="text-sm font-medium text-white">Live activity</span>
            </div>
            <div className="max-h-64 overflow-y-auto">
              <ActivityFeed items={data?.recent_activity} />
            </div>
          </div>
        </div>

        {/* Ralph Loop explainer */}
        <div className="mt-4 glass rounded-2xl border border-accent-purple/20 p-5">
          <div className="flex items-start gap-3">
            <RotateCcw size={18} className="text-accent-purple mt-0.5 flex-shrink-0" />
            <div>
              <div className="text-sm font-medium text-white mb-1">Ralph Loop active on Coder, Architect & DevOps tasks</div>
              <div className="text-xs text-slate-500 leading-relaxed">
                After every task, the Self-Critic and QA agents automatically review the output in parallel.
                If either flags issues, a fix is applied and the review runs again — up to 3 times.
                This ensures every output meets quality standards before it's delivered to you.
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}
