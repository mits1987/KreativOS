import React, { useState, useEffect } from 'react'
import { Users, Plus, Trash2, Shield, User } from 'lucide-react'
import api from '../utils/api'

export default function UsersView() {
  const [users, setUsers] = useState([])
  const [form, setForm] = useState({username:'',password:'',role:'user'})
  const [showAdd, setShowAdd] = useState(false)
  const [msg, setMsg] = useState('')

  const load = async () => {
    const d = await api.get('/api/auth/users')
    setUsers(d.users||[])
  }

  const add = async () => {
    if (!form.username.trim()||!form.password.trim()) return
    try {
      await api.post('/api/auth/users', form)
      setForm({username:'',password:'',role:'user'}); setShowAdd(false)
      setMsg('User created'); load()
    } catch(e) { setMsg('Error: '+e.message) }
    setTimeout(()=>setMsg(''),3000)
  }

  const del = async (u) => {
    if (!confirm(`Delete user "${u}"?`)) return
    await api.delete(`/api/auth/users/${u}`); load()
  }

  useEffect(()=>{ load() },[])

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Users size={20} className="text-accent-blue"/>
            <h1 className="text-xl font-bold text-white">User Management</h1>
          </div>
          <button onClick={()=>setShowAdd(!showAdd)} className="btn-primary text-xs flex items-center gap-1.5">
            <Plus size={12}/> Add User
          </button>
        </div>

        {msg && <div className="mb-4 px-4 py-2 rounded-lg bg-accent-green/10 border border-accent-green/20 text-accent-green text-xs">{msg}</div>}

        <div className="glass rounded-xl border border-white/10 p-3 mb-4 text-xs text-slate-500">
          <div className="flex items-start gap-2">
            <Shield size={13} className="text-accent-amber mt-0.5"/>
            <div>KreativOS uses optional auth. Default admin login: <span className="font-mono text-white">admin / admin123</span> — change this after setup. Auth is optional for single-user deployments.</div>
          </div>
        </div>

        {showAdd && (
          <div className="glass rounded-2xl border border-white/10 p-5 mb-5">
            <div className="text-sm font-medium text-white mb-4">New User</div>
            <div className="space-y-3">
              <input className="input-base w-full" placeholder="Username" value={form.username} onChange={e=>setForm({...form,username:e.target.value})}/>
              <input className="input-base w-full" type="password" placeholder="Password" value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/>
              <select className="input-base w-full" value={form.role} onChange={e=>setForm({...form,role:e.target.value})}>
                <option value="user">User</option>
                <option value="admin">Admin</option>
              </select>
              <div className="flex gap-2">
                <button onClick={add} className="btn-primary text-xs">Create User</button>
                <button onClick={()=>setShowAdd(false)} className="btn-ghost text-xs">Cancel</button>
              </div>
            </div>
          </div>
        )}

        <div className="space-y-2">
          {users.map(u => (
            <div key={u.username} className="glass rounded-xl border border-white/10 p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                {u.role==='admin' ? <Shield size={16} className="text-accent-amber"/> : <User size={16} className="text-slate-400"/>}
                <div>
                  <div className="text-sm font-medium text-white">{u.username}</div>
                  <div className="text-xs text-slate-500 capitalize">{u.role} · Created {new Date(u.created).toLocaleDateString()}</div>
                </div>
              </div>
              {u.username !== 'admin' && (
                <button onClick={()=>del(u.username)} className="p-1.5 text-slate-600 hover:text-red-400 transition-all">
                  <Trash2 size={14}/>
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
