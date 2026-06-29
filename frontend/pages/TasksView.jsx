import React, { useState } from 'react'
import { Zap, Play, CheckCircle, XCircle, Clock, FileText, ChevronDown, ChevronRight, RotateCcw, Shield } from 'lucide-react'
import clsx from 'clsx'
import useStore from '../store'
import api from '../utils/api'
import MessageRenderer from '../components/MessageRenderer'

const AGENT_TASKS = {
  orchestrator: { icon: '🎯', desc: 'Break into multi-agent plan' },
  architect:    { icon: '🏗️', desc: 'Design system & structure' },
  coder:        { icon: '💻', desc: 'Write & auto-save code' },
  researcher:   { icon: '🔍', desc: 'Deep research & analysis' },
  devops:       { icon: '⚙️', desc: 'Docker & deployment scripts' },
}

function RalphBadge({ ralph }) {
  if (!ralph) return null
  return (
    <div className={clsx('flex items-center gap-2 text-xs px-2 py-1 rounded-lg',
      ralph.passed ? 'bg-green-500/10 text-green-400 border border-green-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20')}>
      <RotateCcw size={11} />
      Ralph Loop: {ralph.passed ? 'Passed' : 'Partial'} · {ralph.iterations}/3 iterations
    </div>
  )
}

function TaskCard({ task }) {
  const [expanded, setExpanded] = useState(true)
  const [showRalph, setShowRalph] = useState(false)

  const statusIcon = {
    running: <Clock size={14} className="text-amber-400 agent-pulse" />,
    done:    <CheckCircle size={14} className="text-green-400" />,
    error:   <XCircle size={14} className="text-red-400" />,
  }[task.status]

  return (
    <div className="glass rounded-xl border border-white/10 overflow-hidden">
      <div className="flex items-center gap-3 p-4 cursor-pointer hover:bg-white/5" onClick={() => setExpanded(!expanded)}>
        {statusIcon}
        <div className="flex-1 min-w-0">
          <div className="text-sm text-white font-medium truncate">{task.task}</div>
          <div className="flex items-center gap-2 mt-0.5 flex-wrap">
            <span className="text-xs text-slate-500">{AGENT_TASKS[task.agentType]?.icon} {task.agentType}</span>
            <span className="text-xs text-slate-700">·</span>
            <span className="text-xs text-slate-600">{new Date(task.timestamp).toLocaleTimeString()}</span>
            {task.savedFiles?.length > 0 && (
              <span className="text-xs text-accent-green flex items-center gap-1">
                <FileText size={10} />{task.savedFiles.length} file{task.savedFiles.length !== 1 ? 's' : ''} saved
              </span>
            )}
            {task.ralph && <RalphBadge ralph={task.ralph} />}
          </div>
        </div>
        {expanded ? <ChevronDown size={15} className="text-slate-500" /> : <ChevronRight size={15} className="text-slate-500" />}
      </div>

      {expanded && (
        <div className="border-t border-white/10 p-4 bg-surface-1/40">
          {task.status === 'running' ? (
            <div className="flex items-center gap-2 text-sm text-slate-500 py-4">
              <div className="w-4 h-4 border-2 border-accent-purple/40 border-t-accent-purple rounded-full animate-spin" />
              Agent working… Ralph Loop will run after completion.
            </div>
          ) : (
            <MessageRenderer content={task.result || ''} />
          )}

          {task.savedFiles?.length > 0 && (
            <div className="mt-3 pt-3 border-t border-white/10">
              <div className="text-xs text-slate-500 mb-1">Files saved to workspace:</div>
              {task.savedFiles.map(f => (
                <div key={f} className="text-xs font-mono text-accent-green flex items-center gap-1">
                  <FileText size={10} />{f}
                </div>
              ))}
            </div>
          )}

          {task.ralph?.log?.length > 0 && (
            <div className="mt-3 pt-3 border-t border-white/10">
              <button onClick={() => setShowRalph(!showRalph)}
                className="flex items-center gap-2 text-xs text-slate-500 hover:text-white transition-colors">
                <RotateCcw size={11} />
                {showRalph ? 'Hide' : 'Show'} Ralph Loop details ({task.ralph.log.length} iteration{task.ralph.log.length !== 1 ? 's' : ''})
              </button>
              {showRalph && (
                <div className="mt-2 space-y-2">
                  {task.ralph.log.map((l, i) => (
                    <div key={i} className="text-xs bg-surface-2 rounded-lg p-3 border border-white/10">
                      <div className="font-medium text-slate-400 mb-1">Iteration {l.iteration}/3</div>
                      <div className="flex gap-2 mb-2">
                        <span className={l.critic_passed ? 'text-green-400' : 'text-red-400'}>
                          {l.critic_passed ? '✅' : '❌'} Self-critic
                        </span>
                        <span className={l.qa_passed ? 'text-green-400' : 'text-red-400'}>
                          {l.qa_passed ? '✅' : '❌'} QA
                        </span>
                      </div>
                      {!l.critic_passed && <pre className="text-slate-500 whitespace-pre-wrap text-xs">{l.critic}</pre>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function TasksView() {
  const { selectedModel, agents } = useStore()
  const [task, setTask] = useState('')
  const [agentType, setAgentType] = useState('coder')
  const [useRalph, setUseRalph] = useState(true)
  const [taskHistory, setTaskHistory] = useState([])
  const [running, setRunning] = useState(false)

  const runTask = async () => {
    if (!task.trim() || !selectedModel || running) return
    const newTask = {
      id: `task_${Date.now()}`, task: task.trim(), agentType,
      status: 'running', timestamp: new Date().toISOString(),
      result: null, savedFiles: [], ralph: null,
    }
    setTaskHistory(prev => [newTask, ...prev])
    setTask('')
    setRunning(true)
    try {
      const result = await api.runTask(newTask.task, selectedModel, agentType, useRalph)
      setTaskHistory(prev => prev.map(t => t.id === newTask.id
        ? { ...t, status: 'done', result: result.result, savedFiles: result.saved_files || [], ralph: result.ralph }
        : t
      ))
    } catch (e) {
      setTaskHistory(prev => prev.map(t => t.id === newTask.id
        ? { ...t, status: 'error', result: `Error: ${e.message}` }
        : t
      ))
    } finally {
      setRunning(false)
    }
  }

  const examples = [
    { task: 'Build a complete TODO app with FastAPI backend and React frontend. Write all files with filenames.', agent: 'coder' },
    { task: 'Design full architecture for a multi-tenant SaaS with auth, billing, dashboard, and API.', agent: 'architect' },
    { task: 'Research the best tech stack for a real-time collaborative app in 2024. Compare options thoroughly.', agent: 'researcher' },
    { task: 'Create a complete Docker + GitHub Actions CI/CD pipeline for a Python FastAPI app.', agent: 'devops' },
  ]

  const ralphAgents = ['coder', 'architect', 'devops']

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto w-full px-6 py-8">
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-1">
            <Zap size={20} className="text-accent-amber" />
            <h1 className="text-xl font-bold text-white">Autonomous Tasks</h1>
          </div>
          <p className="text-slate-500 text-sm">Give a complex task. The agent works autonomously, writes code, and saves files.</p>
        </div>

        <div className="glass rounded-2xl border border-white/10 p-5 mb-5">
          {/* Agent selector */}
          <div className="mb-4">
            <label className="text-xs text-slate-500 uppercase tracking-wider mb-2 block">Choose Agent</label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {Object.entries(AGENT_TASKS).map(([id, { icon, desc }]) => (
                <button key={id} onClick={() => setAgentType(id)}
                  className={clsx('flex items-start gap-2 px-3 py-2.5 rounded-lg text-xs border transition-all text-left',
                    agentType === id ? 'bg-accent-purple/20 border-accent-purple/50 text-white' : 'border-white/10 text-slate-400 hover:border-white/20 hover:text-white')}>
                  <span className="text-base">{icon}</span>
                  <div><div className="font-medium capitalize">{id}</div><div className="text-slate-600 text-xs mt-0.5">{desc}</div></div>
                </button>
              ))}
            </div>
          </div>

          {/* Ralph loop toggle */}
          {ralphAgents.includes(agentType) && (
            <div className="mb-4 flex items-center justify-between p-3 bg-surface-2 rounded-xl border border-white/10">
              <div className="flex items-center gap-2">
                <RotateCcw size={14} className="text-accent-purple" />
                <div>
                  <div className="text-xs font-medium text-white">Ralph Loop</div>
                  <div className="text-xs text-slate-600">Auto self-critic + QA review after task</div>
                </div>
              </div>
              <button onClick={() => setUseRalph(!useRalph)}
                className={clsx('relative w-10 h-5 rounded-full transition-colors cursor-pointer',
                  useRalph ? 'bg-accent-purple' : 'bg-white/15')}>
                <span className={clsx('absolute left-0.5 top-0.5 w-4 h-4 rounded-full bg-white transition-transform',
                  useRalph ? 'translate-x-5' : 'translate-x-0')} />
              </button>
            </div>
          )}

          {/* Task input */}
          <div className="mb-4">
            <label className="text-xs text-slate-500 uppercase tracking-wider mb-2 block">Task</label>
            <textarea value={task} onChange={e => setTask(e.target.value)}
              placeholder="Describe your task in detail…"
              rows={4} className="input-base w-full resize-none leading-relaxed" />
          </div>

          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-600 font-mono">{selectedModel || 'no model'}</span>
            <button onClick={runTask} disabled={!task.trim() || !selectedModel || running}
              className="btn-primary flex items-center gap-2 disabled:opacity-30 disabled:cursor-not-allowed">
              <Play size={14} />
              {running ? 'Running…' : 'Run Task'}
            </button>
          </div>
        </div>

        {!taskHistory.length && (
          <div className="space-y-2 mb-5">
            <div className="text-xs text-slate-600 uppercase tracking-wider mb-2">Example tasks</div>
            {examples.map((ex, i) => (
              <button key={i} onClick={() => { setTask(ex.task); setAgentType(ex.agent) }}
                className="w-full text-left glass glass-hover rounded-xl p-3 border border-white/10 transition-all">
                <div className="flex items-start gap-2">
                  <span>{AGENT_TASKS[ex.agent]?.icon}</span>
                  <div>
                    <div className="text-xs text-slate-500 mb-0.5 capitalize">{ex.agent}</div>
                    <div className="text-sm text-slate-300">{ex.task}</div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}

        {taskHistory.length > 0 && (
          <div className="space-y-3">
            <div className="text-xs text-slate-600 uppercase tracking-wider">Task history</div>
            {taskHistory.map(t => <TaskCard key={t.id} task={t} />)}
          </div>
        )}
      </div>
    </div>
  )
}
