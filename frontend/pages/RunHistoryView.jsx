import React, { useEffect, useState } from 'react'
import { Activity, RefreshCw } from 'lucide-react'
import api from '../utils/api'

function StatCard({ label, value }) {
  return (
    <div className="glass rounded-xl border border-white/10 p-4 text-center">
      <div className="text-2xl font-bold text-white">{value}</div>
      <div className="text-xs text-slate-500 mt-1">{label}</div>
    </div>
  )
}

export default function RunHistoryView() {
  const [runs, setRuns] = useState([])
  const [stats, setStats] = useState({})
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const [r, s] = await Promise.all([
        api.get('/api/runs'),
        api.get('/api/runs/stats'),
      ])
      setRuns(r)
      setStats(s)
    } catch (e) {
      console.error('Failed to load run history', e)
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <Activity size={24} className="text-accent-purple" />
            <h1 className="text-2xl font-bold text-white">Run History</h1>
          </div>
          <button onClick={load} className="btn-ghost flex items-center gap-2">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        <div className="grid grid-cols-4 gap-4 mb-8">
          <StatCard label="Total Runs" value={stats.total_runs || 0} />
          <StatCard label="Successful" value={stats.successful || 0} />
          <StatCard label="Failed" value={stats.failed || 0} />
          <StatCard label="Avg Duration" value={stats.avg_duration_ms ? `${(stats.avg_duration_ms / 1000).toFixed(1)}s` : '—'} />
        </div>

        <div className="glass rounded-2xl border border-white/10 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/5 text-slate-500 text-xs uppercase tracking-wider">
                <th className="text-left px-4 py-3 font-medium">Agent / Workflow</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">Duration</th>
                <th className="text-left px-4 py-3 font-medium">Files</th>
                <th className="text-left px-4 py-3 font-medium">When</th>
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-600">No runs yet.</td></tr>
              )}
              {runs.map(run => (
                <tr key={run.id} className="border-b border-white/5 last:border-0 hover:bg-white/5">
                  <td className="px-4 py-3 text-white">{run.agent_name || run.workflow_name || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                      run.status === 'completed' ? 'bg-emerald-500/15 text-emerald-400' :
                      run.status === 'failed' ? 'bg-red-500/15 text-red-400' :
                      run.status === 'cancelled' ? 'bg-slate-500/15 text-slate-400' :
                      'bg-amber-500/15 text-amber-400'
                    }`}>{run.status}</span>
                  </td>
                  <td className="px-4 py-3 text-slate-400 font-mono">{run.duration_ms ? `${(run.duration_ms / 1000).toFixed(1)}s` : '—'}</td>
                  <td className="px-4 py-3 text-slate-400">{run.files_generated ? JSON.parse(run.files_generated || '[]').length : 0}</td>
                  <td className="px-4 py-3 text-slate-500 font-mono text-xs">
                    {run.started_at ? new Date(run.started_at + 'Z').toLocaleString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
