import React, { useState, useRef } from 'react'
import {
  MessageSquare, FolderOpen, Settings, ChevronLeft, Plus, Trash2,
  Sparkles, Zap, LayoutDashboard, Search, Package, GitBranch, Workflow,
  Blocks, Database, Clock, Shield, Activity,
  BookOpen, Star, LogOut, Network,
} from 'lucide-react'
import useStore from '../store'
import api from '../utils/api'
import clsx from 'clsx'
import BrainMark from './BrainMark'

// ── Nav structure — 4 purposeful groups ───────────────────────────────────────
const NAV = [
  // Core — unlabeled, always prominent
  { id:'dashboard',  icon:LayoutDashboard, label:'Dashboard',    group:'core'   },
  { id:'chat',       icon:MessageSquare,   label:'Chat',         group:'core'   },
  { id:'tasks',      icon:Zap,             label:'Tasks',        group:'core'   },
  { id:'prompts',    icon:BookOpen,        label:'Prompts',      group:'core'   },
  // Create
  { id:'appbuilder', icon:Blocks,          label:'App Builder',  group:'create' },
  { id:'canvas',     icon:Workflow,        label:'Canvas',       group:'create' },
  { id:'office',     icon:Sparkles,        label:'Office Files', group:'create' },
  { id:'pipeline',   icon:GitBranch,       label:'Pipeline',     group:'create' },
  // Workspace
  { id:'files',      icon:FolderOpen,      label:'Files',        group:'data'   },
  { id:'memory',     icon:Database,        label:'Memory',       group:'data'   },
  { id:'hub',        icon:Package,         label:'Model Hub',    group:'data'   },
  { id:'mcp',        icon:Network,         label:'MCP Servers',  group:'data'   },
  // System
  { id:'runs',       icon:Activity,        label:'Run History',  group:'system' },
  { id:'scheduler',  icon:Clock,           label:'Scheduler',    group:'system' },
  { id:'audit',      icon:Shield,          label:'Audit Log',    group:'system' },
  { id:'settings',   icon:Settings,        label:'Settings',     group:'system' },
]

const GROUP_META = {
  core:   { label: null },
  create: { label: 'Create' },
  data:   { label: 'Workspace' },
  system: { label: 'System' },
}

// ── Collapsed sidebar ─────────────────────────────────────────────────────────
function SidebarCollapsed({ activeView, setActiveView, setSidebarOpen, logout }) {
  const groups = {}
  NAV.forEach(item => {
    if (!groups[item.group]) groups[item.group] = []
    groups[item.group].push(item)
  })

  return (
    <div className="w-[52px] bg-surface-1 border-r border-white/5 flex flex-col items-center py-3 overflow-y-auto">
      {/* Logo mark */}
      <button onClick={() => setSidebarOpen(true)}
        className="mb-3 p-1.5 rounded-xl hover:bg-surface-3 transition-all group"
        title="Expand sidebar">
        <div className="w-7 h-7 text-surface-1">
          <BrainMark size={28} fill="currentColor"/>
        </div>
      </button>

      {/* Grouped icons with thin dividers */}
      {Object.entries(groups).map(([group, items], gi) => (
        <React.Fragment key={group}>
          {gi > 0 && <div className="w-6 h-px bg-white/8 my-1.5"/>}
          {items.map(({ id, icon: Icon, label }) => (
            <button key={id} onClick={() => setActiveView(id)} title={label}
              className={clsx(
                'w-9 h-9 flex items-center justify-center rounded-lg transition-all mb-0.5',
                activeView === id
                  ? 'bg-accent-purple/20 text-accent-purple'
                  : 'text-slate-600 hover:text-white hover:bg-surface-3'
              )}>
              <Icon size={16}/>
            </button>
          ))}
        </React.Fragment>
      ))}

      <div className="mt-auto pt-2">
        <button onClick={logout} title="Sign out"
          className="w-9 h-9 flex items-center justify-center rounded-lg text-slate-700 hover:text-red-400 hover:bg-surface-3 transition-all">
          <LogOut size={15}/>
        </button>
      </div>
    </div>
  )
}

// ── Nav item ──────────────────────────────────────────────────────────────────
function NavItem({ id, icon: Icon, label, active, onClick }) {
  return (
    <button onClick={onClick}
      className={clsx(
        'w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all duration-150 relative group',
        active
          ? 'bg-accent-purple/12 text-white font-medium'
          : 'text-slate-500 hover:text-slate-200 hover:bg-white/5'
      )}>
      {/* Active indicator bar */}
      {active && (
        <span className="absolute left-0 top-1 bottom-1 w-0.5 rounded-full bg-accent-purple"/>
      )}
      <Icon size={15} className={active ? 'text-accent-purple' : 'text-current'}/>
      <span className="text-xs leading-none">{label}</span>
    </button>
  )
}

// ── Expanded sidebar ──────────────────────────────────────────────────────────
export default function Sidebar() {
  const conversations = useStore(s => s.conversations)
  const activeConvId  = useStore(s => s.activeConvId)
  const setActiveConv = useStore(s => s.setActiveConv)
  const createConversation = useStore(s => s.createConversation)
  const deleteConversation = useStore(s => s.deleteConversation)
  const sidebarOpen  = useStore(s => s.sidebarOpen)
  const setSidebarOpen = useStore(s => s.setSidebarOpen)
  const activeView   = useStore(s => s.activeView)
  const setActiveView = useStore(s => s.setActiveView)
  const ollamaStatus = useStore(s => s.ollamaStatus)
  const agents       = useStore(s => s.agents)
  const logout       = useStore(s => s.logout)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [isSearching, setIsSearching] = useState(false)
  const [deleteConfirmId, setDeleteConfirmId] = useState(null)
  const searchTimerRef = useRef(null)
  const lastNavRef = useRef(0)

  const handleSearch = (q) => {
    setSearchQuery(q)
    clearTimeout(searchTimerRef.current)
    if (!q.trim()) {
      setSearchResults([])
      return
    }
    searchTimerRef.current = setTimeout(async () => {
      setIsSearching(true)
      try {
        const results = await api.get(`/api/conversations/search?q=${encodeURIComponent(q)}`)
        setSearchResults(results)
      } catch {}
      setIsSearching(false)
    }, 300)
  }

  const handleNav = (view) => {
    const now = Date.now()
    if (now - lastNavRef.current < 200) return
    lastNavRef.current = now
    setActiveView(view)
  }

  const displayConvs = searchQuery.trim() && searchResults.length > 0
    ? searchResults
    : conversations.filter(c =>
        c.title.toLowerCase().includes(searchQuery.toLowerCase())
      )

  if (!sidebarOpen) {
    return (
      <SidebarCollapsed
        activeView={activeView}
        setActiveView={handleNav}
        setSidebarOpen={setSidebarOpen}
        logout={logout}
      />
    )
  }

  const groups = {}
  NAV.forEach(item => {
    if (!groups[item.group]) groups[item.group] = []
    groups[item.group].push(item)
  })

  const statusColor = {
    connected:    'bg-emerald-400',
    disconnected: 'bg-red-500',
  }[ollamaStatus] || 'bg-slate-600'

  return (
    <div className="w-60 bg-surface-1 border-r border-white/5 flex flex-col select-none">

      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-3 py-3 border-b border-white/5 flex-shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 flex-shrink-0 text-surface-1">
            <BrainMark size={28} fill="currentColor"/>
          </div>
          <div className="flex flex-col leading-none">
            <span className="text-sm font-semibold text-white tracking-tight">KreativOS</span>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className={clsx('w-1.5 h-1.5 rounded-full', statusColor)}/>
              <span className="text-xs text-slate-600 capitalize">{ollamaStatus || 'offline'}</span>
            </div>
          </div>
        </div>
        <button onClick={() => setSidebarOpen(false)}
          className="p-1 text-slate-600 hover:text-white hover:bg-surface-3 rounded-lg transition-all">
          <ChevronLeft size={14}/>
        </button>
      </div>

      {/* ── Nav ───────────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5">
        {Object.entries(groups).map(([group, items]) => {
          const meta = GROUP_META[group]
          return (
            <div key={group}>
              {meta.label && (
                <div className="px-3 pt-3 pb-1">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest">
                    {meta.label}
                  </span>
                </div>
              )}
              {items.map(item => (
                <NavItem
                  key={item.id}
                  {...item}
                  active={activeView === item.id}
                  onClick={() => handleNav(item.id)}
                />
              ))}
            </div>
          )
        })}

        {/* ── Chat history (shown when Chat is active) ─────────────────── */}
        {activeView === 'chat' && (
          <div className="mt-2 pt-2 border-t border-white/5">
            <div className="flex items-center justify-between px-3 py-1.5">
              <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest">
                Conversations
              </span>
              <button onClick={() => createConversation()}
                className="p-1 text-slate-600 hover:text-white hover:bg-surface-3 rounded transition-all"
                title="New chat">
                <Plus size={11}/>
              </button>
            </div>
            <div className="relative mb-1 px-2">
              <Search size={10} className="absolute left-5 top-2.5 text-slate-600"/>
              <input
                className="w-full bg-surface-3/50 border border-white/8 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-accent-purple/30 transition-colors"
                placeholder="Search…"
                value={searchQuery}
                onChange={e => handleSearch(e.target.value)}
              />
            </div>
            <div className="space-y-0.5 px-1">
              {displayConvs.map(conv => {
                const agentIcon = agents.find(a => a.id === conv.agent)?.icon || '🤖'
                return (
                  <div key={conv.id}
                    onClick={() => { setActiveConv(conv.id); handleNav('chat') }}
                    className={clsx(
                      'group flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer transition-all',
                      activeConvId === conv.id
                        ? 'bg-surface-3 text-white'
                        : 'text-slate-500 hover:text-white hover:bg-surface-2'
                    )}>
                    <span className="text-[11px] flex-shrink-0">{agentIcon}</span>
                    <span className="flex-1 truncate text-xs">{conv.title}</span>
                    <button
                      onClick={e => { e.stopPropagation(); setDeleteConfirmId(conv.id) }}
                      className="opacity-0 group-hover:opacity-100 text-slate-700 hover:text-red-400 transition-all p-0.5 rounded">
                      <Trash2 size={10}/>
                    </button>
                  </div>
                )
              })}
              {!displayConvs.length && (
                <div className="text-center py-4 text-slate-700 text-xs">
                  {searchQuery && isSearching ? 'Searching…' : 'No chats yet'}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Delete confirmation overlay */}
      {deleteConfirmId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-surface-1 border border-red-500/30 rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl animate-fade-in">
            <div className="text-sm font-semibold text-white mb-4">Delete conversation?</div>
            <div className="text-xs text-slate-400 mb-6">This cannot be undone.</div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setDeleteConfirmId(null)}
                className="btn-ghost text-xs">Cancel</button>
              <button onClick={() => { deleteConversation(deleteConfirmId); setDeleteConfirmId(null) }}
                className="px-3 py-2 bg-red-500/15 border border-red-500/30 text-red-400 rounded-lg text-xs font-medium hover:bg-red-500/25 transition-all">
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Footer ────────────────────────────────────────────────────────── */}
      <div className="px-3 py-2.5 border-t border-white/5 flex-shrink-0 flex items-center justify-between">
        <span className="text-xs text-slate-700 font-mono">v1.0</span>
        <button onClick={logout} title="Sign out"
          className="flex items-center gap-1.5 px-2 py-1 text-slate-600 hover:text-red-400 hover:bg-surface-3 rounded-lg transition-all text-xs">
          <LogOut size={12}/> Sign out
        </button>
      </div>
    </div>
  )
}
