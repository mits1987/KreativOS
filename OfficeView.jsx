import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Plus, Play, Trash2, Save, ArrowRight, Workflow } from 'lucide-react'
import clsx from 'clsx'
import useStore from '../store'
import api from '../utils/api'
import MessageRenderer from '../components/MessageRenderer'

const AGENTS = [
  { id:'coder',        icon:'💻', label:'Coder',        color:'#10b981' },
  { id:'researcher',   icon:'🔍', label:'Researcher',   color:'#f59e0b' },
  { id:'architect',    icon:'🏗️', label:'Architect',    color:'#8b5cf6' },
  { id:'devops',       icon:'⚙️', label:'DevOps',       color:'#06b6d4' },
  { id:'orchestrator', icon:'🎯', label:'Orchestrator', color:'#ef4444' },
  { id:'general',      icon:'🤖', label:'General',      color:'#6366f1' },
]

function AgentNode({ node, selected, onSelect, onDelete }) {
  const agent = AGENTS.find(a => a.id === node.data.agent) || AGENTS[0]
  return (
    <div onClick={() => onSelect(node.id)}
      className={clsx('absolute flex flex-col items-center gap-1 cursor-pointer select-none group', selected && 'z-10')}
      style={{ left: node.position.x, top: node.position.y }}>
      <div className={clsx('w-16 h-16 rounded-2xl flex items-center justify-center text-2xl border-2 transition-all shadow-lg',
        selected ? 'scale-110' : 'hover:scale-105')}
        style={{ background: agent.color+'22', borderColor: selected ? agent.color : agent.color+'44' }}>
        {agent.icon}
      </div>
      <div className="text-xs text-slate-300 font-medium whitespace-nowrap">{node.data.label||agent.label}</div>
      <button onClick={e=>{e.stopPropagation();onDelete(node.id)}}
        className="opacity-0 group-hover:opacity-100 absolute -top-2 -right-2 w-5 h-5 rounded-full bg-red-500 text-white flex items-center justify-center text-xs transition-all">
        ×
      </button>
    </div>
  )
}

export default function CanvasView() {
  const { selectedModel } = useStore()
  const [nodes, setNodes] = useState([])
  const [selectedNode, setSelectedNode] = useState(null)
  const [workflows, setWorkflows] = useState([])
  const [wfName, setWfName] = useState('')
  const [task, setTask] = useState('')
  const [running, setRunning] = useState(false)
  const [results, setResults] = useState(null)
  const [activeWf, setActiveWf] = useState(null)
  const canvasRef = useRef(null)
  const nextX = useRef(60)

  useEffect(() => {
    api.get('/api/canvas/workflows').then(d => setWorkflows(d.workflows||[]))
  }, [])

  const addNode = (agentId) => {
    const agent = AGENTS.find(a=>a.id===agentId)
    const node = { id:`node_${Date.now()}`, data:{agent:agentId,label:agent.label},
                   position:{x:nextX.current,y:80} }
    nextX.current += 120
    setNodes(prev=>[...prev,node])
  }

  const deleteNode = (id) => {
    setNodes(prev=>prev.filter(n=>n.id!==id))
    if(selectedNode===id) setSelectedNode(null)
  }

  const saveWorkflow = async () => {
    if(!wfName.trim()||!nodes.length) return
    const edges = nodes.slice(0,-1).map((n,i)=>({id:`e${i}`,source:n.id,target:nodes[i+1].id}))
    const saved = await api.post('/api/canvas/workflows',{name:wfName,description:`${nodes.length} agent workflow`,nodes,edges})
    setWorkflows(prev=>[...prev,saved])
    setWfName('')
  }

  const loadWorkflow = (wf) => {
    setNodes(wf.nodes||[])
    setActiveWf(wf.id)
    nextX.current = (wf.nodes?.length||0)*120+60
  }

  const deleteWorkflow = async (id) => {
    await api.delete(`/api/canvas/workflows/${id}`)
    setWorkflows(prev=>prev.filter(w=>w.id!==id))
    if(activeWf===id) { setNodes([]); setActiveWf(null) }
  }

  const runWorkflow = async () => {
    if(!nodes.length||!task.trim()||!selectedModel||running) return
    setRunning(true); setResults(null)
    try {
      if(activeWf) {
        const r = await api.post(`/api/canvas/run/${activeWf}`,{model:selectedModel,task})
        setResults(r)
      } else {
        // Run unsaved workflow inline
        const edges = nodes.slice(0,-1).map((n,i)=>({id:`e${i}`,source:n.id,target:nodes[i+1].id}))
        const tmp = await api.post('/api/canvas/workflows',{name:'_temp',description:'',nodes,edges})
        const r = await api.post(`/api/canvas/run/${tmp.id}`,{model:selectedModel,task})
        await api.delete(`/api/canvas/workflows/${tmp.id}`)
        setResults(r)
      }
    } catch(e) { console.error(e) }
    finally { setRunning(false) }
  }

  return (
    <div className="flex h-full">
      {/* Left panel */}
      <div className="w-64 bg-surface-1 border-r border-white/5 flex flex-col">
        <div className="p-4 border-b border-white/5">
          <div className="flex items-center gap-2 mb-3">
            <Workflow size={16} className="text-accent-purple"/>
            <span className="text-sm font-semibold text-white">Canvas</span>
          </div>
          <div className="text-xs text-slate-500 mb-3">Drag agents onto the canvas to build a custom workflow</div>
          <div className="text-xs text-slate-600 uppercase tracking-wider mb-2">Add Agent</div>
          <div className="grid grid-cols-2 gap-1.5">
            {AGENTS.map(a => (
              <button key={a.id} onClick={()=>addNode(a.id)}
                className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg border border-white/10 hover:border-white/20 text-xs text-slate-400 hover:text-white transition-all">
                <span>{a.icon}</span>{a.label}
              </button>
            ))}
          </div>
        </div>

        <div className="p-4 border-b border-white/5">
          <div className="text-xs text-slate-600 uppercase tracking-wider mb-2">Save Workflow</div>
          <input className="input-base w-full mb-2 text-xs" placeholder="Workflow name…"
            value={wfName} onChange={e=>setWfName(e.target.value)}/>
          <button onClick={saveWorkflow} disabled={!wfName.trim()||!nodes.length}
            className="btn-primary w-full text-xs py-1.5 flex items-center justify-center gap-1 disabled:opacity-30">
            <Save size={12}/>Save Workflow
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          <div className="text-xs text-slate-600 uppercase tracking-wider mb-2">Saved Workflows</div>
          {!workflows.length && <div className="text-xs text-slate-700 py-4 text-center">No workflows saved yet</div>}
          {workflows.map(wf => (
            <div key={wf.id} className={clsx('p-2.5 rounded-lg border mb-1.5 cursor-pointer transition-all group',
              activeWf===wf.id ? 'border-accent-purple/50 bg-accent-purple/10' : 'border-white/10 hover:border-white/20')}>
              <div className="flex items-start justify-between">
                <div onClick={()=>loadWorkflow(wf)} className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-white truncate">{wf.name}</div>
                  <div className="text-xs text-slate-600">{wf.nodes?.length||0} agents</div>
                </div>
                <button onClick={()=>deleteWorkflow(wf.id)}
                  className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-red-400 transition-all ml-1">
                  <Trash2 size={11}/>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Canvas */}
      <div className="flex-1 flex flex-col">
        <div ref={canvasRef} className="flex-1 relative bg-surface-0 overflow-auto"
          style={{backgroundImage:'radial-gradient(circle, #ffffff08 1px, transparent 1px)',backgroundSize:'24px 24px'}}>
          {!nodes.length && (
            <div className="absolute inset-0 flex items-center justify-center text-slate-700 text-sm pointer-events-none">
              <div className="text-center">
                <Workflow size={40} className="mx-auto mb-3 opacity-30"/>
                <div>Click agents on the left to add them to the canvas</div>
                <div className="text-xs mt-1">Agents run left-to-right in order</div>
              </div>
            </div>
          )}
          {/* Connection lines */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none">
            {nodes.slice(0,-1).map((n,i) => {
              const next = nodes[i+1]
              const x1 = n.position.x+32, y1 = n.position.y+32
              const x2 = next.position.x+32, y2 = next.position.y+32
              return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
                stroke="#8b5cf640" strokeWidth="2" strokeDasharray="6 3" markerEnd="url(#arr)"/>
            })}
            <defs><marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M2 1L8 5L2 9" fill="none" stroke="#8b5cf6" strokeWidth="1.5"/>
            </marker></defs>
          </svg>
          {nodes.map(n => <AgentNode key={n.id} node={n} selected={selectedNode===n.id}
            onSelect={setSelectedNode} onDelete={deleteNode}/>)}
        </div>

        {/* Run bar */}
        <div className="border-t border-white/5 bg-surface-1 px-4 py-3 flex items-center gap-3">
          <input className="input-base flex-1 text-sm" placeholder="Describe the task to run through this workflow…"
            value={task} onChange={e=>setTask(e.target.value)}
            onKeyDown={e=>e.key==='Enter'&&runWorkflow()}/>
          <button onClick={runWorkflow} disabled={!nodes.length||!task.trim()||!selectedModel||running}
            className="btn-primary flex items-center gap-2 disabled:opacity-30 whitespace-nowrap">
            <Play size={14}/>{running?'Running…':'Run Workflow'}
          </button>
        </div>

        {/* Results */}
        {results && (
          <div className="border-t border-white/5 bg-surface-1 max-h-64 overflow-y-auto p-4">
            <div className="text-xs text-slate-500 uppercase tracking-wider mb-3">Workflow Results</div>
            {results.results?.map((r,i) => (
              <div key={i} className="mb-3 pb-3 border-b border-white/5 last:border-0">
                <div className="text-xs font-medium text-accent-purple mb-1">{r.node} ({r.agent})</div>
                <div className="text-xs text-slate-400 line-clamp-3">{r.output?.slice(0,300)}…</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
