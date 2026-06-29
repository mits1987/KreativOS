import React from 'react'
import { X, FileWarning } from 'lucide-react'
import useStore from '../store'
import api from '../utils/api'

export default function PermissionDialog() {
  const permissionDialog = useStore(s => s.permissionDialog)
  const setPermissionDialog = useStore(s => s.setPermissionDialog)
  if (!permissionDialog) return null

  const handleDecision = async (decision) => {
    try {
      await api.respondPermission(permissionDialog.req_id, decision)
      setPermissionDialog(null)
    } catch (err) {
      console.error('Failed to respond to permission request:', err)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-surface-1 border border-accent-purple/30 rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl animate-fade-in">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center">
              <FileWarning size={18} className="text-amber-400" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">Permission Required</h3>
              <p className="text-xs text-slate-500">An agent wants to access this path</p>
            </div>
          </div>
          <button onClick={() => setPermissionDialog(null)}
            className="text-slate-500 hover:text-white transition-colors">
            <X size={16} />
          </button>
        </div>

        <div className="bg-surface-0 rounded-lg px-3 py-2.5 mb-1">
          <div className="text-xs text-slate-500 mb-1">Path</div>
          <div className="text-sm font-mono text-amber-300 break-all">
            {permissionDialog.path}
          </div>
        </div>

        <div className="mb-5">
          <span className="text-xs text-slate-500">Operation: </span>
          <span className="text-xs text-slate-400 font-medium">{permissionDialog.operation}</span>
        </div>

        <div className="flex gap-2">
          <button onClick={() => handleDecision('allow_once')}
            className="flex-1 px-3 py-2.5 bg-accent-purple/15 border border-accent-purple/30
                       text-accent-purple rounded-lg text-sm font-medium
                       hover:bg-accent-purple/25 transition-all">
            Allow Once
          </button>
          <button onClick={() => handleDecision('allow_session')}
            className="flex-1 px-3 py-2.5 bg-emerald-500/15 border border-emerald-500/30
                       text-emerald-400 rounded-lg text-sm font-medium
                       hover:bg-emerald-500/25 transition-all">
            Allow Session
          </button>
          <button onClick={() => handleDecision('deny')}
            className="flex-1 px-3 py-2.5 bg-red-500/15 border border-red-500/30
                       text-red-400 rounded-lg text-sm font-medium
                       hover:bg-red-500/25 transition-all">
            Deny
          </button>
        </div>
      </div>
    </div>
  )
}
