import React, { useState, useRef, useEffect, useCallback } from 'react'
import { Send, StopCircle, ChevronDown, AlertCircle } from 'lucide-react'
import clsx from 'clsx'
import useStore from '../store'
import api from '../utils/api'
import MessageRenderer from '../components/MessageRenderer'

const MessageRow = React.memo(({ msg, isLast, isStreaming, liveContent, thinkingTime, agentInfo }) => (
  <div className="max-w-3xl mx-auto message-enter mb-6">
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
            {isLast && isStreaming && (
              <span className="text-xs text-slate-500 agent-pulse">
                {thinkingTime > 5
                  ? `Model is thinking… ${thinkingTime}s`
                  : 'thinking…'}
              </span>
            )}
          </div>
          <MessageRenderer
            content={isLast && isStreaming ? liveContent : (msg.content || '')}
            isStreaming={isLast && isStreaming}
          />
        </div>
      </div>
    )}
  </div>
))

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
              {selected === agent.id && (
                <div className="ml-auto w-1.5 h-1.5 rounded-full" style={{ backgroundColor: agent.color }} />
              )}
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
    persistMessage,
    selectedModel, setSelectedModel, models, selectedAgent, setSelectedAgent, agents,
    isStreaming, setIsStreaming,
  } = useStore()

  const [input,        setInput]        = useState('')
  const [streamError,  setStreamError]  = useState(null)
  const [thinkingTime, setThinkingTime] = useState(0)
  const [liveContent,  setLiveContent]  = useState('')
  const [inputHistory, setInputHistory] = useState([])   // sent messages, newest first
  const [historyIdx,   setHistoryIdx]   = useState(-1)   // -1 = current draft
  const messagesEndRef  = useRef(null)
  const scrollContainerRef = useRef(null)
  const userScrolledRef    = useRef(false)  // true when user has scrolled up
  const textareaRef     = useRef(null)
  const abortRef        = useRef(false)
  const lastChunkRef    = useRef(null)
  const thinkingTimerRef= useRef(null)
  const streamBufferRef = useRef('')
  const abortCtrlRef    = useRef(null)

  const conv     = conversations.find(c => c.id === activeConvId)
  const messages = conv?.messages || []

  // Only auto-scroll when user hasn't manually scrolled up
  useEffect(() => {
    if (!userScrolledRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  // Re-enable auto-scroll when streaming ends
  useEffect(() => {
    if (!isStreaming) userScrolledRef.current = false
  }, [isStreaming])

  const handleScroll = () => {
    const el = scrollContainerRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80
    userScrolledRef.current = !atBottom
  }
  // Load conversations from store on mount (App.jsx triggers the API call)
  useEffect(() => { useStore.getState().loadConversations() }, [])

  // Abort stream on unmount
  useEffect(() => () => { abortCtrlRef.current?.abort(); abortRef.current = true }, [])

  // Pick up prompts sent from PromptsView via CustomEvent or localStorage
  useEffect(() => {
    const handler = (e) => setInput(e.detail)
    window.addEventListener('use_prompt', handler)
    const pending = localStorage.getItem('pending_prompt')
    if (pending) { setInput(pending); localStorage.removeItem('pending_prompt') }
    return () => window.removeEventListener('use_prompt', handler)
  }, [])

  // Thinking-time counter: shows "Model is thinking… Xs" when no chunk for >5s
  useEffect(() => {
    if (isStreaming) {
      lastChunkRef.current = Date.now()
      thinkingTimerRef.current = setInterval(() => {
        const secs = Math.floor((Date.now() - (lastChunkRef.current || Date.now())) / 1000)
        setThinkingTime(secs)
      }, 1000)
    } else {
      clearInterval(thinkingTimerRef.current)
      setThinkingTime(0)
    }
    return () => clearInterval(thinkingTimerRef.current)
  }, [isStreaming])

  const send = useCallback(async (text) => {
    const content = (text || input).trim()
    if (!content || isStreaming || !selectedModel) return

    let convId = activeConvId
    if (!convId) {
      const conv = await createConversation()
      convId = conv.id
    }

    addMessage(convId, { role: 'user', content })
    persistMessage(convId, 'user', content)
    setInputHistory(prev => [content, ...prev.filter(h => h !== content)].slice(0, 50))
    setHistoryIdx(-1)
    setInput('')
    setStreamError(null)
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
    setIsStreaming(true)
    abortRef.current = false

    addMessage(convId, { role: 'assistant', content: '', agent: selectedAgent })

    const conv    = conversations.find(c => c.id === convId)
    const history = [...(conv?.messages || []), { role: 'user', content }]
      .map(m => ({ role: m.role, content: m.content }))

    try {
      abortCtrlRef.current = new AbortController()
      const signal = abortCtrlRef.current.signal
      const tick = (chunk) => {
        lastChunkRef.current = Date.now()
        streamBufferRef.current += chunk
        setLiveContent(streamBufferRef.current)
      }

      if (selectedAgent === 'orchestrator') {
        const ICONS = { researcher:'🔍', architect:'🏗️', coder:'💻', devops:'⚙️', general:'🤖' }
        for await (const event of api.streamOrchestrate(content, selectedModel, '', signal)) {
          if (abortRef.current) break
          if      (event.type === 'planning')      tick('🎯 **Planning your task…**\n\n')
          else if (event.type === 'plan') {
            const chain = (event.steps || []).map(s => s.agent).join(' → ')
            tick(`📋 **Plan:** ${chain}\n*${event.summary || ''}*\n\n`)
          }
          else if (event.type === 'agent_start') {
            const icon = ICONS[event.agent] || '🤖'
            tick(`${icon} **${event.agent}**${event.round > 1 ? ` (round ${event.round})` : ''}…\n`)
          }
          else if (event.type === 'tool_call') {
            const argStr = Object.entries(event.args || {}).map(([k,v]) =>
              `${k}=${JSON.stringify(v).slice(0,30)}`).join(', ')
            tick(`\`  → ${event.tool}(${argStr})\`\n`)
          }
          else if (event.type === 'agent_done') {
            const s = event.score != null ? ` (self-score: ${event.score}/10)` : ''
            tick(`✓ Done${s}\n\n`)
          }
          else if (event.type === 'audit_start')  tick('🔍 **Auditor reviewing…**\n')
          else if (event.type === 'audit_result') {
            const mark = event.passed ? '✅' : '⚠️'
            tick(`${mark} Score: ${event.score}/10 — ${event.passed ? 'Passed' : 'Needs revision'}\n\n`)
            if (!event.passed && event.feedback) tick(`*${event.feedback}*\n\n`)
          }
          else if (event.type === 'done') {
            tick('\n---\n\n')
            tick(event.output || '')
          }
          else if (event.type === 'error')        tick(`❌ ${event.message}`)
        }
      } else {
        for await (const chunk of api.streamChat(selectedModel, history, selectedAgent, '', false, signal)) {
          if (abortRef.current) break
          tick(chunk)
        }
      }
    } catch (e) {
      if (e?.name !== 'AbortError') {
        setStreamError('Connection lost — please try sending again.')
        updateLastMessage(convId, '*(Connection lost. Please resend.)*')
      }
    } finally {
      setIsStreaming(false)
      abortCtrlRef.current = null
      if (streamBufferRef.current) {
        updateLastMessage(convId, streamBufferRef.current)
        persistMessage(convId, 'assistant', streamBufferRef.current)
        streamBufferRef.current = ''
      }
      setLiveContent('')
      if (Notification.permission === 'granted' && !document.hasFocus()) {
        new Notification('KreativOS', { body: 'Task complete!' })
      } else if (Notification.permission === 'default') {
        Notification.requestPermission()
      }
    }
  }, [input, isStreaming, selectedModel, selectedAgent, activeConvId, conversations])

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); return }
    if (e.key === 'ArrowUp' && !input.trim()) {
      e.preventDefault()
      const idx = Math.min(historyIdx + 1, inputHistory.length - 1)
      setHistoryIdx(idx)
      if (inputHistory[idx] !== undefined) setInput(inputHistory[idx])
    }
    if (e.key === 'ArrowDown' && historyIdx >= 0) {
      e.preventDefault()
      const idx = historyIdx - 1
      setHistoryIdx(idx)
      setInput(idx < 0 ? '' : (inputHistory[idx] || ''))
    }
  }

  const startVoiceInput = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert('Voice input is not supported in this browser. Try Chrome or Edge.')
      return
    }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    const recognition = new SpeechRecognition()
    recognition.lang = 'en-US'
    recognition.interimResults = false
    recognition.start()
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript
      setInput(prev => prev + transcript)
    }
  }

  const quickPrompts = [
    { icon: '💻', label: 'Build a FastAPI REST API with CRUD',           agent: 'coder' },
    { icon: '🏗️', label: 'Design a SaaS app architecture',              agent: 'architect' },
    { icon: '🔍', label: 'Research best practices for microservices',    agent: 'researcher' },
    { icon: '⚙️', label: 'Write a Docker + CI/CD deployment pipeline',   agent: 'devops' },
  ]

  return (
    <div className="flex flex-col h-full">
      <div ref={scrollContainerRef} onScroll={handleScroll} className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 && (
          <div className="max-w-2xl mx-auto text-center mt-12">
            <div className="text-5xl mb-4">🧠</div>
            <h2 className="text-2xl font-bold text-white mb-2">KreativOS</h2>
            <p className="text-slate-500 mb-8 text-sm">
              Multi-agent · Ralph Loop · Voice · Skills · File workspace
            </p>
            <div className="grid grid-cols-2 gap-3">
              {quickPrompts.map((p, i) => (
                <button key={i}
                  onClick={() => { setSelectedAgent(p.agent); setInput(p.label); textareaRef.current?.focus() }}
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
            <MessageRow key={msg.id || i} msg={msg} isLast={isLast} isStreaming={isStreaming} liveContent={isLast && isStreaming ? liveContent : ''} thinkingTime={thinkingTime} agentInfo={agentInfo} />
          )
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Connection lost banner */}
      {streamError && (
        <div className="mx-4 mb-2 flex items-center gap-2 px-4 py-2.5 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400">
          <AlertCircle size={14} />
          {streamError}
          <button onClick={() => setStreamError(null)} className="ml-auto text-red-500 hover:text-red-300 text-lg">×</button>
        </div>
      )}

      {/* Input */}
      <div className="border-t border-white/5 bg-surface-1 px-4 py-4">
        <div className="max-w-3xl mx-auto">
          <div className="glass rounded-xl border border-white/10 focus-within:border-accent-purple/40 transition-all">
            <textarea ref={textareaRef} value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder={`Message ${agents.find(a => a.id === selectedAgent)?.name || 'KreativOS'}…`}
              rows={1} disabled={isStreaming}
              className="w-full bg-transparent px-4 py-3 text-sm text-white placeholder-slate-600 resize-none focus:outline-none max-h-40 overflow-y-auto"
              style={{ minHeight: '48px' }}
              onInput={e => {
                e.target.style.height = 'auto'
                e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px'
              }}
            />
            <div className="flex items-center justify-between px-3 pb-2 gap-2">
              <div className="flex items-center gap-2 flex-wrap">
                <AgentPicker agents={agents} selected={selectedAgent} onSelect={setSelectedAgent} />
                <ModelPicker models={models} selected={selectedModel} onSelect={setSelectedModel} />
              </div>
              <div className="flex items-center gap-2">
                <button onClick={startVoiceInput}
                  className="p-2 text-zinc-400 hover:text-white transition-colors"
                  title="Voice input" aria-label="Voice input">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m-4 0h8" />
                  </svg>
                </button>
                {isStreaming ? (
                  <button onClick={() => { abortCtrlRef.current?.abort(); abortRef.current = true; setIsStreaming(false) }}
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
            <p className="text-xs text-amber-500/70 mt-2 text-center">
              ⚠️ No model selected. Go to Settings to connect Ollama.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
