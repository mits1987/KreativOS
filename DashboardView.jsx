import React, { useState } from 'react'
import {
  MessageSquare, FolderOpen, Settings, ChevronLeft, Plus, Trash2,
  Zap, Brain, LayoutDashboard, Search, Package, GitBranch, Workflow,
  Blocks, Eye, Database, Clock, Users, Terminal, Shield, HardDrive,
  BookOpen, Star, Bot, Sparkles
} from 'lucide-react'
import useStore from '../store'
import clsx from 'clsx'

const NAV = [
  // Main
  { id:'dashboard',  icon:LayoutDashboard, label:'Dashboard',    group:'main' },
  { id:'chat',       icon:MessageSquare,   label:'Chat',         group:'main' },
  { id:'tasks',      icon:Zap,             label:'Tasks',        group:'main' },
  { id:'prompts',    icon:BookOpen,        label:'Prompts',      group:'main' },
  // Build
  { id:'pipeline',   icon:GitBranch,       label:'Pipeline',     group:'build' },
  { id:'appbuilder', icon:Blocks,          label:'App Builder',  group:'build' },
  { id:'canvas',     icon:Workflow,        label:'Canvas',       group:'build' },
  { id:'office',     icon:Sparkles,        label:'Office Files', group:'build', badge:'New' },
  // Tools
  { id:'codereview', icon:Eye,             label:'Code Review',  group:'tools' },
  { id:'memory',     icon:Database,        label:'Memory',       group:'tools' },
  { id:'files',      icon:FolderOpen,      label:'Files',        group:'tools' },
  { id:'hub',        icon:Package,         label:'Model Hub',    group:'tools' },
  { id:'skills',     icon:Star,            label:'Skills',       group:'tools', badge:'New' },
  // System
  { id:'scheduler',  icon:Clock,           label:'Scheduler',    group:'system' },
  { id:'telegram',   icon:Bot,             label:'Telegram Bot', group:'system', badge:'New' },
  { id:'audit',      icon:Shield,          label:'Audit Log',    group:'system', badge:'New' },
  { id:'backup',     icon:HardDrive,       label:'Backup',       group:'system', badge:'New' },
  { id:'users',      icon:Users,           label:'Users',        group:'system' },
  { id:'settings',   icon:Settings,        label:'Settings',     group:'system' },
]

const GROUP_LABELS = { main:null, build:'Build', tools:'Tools', system:'System' }

export default function Sidebar() {
  const {
    conversations, activeConvId, setActiveConv, createConversation,
    deleteConversation, sidebarOpen, setSidebarOpen,
    activeView, setActiveView, ollamaStatus, agents,
  } = useStore()
  const [search, setSearch] = useState('')
  const filtered = conversations.filter(c => c.title.toLowerCase().includes(search.toLowerCase()))

  if (!sidebarOpen) return (
    <div className="w-14 bg-surface-1 border-r border-white/5 flex flex-col items-center py-3 gap-1 overflow-y-auto">
      <button onClick={()=>setSidebarOpen(true)} className="p-2 text-slate-400 hover:text-white hover:bg-surface-3 rounded-lg transition-all mb-2">
        <Brain size={20} className="text-accent-purple"/>
      </button>
      {NAV.map(({ id, icon:Icon }) => (
        <button key={id} onClick={()=>setActiveView(id)}
          className={clsx('p-2 rounded-lg transition-all',
            activeView===id ? 'bg-surface-3 text-white' : 'text-slate-600 hover:text-white hover:bg-surface-3')}>
          <Icon size={15}/>
        </button>
      ))}
    </div>
  )

  const groups = {}
  NAV.forEach(item => { if(!groups[item.group]) groups[item.group]=[]; groups[item.group].push(item) })

  return (
    <div className="w-64 bg-surface-1 border-r border-white/5 flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 flex-shrink-0">
        <div className="flex items-center gap-2">
          <Brain size={17} className="text-accent-purple"/>
          <span className="font-semibold text-white text-sm">KrestivOS</span>
          <span className="text-xs text-slate-600 font-mono">v3.1</span>
          <span className={clsx('w-2 h-2 rounded-full flex-shrink-0',
            ollamaStatus==='connected' ? 'bg-accent-green' :
            ollamaStatus==='disconnected' ? 'bg-red-500' : 'bg-slate-500')}
            title={`Ollama: ${ollamaStatus}`}/>
        </div>
        <button onClick={()=>setSidebarOpen(false)} className="text-slate-500 hover:text-white transition-colors">
          <ChevronLeft size={14}/>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5">
        {Object.entries(groups).map(([group, items]) => (
          <div key={group}>
            {GROUP_LABELS[group] && (
              <div className="text-xs text-slate-700 uppercase tracking-widest px-3 pt-3 pb-1 font-medium">
                {GROUP_LABELS[group]}
              </div>
            )}
            {items.map(({ id, icon:Icon, label, badge }) => (
              <button key={id} onClick={()=>setActiveView(id)}
                className={clsx('sidebar-item w-full', activeView===id && 'active')}>
                <Icon size={14}/>
                <span className="flex-1 text-left text-xs">{label}</span>
                {badge && (
                  <span className="text-xs px-1.5 py-0.5 rounded-full bg-accent-purple/15 text-accent-purple/80">
                    {badge}
                  </span>
                )}
              </button>
            ))}
          </div>
        ))}

        {activeView === 'chat' && (
          <div className="mt-2">
            <div className="flex items-center justify-between px-3 py-2">
              <span className="text-xs text-slate-700 uppercase tracking-widest font-medium">Chats</span>
              <button onClick={()=>createConversation()}
                className="p-1 text-slate-500 hover:text-white hover:bg-surface-3 rounded transition-all">
                <Plus size={12}/>
              </button>
            </div>
            {conversations.length > 5 && (
              <div className="relative mb-1 px-1">
                <Search size={11} className="absolute left-4 top-2.5 text-slate-600"/>
                <input className="input-base w-full pl-8 py-1.5 text-xs"
                  placeholder="Search chats…" value={search} onChange={e=>setSearch(e.target.value)}/>
              </div>
            )}
            <div className="space-y-0.5">
              {filtered.map(conv => (
                <div key={conv.id}
                  onClick={()=>{ setActiveConv(conv.id); setActiveView('chat') }}
                  className={clsx('group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-all',
                    activeConvId===conv.id ? 'bg-surface-3 text-white' : 'text-slate-500 hover:text-white hover:bg-surface-2')}>
                  <span className="text-xs flex-shrink-0">{agents.find(a=>a.id===conv.agent)?.icon||'🤖'}</span>
                  <span className="flex-1 truncate text-xs">{conv.title}</span>
                  <button onClick={e=>{e.stopPropagation();deleteConversation(conv.id)}}
                    className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-red-400 transition-all">
                    <Trash2 size={11}/>
                  </button>
                </div>
              ))}
              {!filtered.length && <div className="text-center py-4 text-slate-700 text-xs">No chats yet</div>}
            </div>
          </div>
        )}
      </div>

      <div className="px-4 py-2.5 border-t border-white/5 flex-shrink-0">
        <div className="flex items-center gap-2 text-xs text-slate-700">
          <Terminal size={10}/>
          <span>Ollama · 10 Phases · 19 Views</span>
        </div>
      </div>
    </div>
  )
}
