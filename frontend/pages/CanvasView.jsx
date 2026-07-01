import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Download, Plus, Play, Trash2, Save, Upload, Workflow } from 'lucide-react'
import clsx from 'clsx'
import useStore from '../store'
import api from '../utils/api'
import MessageRenderer from '../components/MessageRenderer'

const AGENTS = [
  { id: 'coder',        icon: '💻', label: 'Coder',        color: '#10b981' },
  { id: 'researcher',   icon: '🔍', label: 'Researcher',   color: '#f59e0b' },
  { id: 'architect',    icon: '🏗️', label: 'Architect',    color: '#8b5cf6' },
  { id: 'devops',       icon: '⚙️', label: 'DevOps',       color: '#06b6d4' },
  { id: 'orchestrator', icon: '🎯', label: 'Orchestrator', color: '#ef4444' },
  { id: 'general',      icon: '🤖', label: 'General',      color: '#6366f1' },
]

/**
 * Phase 1 Fix: AgentNode now supports real drag-to-reposition.
 * Uses pointer events (works on desktop and touch).
 * The canvas UI copy said "drag agents" — now it actually does.
 */
function AgentNode({ node, selected, onSelect, onDelete, onDragEnd }) {
  const agent   = AGENTS.find(a => a.id === node.data.agent) || AGENTS[0]
  const dragging = useRef(false)
  const origin   = useRef({ x: 0, y: 0, nodeX: 0, nodeY: 0 })

  const handlePointerDown = (e) => {
    // Left button only; ignore right-click / context menu
    if (e.button !== 0) return
    e.currentTarget.setPointerCapture(e.pointerId)
    dragging.current = true
    origin.current = {
      x:     e.clientX,
      y:     e.clientY,
      nodeX: node.position.x,
      nodeY: node.position.y,
    }
    onSelect(node.id)
  }

  const handlePointerMove = (e) => {
    if (!dragging.current) return
    const dx   = e.clientX - origin.current.x
    const dy   = e.clientY - origin.current.y
    const newX = Math.max(0, origin.current.nodeX + dx)
    const newY = Math.max(0, origin.current.nodeY + dy)
    // Live update via callback so canvas redraws edges
    onDragEnd(node.id, newX, newY, true /* live */)
  }

  const handlePointerUp = (e) => {
    if (!dragging.current) return
    dragging.current = false
    e.currentTarget.releasePointerCapture(e.pointerId)
    const dx   = e.clientX - origin.current.x
    const dy   = e.clientY - origin.current.y
    const newX = Math.max(0, origin.current.nodeX + dx)
    const newY = Math.max(0, origin.current.nodeY + dy)
    onDragEnd(node.id, newX, newY, false /* final */)
  }

  return (
    <div
      className={clsx(
        'absolute flex flex-col items-center gap-1 select-none group',
        selected && 'z-10',
        'cursor-grab active:cursor-grabbing'
      )}
      style={{ left: node.position.x, top: node.position.y, touchAction: 'none' }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
    >
      <div
        className={clsx(
          'w-16 h-16 rounded-2xl flex items-center justify-center text-2xl border-2 transition-shadow shadow-lg',
          selected ? 'scale-110' : ''
        )}
        style={{
          background:   agent.color + '22',
          borderColor:  selected ? agent.color : agent.color + '44',
        }}
      >
        {agent.icon}
      </div>
      <div className="text-xs text-slate-300 font-medium whitespace-nowrap pointer-events-none">
        {node.data.label || agent.label}
      </div>
      <button
        onPointerDown={e => e.stopPropagation()}
        onClick={e => { e.stopPropagation(); onDelete(node.id) }}
        className="opacity-0 group-hover:opacity-100 absolute -top-2 -right-2 w-5 h-5 rounded-full bg-red-500 text-white flex items-center justify-center text-xs transition-all"
      >
        ×
      </button>
    </div>
  )
}

export default function CanvasView() {
  const { selectedModel } = useStore()
  const [nodes,     setNodes]     = useState([])
  const [selectedNode, setSelectedNode] = useState(null)
  const [workflows, setWorkflows] = useState([])
  const [wfName,    setWfName]    = useState('')
  const [task,      setTask]      = useState('')
  const [running,   setRunning]   = useState(false)
  const [results,   setResults]   = useState(null)
  const [activeWf,  setActiveWf]  = useState(null)
  const nextX = useRef(60)

  useEffect(() => { loadWorkflows() }, [loadWorkflows])

  const addNode = (agentId) => {
    const agent = AGENTS.find(a => a.id === agentId)
    const node  = {
      id:       `node_${Date.now()}`,
      data:     { agent: agentId, label: agent.label },
      position: { x: nextX.current, y: 80 },
    }
    nextX.current += 130
    setNodes(prev => [...prev, node])
  }

  const deleteNode = (id) => {
    setNodes(prev => prev.filter(n => n.id !== id))
    if (selectedNode === id) setSelectedNode(null)
  }

  // [P1 Fix] Real drag: update node position live or on release
  const handleDragEnd = useCallback((id, x, y, live) => {
    setNodes(prev => prev.map(n =>
      n.id === id ? { ...n, position: { x, y } } : n
    ))
  }, [])

  const saveWorkflow = async () => {
    if (!wfName.trim() || !nodes.length) return
    const edges = nodes.slice(0, -1).map((n, i) => ({
      id: `e${i}`, source: n.id, target: nodes[i + 1].id,
    }))
    const saved = await api.post('/api/canvas/workflows', {
      name: wfName, description: `${nodes.length} agent workflow`, nodes, edges,
    })
    setWorkflows(prev => [...prev, saved])
    setWfName('')
  }

  const loadWorkflow = (wf) => {
    setNodes(wf.nodes || [])
    setActiveWf(wf.id)
    nextX.current = (wf.nodes?.length || 0) * 130 + 60
  }

  const deleteWorkflow = async (id) => {
    await api.delete(`/api/canvas/workflows/${id}`)
    setWorkflows(prev => prev.filter(w => w.id !== id))
    if (activeWf === id) { setNodes([]); setActiveWf(null) }
  }

  const exportWorkflow = async (wf) => {
    try {
      const data = await api.exportWorkflow(wf.id)
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `workflow-${wf.id}.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch {}
  }

  const importWorkflow = () => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.json'
    input.onchange = async (e) => {
      const file = e.target.files[0]
      if (!file) return
      try {
        const text = await file.text()
        const data = JSON.parse(text)
        await api.importWorkflow(data)
        loadWorkflows()
      } catch {}
    }
    input.click()
  }

  const loadWorkflows = useCallback(async () => {
    try {
      const d = await api.get('/api/canvas/workflows')
      setWorkflows(d.workflows || [])
    } catch {}
  }, [])

  const runWorkflow = async () => {
    if (!nodes.length || !task.trim() || !selectedModel || running) return
    setRunning(true); setResults(null)
    try {
      if (activeWf) {
        const r = await api.post(`/api/canvas/run/${activeWf}`, { model: selectedModel, task })
        setResults(r)
      } else {
        const edges = nodes.slice(0, -1).map((n, i) => ({ id: `e${i}`, source: n.id, target: nodes[i + 1].id }))
        const tmp   = await api.post('/api/canvas/workflows', { name: '_temp', description: '', nodes, edges })
        const r     = await api.post(`/api/canvas/run/${tmp.id}`, { model: selectedModel, task })
        await api.delete(`/api/canvas/workflows/${tmp.id}`)
        setResults(r)
      }
    } catch (e) { console.error(e) }
    finally { setRunning(false) }
  }

  // Sort nodes by x position for edge drawing
  const sortedNodes = [...nodes].sort((a, b) => a.position.x - b.position.x)

  return (
    <div className="flex h-full">
      {/* Left panel */}
      <div className="w-64 bg-surface-1 border-r border-white/5 flex flex-col">
        <div className="p-4 border-b border-white/5">
          <div className="flex items-center gap-2 mb-3">
            <Workflow size={16} className="text-accent-purple" />
            <span className="text-sm font-semibold text-white">Canvas</span>
          </div>
          <p className="text-xs text-slate-500 mb-3">
            Click to add agents. <span className="text-slate-400">Drag to reposition.</span>
          </p>
          <div className="text-xs text-slate-600 uppercase tracking-wider mb-2">Add Agent</div>
          <div className="grid grid-cols-2 gap-1.5">
            {AGENTS.map(a => (
              <button
                key={a.id}
                onClick={() => addNode(a.id)}
                className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg border border-white/10 hover:border-white/20 text-xs text-slate-400 hover:text-white transition-all"
              >
                <span>{a.icon}</span>{a.label}
              </button>
            ))}
          </div>
        </div>

        <div className="p-4 border-b border-white/5">
          <div className="text-xs text-slate-600 uppercase tracking-wider mb-2">Save Workflow</div>
          <input
            className="input-base w-full mb-2 text-xs"
            placeholder="Workflow name…"
            value={wfName}
            onChange={e => setWfName(e.target.value)}
          />
          <button
            onClick={saveWorkflow}
            disabled={!wfName.trim() || !nodes.length}
            className="btn-primary w-full text-xs py-1.5 flex items-center justify-center gap-1 disabled:opacity-30"
          >
            <Save size={12} /> Save Workflow
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs text-slate-600 uppercase tracking-wider">Saved Workflows</div>
            <button onClick={importWorkflow} className="text-xs text-accent-purple hover:text-accent-purple/80 flex items-center gap-1">
              <Upload size={12} /> Import
            </button>
          </div>
          {!workflows.length && (
            <div className="text-xs text-slate-700 py-4 text-center">No workflows saved yet</div>
          )}
          {workflows.map(wf => (
            <div
              key={wf.id}
              className={clsx(
                'p-2.5 rounded-lg border mb-1.5 cursor-pointer transition-all group',
                activeWf === wf.id
                  ? 'border-accent-purple/50 bg-accent-purple/10'
                  : 'border-white/10 hover:border-white/20'
              )}
            >
              <div className="flex items-start justify-between">
                <div onClick={() => loadWorkflow(wf)} className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-white truncate">{wf.name}</div>
                  <div className="text-xs text-slate-600">{wf.nodes?.length || 0} agents</div>
                </div>
                <div className="flex items-center opacity-0 group-hover:opacity-100 transition-all ml-1">
                  <button
                    onClick={() => exportWorkflow(wf)}
                    className="text-slate-600 hover:text-accent-purple mr-1"
                    title="Export workflow"
                  >
                    <Download size={11} />
                  </button>
                  <button
                    onClick={() => deleteWorkflow(wf.id)}
                    className="text-slate-600 hover:text-red-400"
                  >
                    <Trash2 size={11} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Canvas area */}
      <div className="flex-1 flex flex-col">
        <div
          className="flex-1 relative bg-surface-0 overflow-auto"
          style={{
            backgroundImage: 'radial-gradient(circle, #ffffff08 1px, transparent 1px)',
            backgroundSize:  '24px 24px',
          }}
        >
          {!nodes.length && (
            <div className="absolute inset-0 flex items-center justify-center text-slate-700 text-sm pointer-events-none">
              <div className="text-center">
                <Workflow size={40} className="mx-auto mb-3 opacity-30" />
                <div>Click agents on the left to add them</div>
                <div className="text-xs mt-1">Drag nodes to reposition · Agents run left-to-right</div>
              </div>
            </div>
          )}

          {/* SVG edges */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ minWidth: '100%', minHeight: '100%' }}>
            <defs>
              <marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                <path d="M2 1L8 5L2 9" fill="none" stroke="#8b5cf6" strokeWidth="1.5" />
              </marker>
            </defs>
            {sortedNodes.slice(0, -1).map((n, i) => {
              const next = sortedNodes[i + 1]
              return (
                <line
                  key={i}
                  x1={n.position.x + 32}
                  y1={n.position.y + 32}
                  x2={next.position.x + 32}
                  y2={next.position.y + 32}
                  stroke="#8b5cf640"
                  strokeWidth="2"
                  strokeDasharray="6 3"
                  markerEnd="url(#arr)"
                />
              )
            })}
          </svg>

          {/* Nodes */}
          {nodes.map(n => (
            <AgentNode
              key={n.id}
              node={n}
              selected={selectedNode === n.id}
              onSelect={setSelectedNode}
              onDelete={deleteNode}
              onDragEnd={handleDragEnd}
            />
          ))}
        </div>

        {/* Run bar */}
        <div className="border-t border-white/5 bg-surface-1 px-4 py-3 flex items-center gap-3">
          <input
            className="input-base flex-1 text-sm"
            placeholder="Describe the task to run through this workflow…"
            value={task}
            onChange={e => setTask(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && runWorkflow()}
          />
          <button
            onClick={runWorkflow}
            disabled={!nodes.length || !task.trim() || !selectedModel || running}
            className="btn-primary flex items-center gap-2 disabled:opacity-30 whitespace-nowrap"
          >
            <Play size={14} />{running ? 'Running…' : 'Run Workflow'}
          </button>
        </div>

        {results && (
          <div className="border-t border-white/5 bg-surface-1 max-h-64 overflow-y-auto p-4">
            <div className="text-xs text-slate-500 uppercase tracking-wider mb-3">
              Workflow Results
              {results.results?.some(r => r.handoff_to) && (
                <span className="ml-2 text-accent-purple">(includes agent handoffs)</span>
              )}
            </div>
            {results.results?.map((r, i) => (
              <div key={i} className="mb-3 pb-3 border-b border-white/5 last:border-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium text-accent-purple">{r.node}</span>
                  <span className="text-xs text-slate-600">({r.agent})</span>
                  {r.handoff_to && (
                    <span className="text-xs text-accent-amber">→ handoff: {r.handoff_to}</span>
                  )}
                </div>
                <div className="text-xs text-slate-400 line-clamp-3">{r.output?.slice(0, 300)}…</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
