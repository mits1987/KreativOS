import React, { useState } from 'react'
import {
  MessageSquare, FolderOpen, Settings, ChevronLeft, Plus, Trash2,
  Zap, LayoutDashboard, Search, Package, GitBranch, Workflow,
  Blocks, Database, Clock, Users, Terminal, Shield, HardDrive,
  BookOpen, Star, Bot, Sparkles, LogOut, ChevronRight,
} from 'lucide-react'
import useStore from '../store'
import clsx from 'clsx'

// ── KreativOS brain mark (matches favicon.svg) ─────────────────────────────────
function BrainMark({ size = 24 }) {
  const s = size
  const cx = s / 2, cy = s / 2, r = s * 0.13
  return (
    <svg width={s} height={s} viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <line x1="20" y1="16" x2="32" y2="32" stroke="#8B5CF6" strokeWidth="2.5" strokeLinecap="round" opacity="0.8"/>
      <line x1="44" y1="16" x2="32" y2="32" stroke="#8B5CF6" strokeWidth="2.5" strokeLinecap="round" opacity="0.8"/>
      <line x1="14" y1="38" x2="32" y2="32" stroke="#10B981" strokeWidth="2.5" strokeLinecap="round" opacity="0.8"/>
      <line x1="50" y1="38" x2="32" y2="32" stroke="#10B981" strokeWidth="2.5" strokeLinecap="round" opacity="0.8"/>
      <line x1="32" y1="32" x2="32" y2="52" stroke="#8B5CF6" strokeWidth="2.5" strokeLinecap="round" opacity="0.8"/>
      <circle cx="20" cy="16" r="4.5" fill="#8B5CF6"/>
      <circle cx="44" cy="16" r="4.5" fill="#8B5CF6"/>
      <circle cx="14" cy="38" r="4" fill="#10B981"/>
      <circle cx="50" cy="38" r="4" fill="#10B981"/>
      <circle cx="32" cy="52" r="4" fill="#6366F1"/>
      <circle cx="32" cy="32" r="8" fill="#8B5CF6"/>
      <circle cx="32" cy="32" r="5" fill="currentColor"/>
      <circle cx="32" cy="32" r="2.5" fill="#8B5CF6"/>
    </svg>
  )
}

// ── Nav structure — 4 purposeful groups ───────────────────────────────────────
const NAV = [
  // Core — unlabeled, always prominent
  { id:'chat',       icon:MessageSquare,   label:'Chat',         group:'core'   },
  { id:'tasks',      icon:Zap,             label:'Tasks',        group:'core'   },
  { id:'dashboard',  icon:LayoutDashboard, label:'Dashboard',    group:'core'   },
  { id:'prompts',    icon:BookOpen,        label:'Prompts',      group:'core'   },
  // Create
  { id:'appbuilder', icon:Blocks,          label:'App Builder',  group:'create' },
  { id:'canvas',     icon:Workflow,        label:'Canvas',       group:'create' },
  { id:'office',     icon:Sparkles,        label:'Office Files', group:'create' },
  { id:'pipeline',   icon:GitBranch,       label:'Pipeline',     group:'create' },
  // Workspace
  { id:'files',      icon:FolderOpen,      label:'Files',        group:'data'   },
  { id:'memory',     icon:Database,        label:'Memory',       group:'data'   },
  { id:'skills',     icon:Star,            label:'Skills',       group:'data'   },
  { id:'hub',        icon:Package,         label:'Model Hub',    group:'data'   },
  // System
  { id:'scheduler',  icon:Clock,           label:'Scheduler',    group:'system' },
  { id:'telegram',   icon:Bot,             label:'Telegram Bot', group:'system' },
  { id:'audit',      icon:Shield,          label:'Audit Log',    group:'system' },
  { id:'backup',     icon:HardDrive,       label:'Backup',       group:'system' },
  { id:'users',      icon:Users,           label:'Users',        group:'system' },
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
          <BrainMark size={28}/>
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
  const {
    conversations, activeConvId, setActiveConv, createConversation,
    deleteConversation, sidebarOpen, setSidebarOpen,
    activeView, setActiveView, ollamaStatus, agents, logout,
  } = useStore()
  const [search, setSearch] = useState('')
  const filtered = conversations.filter(c =>
    c.title.toLowerCase().includes(search.toLowerCase())
  )

  if (!sidebarOpen) {
    return (
      <SidebarCollapsed
        activeView={activeView}
        setActiveView={setActiveView}
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
            <BrainMark size={28}/>
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
                  onClick={() => setActiveView(item.id)}
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
            {conversations.length > 5 && (
              <div className="relative mb-1 px-2">
                <Search size={10} className="absolute left-5 top-2.5 text-slate-600"/>
                <input
                  className="w-full bg-surface-3/50 border border-white/8 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-accent-purple/30 transition-colors"
                  placeholder="Search…"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                />
              </div>
            )}
            <div className="space-y-0.5 px-1">
              {filtered.map(conv => {
                const agentIcon = agents.find(a => a.id === conv.agent)?.icon || '🤖'
                return (
                  <div key={conv.id}
                    onClick={() => { setActiveConv(conv.id); setActiveView('chat') }}
                    className={clsx(
                      'group flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer transition-all',
                      activeConvId === conv.id
                        ? 'bg-surface-3 text-white'
                        : 'text-slate-500 hover:text-white hover:bg-surface-2'
                    )}>
                    <span className="text-[11px] flex-shrink-0">{agentIcon}</span>
                    <span className="flex-1 truncate text-xs">{conv.title}</span>
                    <button
                      onClick={e => { e.stopPropagation(); deleteConversation(conv.id) }}
                      className="opacity-0 group-hover:opacity-100 text-slate-700 hover:text-red-400 transition-all p-0.5 rounded">
                      <Trash2 size={10}/>
                    </button>
                  </div>
                )
              })}
              {!filtered.length && (
                <div className="text-center py-4 text-slate-700 text-xs">No chats yet</div>
              )}
            </div>
          </div>
        )}
      </div>

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
