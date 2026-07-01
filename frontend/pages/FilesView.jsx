import React, { useState, useEffect, useCallback } from 'react'
import { FolderOpen, FileText, Trash2, Download, RefreshCw, Plus, ChevronLeft, ChevronRight, History, RotateCcw } from 'lucide-react'
import clsx from 'clsx'
import api from '../utils/api'
import MessageRenderer from '../components/MessageRenderer'

const PAGE_SIZE = 50

function FileIcon({ name }) {
  const ext = name.split('.').pop()?.toLowerCase()
  const icons = {
    py: '🐍', js: '📜', jsx: '⚛️', ts: '📘', tsx: '⚛️',
    html: '🌐', css: '🎨', json: '📋', md: '📝',
    sh: '⚙️', yml: '🔧', yaml: '🔧', txt: '📄',
  }
  return <span className="text-base">{icons[ext] || '📄'}</span>
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

export default function FilesView() {
  const [files,    setFiles]    = useState([])
  const [total,    setTotal]    = useState(0)
  const [page,     setPage]     = useState(0)
  const [selected, setSelected] = useState(null)
  const [content,  setContent]  = useState('')
  const [loading,  setLoading]  = useState(false)
  const [editing,  setEditing]  = useState(false)
  const [creating, setCreating] = useState(false)
  const [newName,    setNewName]    = useState('')
  const [newBody,    setNewBody]    = useState('')
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [versionsFor, setVersionsFor] = useState(null)
  const [versions, setVersions] = useState([])
  const [versionsLoading, setVersionsLoading] = useState(false)

  const load = useCallback(async (p = page) => {
    setLoading(true)
    try {
      const data = await api.files(PAGE_SIZE, p * PAGE_SIZE)
      setFiles(data.files || [])
      setTotal(data.total || 0)
    } catch (e) {
      console.error('Failed to load files', e)
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => { load(page) }, [page])

  const openFile = async (file) => {
    setSelected(file); setEditing(false)
    try {
      const data = await api.readFile(file.name)
      setContent(data.content)
    } catch (e) { setContent(`Error reading file: ${e.message}`) }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    await api.deleteFile(deleteTarget)
    if (selected?.name === deleteTarget) { setSelected(null); setContent('') }
    setDeleteTarget(null)
    load(page)
  }

  const saveEdit = async () => {
    if (!selected) return
    await api.writeFile(selected.name, content)
    setEditing(false); load(page)
  }

  const createFile = async () => {
    if (!newName.trim()) return
    await api.writeFile(newName.trim(), newBody)
    setCreating(false); setNewName(''); setNewBody(''); load(0); setPage(0)
  }

  const downloadFile = (filename, fileContent) => {
    const blob = new Blob([fileContent], { type: 'text/plain' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href = url; a.download = filename.split('/').pop(); a.click()
    URL.revokeObjectURL(url)
  }

  const isCode = (name) =>
    /\.(py|js|jsx|ts|tsx|html|css|json|md|sh|yml|yaml|txt)$/i.test(name)

  const openVersions = async (name) => {
    setVersionsFor(name); setVersionsLoading(true); setVersions([])
    try {
      const data = await api.fileHistory(name)
      setVersions(data || [])
    } catch (e) { console.error('Failed to load versions', e) }
    finally { setVersionsLoading(false) }
  }

  const restoreVersion = async (backupName) => {
    try {
      await api.restoreVersion(backupName)
      setVersionsFor(null); setVersions([])
      load(page)
    } catch (e) { console.error('Failed to restore version', e) }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="flex h-full">
      {/* File list */}
      <div className="w-72 border-r border-white/5 bg-surface-1 flex flex-col">
        <div className="flex items-center justify-between px-4 py-4 border-b border-white/5">
          <div className="flex items-center gap-2">
            <FolderOpen size={16} className="text-accent-amber" />
            <span className="text-sm font-medium text-white">Workspace</span>
            <span className="text-xs text-slate-600">({total})</span>
          </div>
          <div className="flex items-center gap-1">
            <button onClick={() => setCreating(true)}
              className="p-1.5 text-slate-400 hover:text-white hover:bg-surface-3 rounded-lg transition-all">
              <Plus size={14} />
            </button>
            <button onClick={() => load(page)}
              className={clsx('p-1.5 text-slate-400 hover:text-white hover:bg-surface-3 rounded-lg transition-all', loading && 'animate-spin')}>
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto py-2">
          {files.length === 0 && !loading && (
            <div className="text-center py-12 text-slate-600 text-xs px-4">
              No files yet.<br />Files created by agents appear here.
            </div>
          )}
          {files.map(file => (
            <div key={file.name}
              onClick={() => openFile(file)}
              className={clsx(
                'group flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-all',
                selected?.name === file.name
                  ? 'bg-surface-3 text-white'
                  : 'text-slate-400 hover:bg-surface-2 hover:text-white'
              )}>
              <FileIcon name={file.name} />
              <div className="flex-1 min-w-0">
                <div className="text-xs font-mono truncate">{file.name}</div>
                <div className="text-xs text-slate-600">{formatSize(file.size)}</div>
              </div>
              <button onClick={e => { e.stopPropagation(); openVersions(file.name) }}
                className="opacity-0 group-hover:opacity-100 p-1 text-slate-600 hover:text-accent-amber transition-all">
                <History size={12} />
              </button>
              <button onClick={e => { e.stopPropagation(); setDeleteTarget(file.name) }}
                className="opacity-0 group-hover:opacity-100 p-1 text-slate-600 hover:text-red-400 transition-all">
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-2 border-t border-white/5">
            <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
              className="p-1 text-slate-500 hover:text-white disabled:opacity-30 transition-all">
              <ChevronLeft size={14} />
            </button>
            <span className="text-xs text-slate-600">
              {page + 1} / {totalPages}
            </span>
            <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
              className="p-1 text-slate-500 hover:text-white disabled:opacity-30 transition-all">
              <ChevronRight size={14} />
            </button>
          </div>
        )}
      </div>

      {/* Viewer / editor */}
      <div className="flex-1 flex flex-col">
        {creating ? (
          <div className="flex-1 p-6">
            <h3 className="text-white font-medium mb-4">Create New File</h3>
            <input className="input-base w-full mb-3" placeholder="filename.py"
              value={newName} onChange={e => setNewName(e.target.value)} />
            <textarea className="input-base w-full font-mono text-xs leading-relaxed"
              placeholder="File content…" rows={20}
              value={newBody} onChange={e => setNewBody(e.target.value)} />
            <div className="flex gap-3 mt-4">
              <button onClick={createFile} className="btn-primary">Create File</button>
              <button onClick={() => setCreating(false)} className="btn-ghost">Cancel</button>
            </div>
          </div>
        ) : selected ? (
          <>
            <div className="flex items-center justify-between px-5 py-3 border-b border-white/5 bg-surface-1">
              <div className="flex items-center gap-2">
                <FileIcon name={selected.name} />
                <span className="text-sm font-mono text-white">{selected.name}</span>
              </div>
              <div className="flex items-center gap-2">
                {editing ? (
                  <>
                    <button onClick={saveEdit} className="btn-primary text-xs py-1.5">Save</button>
                    <button onClick={() => setEditing(false)} className="btn-ghost text-xs py-1.5">Cancel</button>
                  </>
                ) : (
                  <>
                    <button onClick={() => setEditing(true)} className="btn-ghost text-xs py-1.5">Edit</button>
                    <button onClick={() => downloadFile(selected.name, content)}
                      className="btn-ghost text-xs py-1.5 flex items-center gap-1">
                      <Download size={12} /> Download
                    </button>
                    <button onClick={() => setDeleteTarget(selected.name)}
                      className="btn-ghost text-xs py-1.5 text-red-400 hover:text-red-300">Delete</button>
                  </>
                )}
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-5">
              {editing ? (
                <textarea className="input-base w-full h-full font-mono text-xs leading-relaxed resize-none"
                  value={content} onChange={e => setContent(e.target.value)} />
              ) : isCode(selected.name) ? (
                <MessageRenderer content={`\`\`\`${selected.name.split('.').pop()}\n${content}\n\`\`\``} />
              ) : (
                <pre className="text-xs text-slate-300 font-mono leading-relaxed whitespace-pre-wrap">{content}</pre>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-slate-600 text-sm">
            <div className="text-center">
              <FileText size={40} className="mx-auto mb-4 opacity-30" />
              <div>Select a file to view</div>
            </div>
          </div>
        )}
      </div>

      {/* Version history modal */}
      {versionsFor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-surface-1 border border-white/10 rounded-xl p-6 max-w-lg w-full mx-4 shadow-2xl animate-fade-in max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <div className="text-sm font-semibold text-white flex items-center gap-2">
                <History size={14} className="text-accent-amber" />
                Versions: {versionsFor}
              </div>
              <button onClick={() => { setVersionsFor(null); setVersions([]) }}
                className="text-slate-500 hover:text-white transition-all">✕</button>
            </div>
            <div className="flex-1 overflow-y-auto space-y-2">
              {versionsLoading && <div className="text-xs text-slate-500 text-center py-8">Loading…</div>}
              {!versionsLoading && versions.length === 0 && (
                <div className="text-xs text-slate-500 text-center py-8">No versions found.</div>
              )}
              {versions.map(v => (
                <div key={v.filename} className="flex items-center justify-between px-3 py-2 bg-surface-2 rounded-lg">
                  <div className="text-xs text-slate-300 font-mono">{v.timestamp}</div>
                  <div className="text-xs text-slate-500">{formatSize(v.size)}</div>
                  <button onClick={() => restoreVersion(v.filename)}
                    className="flex items-center gap-1 px-2 py-1 text-xs text-accent-amber hover:bg-surface-3 rounded transition-all">
                    <RotateCcw size={10} /> Restore
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Delete confirmation overlay */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-surface-1 border border-red-500/30 rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl animate-fade-in">
            <div className="text-sm font-semibold text-white mb-4">Delete {deleteTarget}?</div>
            <div className="text-xs text-slate-400 mb-6">This cannot be undone.</div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setDeleteTarget(null)}
                className="btn-ghost text-xs">Cancel</button>
              <button onClick={confirmDelete}
                className="px-3 py-2 bg-red-500/15 border border-red-500/30 text-red-400 rounded-lg text-xs font-medium hover:bg-red-500/25 transition-all">
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
