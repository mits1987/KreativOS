import { create } from 'zustand'

/**
 * Phase 1 Fix: Zustand store
 *
 * Key fix: cap messages per conversation at MAX_MESSAGES_PER_CONV (200).
 * The real unbounded-growth risk is not conversation count (50 × ~1KB = trivial)
 * but a single very long conversation's messages array.
 * When the cap is hit, the oldest 50 messages are pruned and a notice is inserted.
 */

const MAX_MESSAGES_PER_CONV = 200
const PRUNE_AMOUNT          = 50

const useStore = create((set, get) => ({
  // ── Settings ───────────────────────────────────────────────────────────────
  backendUrl:    localStorage.getItem('backendUrl') || 'http://localhost:8000',
  setBackendUrl: (url) => {
    localStorage.setItem('backendUrl', url)
    set({ backendUrl: url })
  },

  // ── Models ────────────────────────────────────────────────────────────────
  models:           [],
  selectedModel:    localStorage.getItem('selectedModel') || '',
  setModels:        (models) => set({ models }),
  setSelectedModel: (m) => {
    localStorage.setItem('selectedModel', m)
    set({ selectedModel: m })
  },

  // ── Agents ────────────────────────────────────────────────────────────────
  agents:           [],
  setAgents:        (agents) => set({ agents }),
  selectedAgent:    localStorage.getItem('selectedAgent') || 'general',
  setSelectedAgent: (a) => {
    localStorage.setItem('selectedAgent', a)
    set({ selectedAgent: a })
  },

  // ── Conversations ──────────────────────────────────────────────────────────
  conversations: JSON.parse(localStorage.getItem('conversations') || '[]'),
  activeConvId:  null,

  createConversation: (title = 'New Chat') => {
    const id   = `conv_${Date.now()}`
    const conv = {
      id,
      title,
      messages:  [],
      agent:     get().selectedAgent,
      model:     get().selectedModel,
      createdAt: new Date().toISOString(),
    }
    const convs = [conv, ...get().conversations]
    localStorage.setItem('conversations', JSON.stringify(convs))
    set({ conversations: convs, activeConvId: id })
    return id
  },

  getActiveConv: () => {
    const { conversations, activeConvId } = get()
    return conversations.find(c => c.id === activeConvId)
  },

  setActiveConv: (id) => set({ activeConvId: id }),

  addMessage: (convId, message) => {
    const convs = get().conversations.map(c => {
      if (c.id !== convId) return c

      let messages = [...c.messages, { ...message, id: `msg_${Date.now()}` }]

      // [P1 Fix] Cap messages to prevent unbounded localStorage growth
      if (messages.length > MAX_MESSAGES_PER_CONV) {
        const notice = {
          id:      `msg_trim_${Date.now()}`,
          role:    'assistant',
          content: `*(Earlier messages trimmed — conversation exceeded ${MAX_MESSAGES_PER_CONV} messages. ` +
                   `The most recent ${MAX_MESSAGES_PER_CONV - PRUNE_AMOUNT} messages are shown.)*`,
          agent:   'general',
        }
        messages = [notice, ...messages.slice(-(MAX_MESSAGES_PER_CONV - PRUNE_AMOUNT))]
      }

      // Auto-title from first user message
      const title =
        c.title === 'New Chat' && message.role === 'user'
          ? message.content.slice(0, 50) + (message.content.length > 50 ? '…' : '')
          : c.title

      return { ...c, messages, title }
    })
    localStorage.setItem('conversations', JSON.stringify(convs))
    set({ conversations: convs })
  },

  updateLastMessage: (convId, content) => {
    const convs = get().conversations.map(c => {
      if (c.id !== convId) return c
      const messages = [...c.messages]
      if (messages.length > 0) {
        messages[messages.length - 1] = { ...messages[messages.length - 1], content }
      }
      return { ...c, messages }
    })
    localStorage.setItem('conversations', JSON.stringify(convs))
    set({ conversations: convs })
  },

  deleteConversation: (id) => {
    const convs       = get().conversations.filter(c => c.id !== id)
    const activeConvId =
      get().activeConvId === id ? (convs[0]?.id || null) : get().activeConvId
    localStorage.setItem('conversations', JSON.stringify(convs))
    set({ conversations: convs, activeConvId })
  },

  clearConversations: () => {
    localStorage.setItem('conversations', '[]')
    set({ conversations: [], activeConvId: null })
  },

  // ── Files ─────────────────────────────────────────────────────────────────
  files:    [],
  setFiles: (files) => set({ files }),

  // ── UI State ──────────────────────────────────────────────────────────────
  sidebarOpen:    true,
  setSidebarOpen: (v) => set({ sidebarOpen: v }),
  activeView:     'dashboard',
  setActiveView:  (v) => set({ activeView: v }),

  // ── Streaming ─────────────────────────────────────────────────────────────
  isStreaming:    false,
  setIsStreaming: (v) => set({ isStreaming: v }),

  // ── Ollama status ──────────────────────────────────────────────────────────
  ollamaStatus:    'unknown',
  setOllamaStatus: (s) => set({ ollamaStatus: s }),
}))

export default useStore
