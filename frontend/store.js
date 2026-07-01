import { create } from 'zustand'
import api from './utils/api'

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
  // ── Auth ──────────────────────────────────────────────────────────────────
  token:        localStorage.getItem('authToken') || null,
  user:         JSON.parse(localStorage.getItem('authUser') || 'null'),
  isAuthenticated: !!localStorage.getItem('authToken'),

  login: async (username, password) => {
    const base = localStorage.getItem('backendUrl') || 'http://localhost:8000'
    const r = await fetch(`${base}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      throw new Error(err.detail || 'Login failed')
    }
    const { token } = await r.json()
    localStorage.setItem('authToken', token)
    localStorage.setItem('authUser', JSON.stringify({ username }))
    set({ token, user: { username }, isAuthenticated: true })
  },

  logout: () => {
    localStorage.removeItem('authToken')
    localStorage.removeItem('authUser')
    set({ token: null, user: null, isAuthenticated: false })
  },

  // ── Settings ───────────────────────────────────────────────────────────────
  backendUrl: (() => {
    const stored = localStorage.getItem('backendUrl')
    if (stored) {
      const origin = window.location.origin
      // Stale local backendUrl — use relative URLs instead (no CORS)
      if (stored === origin || stored === 'http://localhost:8000' || stored === 'http://127.0.0.1:8000') {
        localStorage.removeItem('backendUrl')
        return ''
      }
    }
    return stored || ''
  })(),
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
  conversations: [],
  activeConvId:  localStorage.getItem('activeConvId') || null,
  isLoadingConversations: false,

  loadConversations: async () => {
    set({ isLoadingConversations: true })
    try {
      const convs = await api.get('/api/conversations')
      set({ conversations: convs, isLoadingConversations: false })
    } catch {
      set({ isLoadingConversations: false })
    }
  },

  createConversation: async (title, model) => {
    const t = title || `New Chat ${new Date().toLocaleString()}`
    const m = model || get().selectedModel
    const conv = await api.post('/api/conversations', { title: t, model: m })
    const convs = [{ ...conv, messages: conv.messages || [] }, ...get().conversations]
    localStorage.setItem('activeConvId', conv.id)
    set({ conversations: convs, activeConvId: conv.id })
    return conv
  },

  getActiveConv: () => {
    const { conversations, activeConvId } = get()
    return conversations.find(c => c.id === activeConvId)
  },

  setActiveConv: (id) => {
    localStorage.setItem('activeConvId', id)
    set({ activeConvId: id })
  },

  addMessage: (convId, message) => {
    const convs = get().conversations.map(c => {
      if (c.id !== convId) return c

      let messages = [...c.messages, { ...message, id: `msg_${Date.now()}` }]

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

      const title =
        c.title === 'New Chat' && message.role === 'user'
          ? message.content.slice(0, 50) + (message.content.length > 50 ? '…' : '')
          : c.title

      return { ...c, messages, title }
    })
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
    set({ conversations: convs })
  },

  persistMessage: async (convId, role, content) => {
    try {
      await api.post(`/api/conversations/${convId}/messages`, { role, content })
    } catch {}
  },

  deleteConversation: async (id) => {
    await api.delete(`/api/conversations/${id}`)
    const convs       = get().conversations.filter(c => c.id !== id)
    const activeConvId =
      get().activeConvId === id ? (convs[0]?.id || null) : get().activeConvId
    localStorage.setItem('activeConvId', activeConvId)
    set({ conversations: convs, activeConvId })
  },

  clearConversations: () => {
    localStorage.removeItem('activeConvId')
    set({ conversations: [], activeConvId: null })
  },

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

  // ── Permissions ──────────────────────────────────────────────────────────
  pendingPermissions: [],
  setPendingPermissions: (pp) => set({ pendingPermissions: pp }),
  permissionDialog: null,  // {req_id, path, operation} or null
  setPermissionDialog: (p) => set({ permissionDialog: p }),
}))

export default useStore
