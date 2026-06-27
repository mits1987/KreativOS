import React, { useState, useRef, useEffect, useCallback } from 'react'
import { Send, StopCircle, ChevronDown, Plus, Trash2 } from 'lucide-react'
import clsx from 'clsx'
import useStore from '../store'
import api from '../utils/api'
import MessageRenderer from '../components/MessageRenderer'
import VoiceButton from './VoiceButton'

function AgentPicker({ agents, selected, onSelect }) {
  const [open, setOpen] = useState(false)
  const current = agents.find(a => a.id === selected)
  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-3 hover:bg-surface-4 border border-white/10 text-sm transition-all">
        <span>{current?.icon || '🤖'}</span>
        <span className="text-slate-300 font-medium hidden sm:inline">{current?.name || 'Agent'}</span>
        <ChevronDown size={13} className="text-slate-500" />
      </button>
      {open && (
        <div className="absolute bottom-full left-0 mb-2 w-52 bg-surface-2 border border-white/10 rounded-xl shadow-xl z-50 overflow-hidden">
          {agents.map(agent => (
            <button key={agent.id} onClick={() => { onSelect(agent.id); setOpen(false) }}
              className={clsx('w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-all hover:bg-surface-3',
                selected === agent.id ? 'bg-surface-3 text-white' : 'text-slate-400')}>
              <span>{agent.icon}</span>
              <span className="text-xs font-medium text-white">{agent.name}</span>
              {selected === agent.id && <div className="ml-auto w-1.5 h-1.5 rounded-full" style={{ backgroundColor: agent.color }} />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function ModelPicker({ models, selected, onSelect }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-3 hover:bg-surface-4 border border-white/10 text-sm transition-all">
        <span className="text-slate-300 font-mono text-xs max-w-24 truncate">{selected || 'Model'}</span>
        <ChevronDown size={13} className="text-slate-500" />
      </button>
      {open && (
        <div className="absolute bottom-full left-0 mb-2 w-56 bg-surface-2 border border-white/10 rounded-xl shadow-xl z-50 max-h-48 overflow-y-auto">
          {models.map(m => (
            <button key={m} onClick={() => { onSelect(m); setOpen(false) }}
              className={clsx('w-full text-left px-4 py-2.5 text-xs font-mono transition-all hover:bg-surface-3',
                selected === m ? 'bg-surface-3 text-white' : 'text-slate-400')}>
              {m}
            </button>
          ))}
          {!models.length && <div className="px-4 py-3 text-xs text-slate-500">No models found</div>}
        </div>
      )}
    </div>
  )
}

export default function ChatView() {
  const {
    conversations, activeConvId, createConversation, addMessage, updateLastMessage,
    selectedModel, setSelectedModel, models, selectedAgent, setSelectedAgent, agents,
    isStreaming, setIsStreaming, backendUrl,
  } = useStore()

  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)
  const textareaRef    = useRef(null)
  const abortRef       = useRef(false)

  const conv     = conversations.find(c => c.id === activeConvId)
  const messages = conv?.messages || []

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])
  useEffect(() => { if (!activeConvId) createConversation() }, [])

  const send = useCallback(async (text) => {
    const content = (text || input).trim()
    if (!content || isStreaming || !selectedModel) return

    let convId = activeConvId
    if (!convId) convId = createConversation()

    addMessage(convId, { role: 'user', content })
    setInput('')
    if (textareaRef.current) { textareaRef.current.style.height = 'auto' }
    setIsStreaming(true)
    abortRef.current = false

    addMessage(convId, { role: 'assistant', content: '', agent: selectedAgent })

    const conv = conversations.find(c => c.id === convId)
    const history = [...(conv?.messages || []), { role: 'user', content }]
      .map(m => ({ role: m.role, content: m.content }))

    try {
      let full = ''
      for await (const chunk of api.streamChat(selectedModel, history, selectedAgent)) {
        if (abortRef.current) break
        full += chunk
        updateLastMessage(convId, full)
      }
    } catch (e) {
      updateLastMessage(convId, `❌ Error: ${e.message}`)
    } finally {
      setIsStreaming(false)
    }
  }, [input, isStreaming, selectedModel, selectedAgent, activeConvId, conversations])

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  const quickPrompts = [
    { icon: '💻', label: 'Build a FastAPI REST API with CRUD', agent: 'coder' },
    { icon: '🏗️', label: 'Design a SaaS app architecture', agent: 'architect' },
    { icon: '🔍', label: 'Research best practices for microservices', agent: 'researcher' },
    { icon: '⚙️', label: 'Write a Docker + CI/CD deployment pipeline', agent: 'devops' },
  ]

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 && (
          <div className="max-w-2xl mx-auto text-center mt-12">
            <div className="text-5xl mb-4">🧠</div>
            <h2 className="text-2xl font-bold text-white mb-2">KrestivOS v2</h2>
            <p className="text-slate-500 mb-2 text-sm">Multi-agent · Ralph Loop · Voice · Skills · File workspace</p>
            <p className="text-slate-600 mb-8 text-xs">Powered by your local Ollama — 100% private, 100% free</p>
            <div className="grid grid-cols-2 gap-3">
              {quickPrompts.map((p, i) => (
                <button key={i} onClick={() => { setSelectedAgent(p.agent); setInput(p.label); textareaRef.current?.focus() }}
                  className="glass glass-hover p-4 rounded-xl text-left border border-white/10 transition-all group">
                  <div className="text-2xl mb-2">{p.icon}</div>
                  <div className="text-xs text-slate-300 group-hover:text-white">{p.label}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => {
          const isLast    = i === messages.length - 1
          const agentInfo = agents.find(a => a.id === (msg.agent || selectedAgent))
          return (
            <div key={msg.id || i} className="max-w-3xl mx-auto message-enter mb-6">
              {msg.role === 'user' ? (
                <div className="flex justify-end">
                  <div className="max-w-xl bg-surface-3 rounded-2xl rounded-br-sm px-4 py-3 text-sm text-slate-200 border border-white/10">
                    {msg.content}
                  </div>
                </div>
              ) : (
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center text-base flex-shrink-0 mt-1"
                    style={{ background: (agentInfo?.color || '#6366f1') + '20' }}>
                    {agentInfo?.icon || '🤖'}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-medium" style={{ color: agentInfo?.color || '#6366f1' }}>
                        {agentInfo?.name || 'Assistant'}
                      </span>
                      {isLast && isStreaming && <span className="text-xs text-slate-600 agent-pulse">thinking…</span>}
                    </div>
                    <MessageRenderer content={msg.content || ''} isStreaming={isLast && isStreaming && !msg.content} />
                  </div>
                </div>
              )}
            </div>
          )
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-white/5 bg-surface-1 px-4 py-4">
        <div className="max-w-3xl mx-auto">
          <div className="glass rounded-xl border border-white/10 focus-within:border-accent-purple/40 transition-all">
            <textarea ref={textareaRef} value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder={`Message ${agents.find(a => a.id === selectedAgent)?.name || 'KrestivOS'}…`}
              rows={1} disabled={isStreaming}
              className="w-full bg-transparent px-4 py-3 text-sm text-white placeholder-slate-600 resize-none focus:outline-none max-h-40 overflow-y-auto"
              style={{ minHeight: '48px' }}
              onInput={e => { e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px' }}
            />
            <div className="flex items-center justify-between px-3 pb-2 gap-2">
              <div className="flex items-center gap-2 flex-wrap">
                <AgentPicker agents={agents} selected={selectedAgent} onSelect={setSelectedAgent} />
                <ModelPicker models={models} selected={selectedModel} onSelect={setSelectedModel} />
                <VoiceButton onTranscript={(t) => send(t)} backendUrl={backendUrl} />
              </div>
              <div className="flex items-center gap-2">
                {isStreaming ? (
                  <button onClick={() => { abortRef.current = true; setIsStreaming(false) }}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-red-500/20 text-red-400 hover:bg-red-500/30 rounded-lg text-xs transition-all">
                    <StopCircle size={13} /> Stop
                  </button>
                ) : (
                  <button onClick={() => send()} disabled={!input.trim() || !selectedModel}
                    className="p-2 bg-accent-purple hover:bg-purple-500 disabled:opacity-30 disabled:cursor-not-allowed rounded-lg transition-all">
                    <Send size={14} className="text-white" />
                  </button>
                )}
              </div>
            </div>
          </div>
          {!selectedModel && (
            <p className="text-xs text-amber-500/70 mt-2 text-center">⚠️ No model selected. Check Settings.</p>
          )}
        </div>
      </div>
    </div>
  )
}
