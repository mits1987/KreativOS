import React, { useState, useRef, useEffect } from 'react'
import {
  Brain, Play, StopCircle, ChevronDown, ChevronRight,
  Wrench, CheckCircle, XCircle, AlertCircle, Sparkles, ClipboardList,
} from 'lucide-react'
import clsx from 'clsx'
import useStore from '../store'
import api from '../utils/api'
import MessageRenderer from '../components/MessageRenderer'

const AGENT_META = {
  researcher:  { icon: '🔍', color: '#f59e0b', label: 'Researcher'  },
  architect:   { icon: '🏗️', color: '#8b5cf6', label: 'Architect'   },
  coder:       { icon: '💻', color: '#10b981', label: 'Coder'       },
  devops:      { icon: '⚙️', color: '#06b6d4', label: 'DevOps'      },
  general:     { icon: '🤖', color: '#6366f1', label: 'General'     },
  orchestrator:{ icon: '🧠', color: '#ec4899', label: 'Orchestrator'},
}

function ToolCallRow({ event }) {
  const [open, setOpen] = useState(false)
  const isResult = event.type === 'tool_result'
  return (
    <div className={clsx('text-xs font-mono rounded-lg px-3 py-1.5 flex items-start gap-2',
      isResult ? 'bg-surface-0/60 text-slate-400' : 'bg-surface-3/60 text-slate-300')}>
      <Wrench size={10} className="mt-0.5 flex-shrink-0 text-slate-500"/>
      <div className="flex-1 min-w-0">
        <span className="text-slate-400">{isResult ? '← ' : '→ '}</span>
        <span className="text-accent-green">{event.tool}</span>
        {!isResult && event.args && Object.keys(event.args).length > 0 && (
          <>
            <span className="text-slate-600">(</span>
            {Object.entries(event.args).map(([k, v], i) => (
              <span key={k}>
                {i > 0 && <span className="text-slate-600">, </span>}
                <span className="text-slate-500">{k}=</span>
                <span className="text-slate-300 truncate max-w-xs inline-block align-bottom">
                  {typeof v === 'string' ? `"${v.slice(0, 40)}${v.length > 40 ? '…"' : '"'}` : JSON.stringify(v)}
                </span>
              </span>
            ))}
            <span className="text-slate-600">)</span>
          </>
        )}
        {isResult && (
          <button onClick={() => setOpen(!open)} className="ml-1 text-slate-600 hover:text-white">
            {open ? <ChevronDown size={9} className="inline"/> : <ChevronRight size={9} className="inline"/>}
          </button>
        )}
        {isResult && open && (
          <div className="mt-1 text-slate-500 whitespace-pre-wrap break-all">{event.result}</div>
        )}
      </div>
    </div>
  )
}

function AgentCard({ agentId, events, round, isActive }) {
  const [open, setOpen] = useState(true)
  const meta   = AGENT_META[agentId] || AGENT_META.general
  const output = events.find(e => e.type === 'agent_done')?.output || ''
  const tools  = events.filter(e => e.type === 'tool_call' || e.type === 'tool_result')
  const done   = events.some(e => e.type === 'agent_done')

  return (
    <div className={clsx('rounded-xl border overflow-hidden transition-all',
      done ? 'border-white/10' : isActive ? 'border-accent-purple/30' : 'border-white/5')}>
      <div onClick={() => setOpen(!open)}
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-white/5 transition-all">
        <div className="w-7 h-7 rounded-lg flex items-center justify-center text-sm"
          style={{ background: meta.color + '20' }}>
          {meta.icon}
        </div>
        <div className="flex-1">
          <div className="text-sm font-medium text-white flex items-center gap-2">
            {meta.label}
            {round > 1 && (
              <span className="text-xs px-1.5 py-0.5 rounded-full bg-amber-500/15 text-amber-400">
                Round {round}
              </span>
            )}
          </div>
          {tools.length > 0 && (
            <div className="text-xs text-slate-600">{tools.filter(e => e.type === 'tool_call').length} tool calls</div>
          )}
        </div>
        {isActive && !done && (
          <div className="w-1.5 h-1.5 rounded-full bg-accent-purple animate-pulse"/>
        )}
        {done && <CheckCircle size={14} className="text-accent-green flex-shrink-0"/>}
        {open ? <ChevronDown size={13} className="text-slate-600"/> : <ChevronRight size={13} className="text-slate-600"/>}
      </div>

      {open && (
        <div className="border-t border-white/5 p-4 space-y-2 bg-surface-1/30">
          {tools.map((e, i) => <ToolCallRow key={i} event={e}/>)}
          {output && (
            <div className="mt-3 pt-3 border-t border-white/5">
              <MessageRenderer content={output}/>
            </div>
          )}
          {isActive && !done && (
            <div className="flex items-center gap-2 text-xs text-slate-500 animate-pulse">
              <div className="w-1 h-1 rounded-full bg-accent-purple"/>
              Working…
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function AuditCard({ event }) {
  return (
    <div className={clsx('rounded-xl border p-4 flex items-start gap-3',
      event.passed ? 'border-accent-green/20 bg-accent-green/5' : 'border-amber-500/20 bg-amber-500/5')}>
      <div className="mt-0.5">
        {event.passed
          ? <CheckCircle size={16} className="text-accent-green"/>
          : <AlertCircle size={16} className="text-amber-400"/>}
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-medium text-white">
            Auditor — Round {event.round}
          </span>
          <span className={clsx('text-xs px-2 py-0.5 rounded-full font-medium',
            event.score >= 8 ? 'bg-accent-green/15 text-accent-green' :
            event.score >= 6 ? 'bg-amber-500/15 text-amber-400' : 'bg-red-500/15 text-red-400')}>
            {event.score}/10
          </span>
          {event.passed
            ? <span className="text-xs text-accent-green">✓ Passed</span>
            : <span className="text-xs text-amber-400">Needs revision</span>}
        </div>
        {event.issues?.length > 0 && (
          <ul className="text-xs text-slate-400 list-disc list-inside space-y-0.5">
            {event.issues.map((issue, i) => <li key={i}>{issue}</li>)}
          </ul>
        )}
        {event.feedback && !event.passed && (
          <p className="text-xs text-slate-500 mt-1">{event.feedback}</p>
        )}
      </div>
    </div>
  )
}

export default function OrchestratorView() {
  const { selectedModel } = useStore()
  const [task,       setTask]       = useState('')
  const [project,    setProject]    = useState('')
  const [running,    setRunning]    = useState(false)
  const [events,     setEvents]     = useState([])
  const [finalOut,   setFinalOut]   = useState('')
  const [planSteps,  setPlanSteps]  = useState([])
  const [planSummary, setPlanSummary] = useState('')
  const abortRef = useRef(false)
  const bottomRef = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [events, finalOut])
  useEffect(() => () => { abortRef.current = true }, [])

  const run = async () => {
    if (!task.trim() || !selectedModel || running) return
    setRunning(true)
    setEvents([])
    setFinalOut('')
    setPlanSteps([])
    setPlanSummary('')
    abortRef.current = false

    try {
      for await (const event of api.streamOrchestrate(task, selectedModel, project)) {
        if (abortRef.current) break
        if (event.type === 'plan') {
          setPlanSteps(event.steps || [])
          setPlanSummary(event.summary || '')
        } else if (event.type === 'done') {
          setFinalOut(event.output || '')
        }
        setEvents(prev => [...prev, event])
      }
    } catch (e) {
      setEvents(prev => [...prev, { type: 'error', message: e.message }])
    } finally {
      setRunning(false)
    }
  }

  // Group agent events by (agent, round) for rendering
  const agentGroups = []
  let currentGroup = null
  for (const e of events) {
    if (e.type === 'agent_start') {
      currentGroup = { agentId: e.agent, round: e.round, events: [], isActive: true }
      agentGroups.push(currentGroup)
    } else if (currentGroup && (e.type === 'tool_call' || e.type === 'tool_result' || e.type === 'agent_done')) {
      currentGroup.events.push(e)
      if (e.type === 'agent_done') {
        currentGroup.isActive = false
        currentGroup = null
      }
    }
  }

  const auditEvents = events.filter(e => e.type === 'audit_result')
  const hasError    = events.some(e => e.type === 'error')
  const isPlanReady = planSteps.length > 0

  return (
    <div className="flex flex-col h-full">
      {/* Feed */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto space-y-4">

          {/* Empty state */}
          {!running && !events.length && (
            <div className="text-center mt-16">
              <div className="w-16 h-16 rounded-2xl bg-accent-purple/15 flex items-center justify-center mx-auto mb-4">
                <Brain size={28} className="text-accent-purple"/>
              </div>
              <h2 className="text-xl font-bold text-white mb-2">Orchestrator</h2>
              <p className="text-slate-500 text-sm max-w-sm mx-auto">
                Describe your task. The Orchestrator plans the work, delegates to specialist agents,
                and loops until the Auditor approves.
              </p>
              <div className="mt-6 grid grid-cols-1 gap-2 max-w-md mx-auto text-left">
                {[
                  'Build a FastAPI REST API with SQLite for a task manager',
                  'Research microservices patterns and design an e-commerce architecture',
                  'Create a Python CLI tool to batch-resize images with Pillow',
                  'Build a React dashboard that fetches live crypto prices',
                ].map((ex, i) => (
                  <button key={i} onClick={() => setTask(ex)}
                    className="glass glass-hover rounded-xl p-3 border border-white/10 text-xs text-slate-400 hover:text-white text-left">
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Planning indicator */}
          {events.some(e => e.type === 'planning') && !isPlanReady && (
            <div className="flex items-center gap-3 glass rounded-xl border border-white/10 p-4">
              <Brain size={16} className="text-accent-purple animate-pulse"/>
              <span className="text-sm text-slate-400">Orchestrator is planning…</span>
            </div>
          )}

          {/* Plan card */}
          {isPlanReady && (
            <div className="glass rounded-xl border border-accent-purple/20 p-4">
              <div className="flex items-center gap-2 mb-3">
                <ClipboardList size={15} className="text-accent-purple"/>
                <span className="text-sm font-semibold text-white">Plan</span>
              </div>
              {planSummary && <p className="text-xs text-slate-400 mb-3">{planSummary}</p>}
              <div className="flex items-center gap-1 flex-wrap">
                {planSteps.map((step, i) => {
                  const meta = AGENT_META[step.agent] || AGENT_META.general
                  return (
                    <React.Fragment key={i}>
                      <div className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium"
                        style={{ background: meta.color + '15', color: meta.color }}>
                        <span>{meta.icon}</span>
                        <span>{meta.label}</span>
                      </div>
                      {i < planSteps.length - 1 && (
                        <span className="text-slate-600 text-xs">→</span>
                      )}
                    </React.Fragment>
                  )
                })}
              </div>
            </div>
          )}

          {/* Agent cards */}
          {agentGroups.map((group, i) => (
            <AgentCard key={i} {...group}/>
          ))}

          {/* Audit cards */}
          {auditEvents.map((e, i) => <AuditCard key={i} event={e}/>)}

          {/* Error */}
          {hasError && (
            <div className="flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/5 p-4">
              <XCircle size={15} className="text-red-400"/>
              <span className="text-sm text-red-400">
                {events.find(e => e.type === 'error')?.message || 'An error occurred'}
              </span>
            </div>
          )}

          {/* Final output */}
          {finalOut && (
            <div className="glass rounded-xl border border-accent-green/20 p-5">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles size={15} className="text-accent-green"/>
                <span className="text-sm font-semibold text-white">Final Report</span>
                {events.find(e => e.type === 'done')?.score && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-accent-green/15 text-accent-green ml-auto">
                    Score: {events.find(e => e.type === 'done').score}/10
                  </span>
                )}
              </div>
              <MessageRenderer content={finalOut}/>
            </div>
          )}

          <div ref={bottomRef}/>
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-white/5 px-4 py-4 flex-shrink-0">
        <div className="max-w-3xl mx-auto space-y-2">
          <div className="flex gap-2">
            <input
              className="input-base flex-1 text-xs"
              placeholder="Project name (optional)"
              value={project}
              onChange={e => setProject(e.target.value)}
            />
          </div>
          <div className="flex gap-3">
            <textarea
              value={task}
              onChange={e => setTask(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !running) { e.preventDefault(); run() } }}
              rows={2}
              placeholder="Describe your task… agents will handle the rest"
              className="input-base flex-1 resize-none text-sm"
            />
            <button
              onClick={running ? () => { abortRef.current = true } : run}
              disabled={!task.trim() || !selectedModel}
              className={clsx('flex-shrink-0 flex items-center gap-2 px-5 rounded-xl font-medium text-sm transition-all disabled:opacity-30',
                running
                  ? 'bg-red-500/15 text-red-400 border border-red-500/30 hover:bg-red-500/25'
                  : 'btn-primary'
              )}>
              {running
                ? <><StopCircle size={15}/>Stop</>
                : <><Play size={15}/>Run</>}
            </button>
          </div>
          {!selectedModel && (
            <p className="text-xs text-amber-500">Select a model in Settings first</p>
          )}
        </div>
      </div>
    </div>
  )
}
