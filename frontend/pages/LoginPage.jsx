import React, { useState } from 'react'
import { Lock, User, AlertCircle } from 'lucide-react'
import useStore from '../store'

function BrainMark({ size = 52 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <line x1="20" y1="16" x2="32" y2="32" stroke="#8B5CF6" strokeWidth="2.5" strokeLinecap="round" opacity="0.9"/>
      <line x1="44" y1="16" x2="32" y2="32" stroke="#8B5CF6" strokeWidth="2.5" strokeLinecap="round" opacity="0.9"/>
      <line x1="14" y1="38" x2="32" y2="32" stroke="#10B981" strokeWidth="2.5" strokeLinecap="round" opacity="0.9"/>
      <line x1="50" y1="38" x2="32" y2="32" stroke="#10B981" strokeWidth="2.5" strokeLinecap="round" opacity="0.9"/>
      <line x1="32" y1="32" x2="32" y2="52" stroke="#8B5CF6" strokeWidth="2.5" strokeLinecap="round" opacity="0.9"/>
      <circle cx="20" cy="16" r="4.5" fill="#8B5CF6"/>
      <circle cx="44" cy="16" r="4.5" fill="#8B5CF6"/>
      <circle cx="14" cy="38" r="4" fill="#10B981"/>
      <circle cx="50" cy="38" r="4" fill="#10B981"/>
      <circle cx="32" cy="52" r="4" fill="#6366F1"/>
      <circle cx="32" cy="32" r="8" fill="#8B5CF6"/>
      <circle cx="32" cy="32" r="5" fill="#0F0F1A"/>
      <circle cx="32" cy="32" r="2.5" fill="#8B5CF6"/>
    </svg>
  )
}

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)
  const login = useStore(s => s.login)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
    } catch (err) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-center h-screen bg-surface-0 relative overflow-hidden">
      {/* Background decoration */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-[-20%] left-[-10%] w-[500px] h-[500px] rounded-full bg-accent-purple/5 blur-3xl"/>
        <div className="absolute bottom-[-20%] right-[-10%] w-[400px] h-[400px] rounded-full bg-emerald-500/5 blur-3xl"/>
      </div>

      <div className="w-full max-w-[340px] relative">
        {/* Card */}
        <div className="glass border border-white/10 rounded-2xl p-8 shadow-2xl"
          style={{ background: 'rgba(15, 15, 26, 0.85)', backdropFilter: 'blur(20px)' }}>

          {/* Brand */}
          <div className="flex flex-col items-center mb-8">
            <div className="mb-4 relative">
              <div className="absolute inset-0 bg-accent-purple/20 blur-xl rounded-full"/>
              <BrainMark size={52}/>
            </div>
            <h1 className="text-xl font-bold text-white tracking-tight">KreativOS</h1>
            <p className="text-sm text-slate-500 mt-1">Agentic OS — sign in to continue</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="flex items-center gap-2 text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                <AlertCircle size={13} className="flex-shrink-0"/>
                <span>{error}</span>
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Username</label>
              <div className="relative">
                <User size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-600"/>
                <input
                  type="text"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  placeholder="admin"
                  autoFocus
                  className="w-full bg-white/5 border border-white/10 rounded-lg pl-9 pr-3 py-2.5 text-sm text-white placeholder-slate-700 focus:outline-none focus:border-accent-purple/50 focus:bg-white/8 transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Password</label>
              <div className="relative">
                <Lock size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-600"/>
                <input
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••"
                  className="w-full bg-white/5 border border-white/10 rounded-lg pl-9 pr-3 py-2.5 text-sm text-white placeholder-slate-700 focus:outline-none focus:border-accent-purple/50 focus:bg-white/8 transition-all"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !username || !password}
              className="w-full py-2.5 rounded-lg text-sm font-semibold text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ background: loading ? 'rgba(139,92,246,0.5)' : 'linear-gradient(135deg, #8B5CF6, #6366F1)' }}>
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  Signing in…
                </span>
              ) : 'Sign in'}
            </button>
          </form>

          <p className="text-xs text-slate-700 text-center mt-5 font-mono">
            default: admin / admin123
          </p>
        </div>
      </div>
    </div>
  )
}
