import { create } from 'zustand'

const useStore = create((set, get) => ({
  // ── Settings ──────────────────────────────────────────────────────────
  backendUrl: localStorage.getItem('backendUrl') || 'http://localhost:8000',
  setBackendUrl: (url) => {
    localStorage.setItem('backendUrl', url)
    set({ backendUrl: url })
  },

  // ── Models ────────────────────────────────────────────────────────────
  models: [],
  selectedModel: localStorage.getItem('selectedModel') || '',
  setModels: (models) => set({ models }),
  setSelectedModel: (m) => {
    localStorage.setItem('selectedModel', m)
    set({ selectedModel: m })
  },

  // ── Agents ────────────────────────────────────────────────────────────
  agents: [],
  setAgents: (agents) => set({ agents }),
  selectedAgent: localStorage.getItem('selectedAgent') || 'general',
  setSelectedAgent: (a) => {
    localStorage.setItem('selectedAgent', a)
    set({ selectedAgent: a })
  },

  // ── Conversations ─────────────────────────────────────────────────────
  conversations: JSON.parse(localStorage.getItem('conversations') || '[]'),
  activeConvId: null,

  createConversation: (title = 'New Chat') => {
    const id = `conv_${Date.now()}`
    const conv = {
      id,
      title,
      messages: [],
      agent: get().selectedAgent,
      model: get().selectedModel,
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
      const messages = [...c.messages, { ...message, id: `msg_${Date.now()}` }]
      // Auto-title from first user message
      const title = c.title === 'New Chat' && message.role === 'user'
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
    const convs = get().conversations.filter(c => c.id !== id)
    localStorage.setItem('conversations', JSON.stringify(convs))
    const activeConvId = get().activeConvId === id ? (convs[0]?.id || null) : get().activeConvId
    set({ conversations: convs, activeConvId })
  },

  clearConversations: () => {
    localStorage.setItem('conversations', '[]')
    set({ conversations: [], activeConvId: null })
  },

  // ── Files ─────────────────────────────────────────────────────────────
  files: [],
  setFiles: (files) => set({ files }),

  // ── UI State ──────────────────────────────────────────────────────────
  sidebarOpen: true,
  setSidebarOpen: (v) => set({ sidebarOpen: v }),
  activeView: 'dashboard', // chat | files | tasks | settings
  setActiveView: (v) => set({ activeView: v }),

  // ── Streaming ─────────────────────────────────────────────────────────
  isStreaming: false,
  setIsStreaming: (v) => set({ isStreaming: v }),

  // ── Status ────────────────────────────────────────────────────────────
  ollamaStatus: 'unknown', // connected | disconnected | unknown
  setOllamaStatus: (s) => set({ ollamaStatus: s }),
}))

export default useStore
