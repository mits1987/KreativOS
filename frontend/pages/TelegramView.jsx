import React, { useState, useEffect } from 'react'
import { Send, CheckCircle, XCircle, ExternalLink, Bot } from 'lucide-react'
import api from '../utils/api'
import useStore from '../store'

const STEPS = [
  { n:1, title:'Create Telegram bot', desc:'Open Telegram, search @BotFather, send /newbot, follow instructions, copy the token.' },
  { n:2, title:'Set env variable on VM', desc:'Edit your docker-compose.yml or .env file and add:', code:'TELEGRAM_BOT_TOKEN=your_token_here' },
  { n:3, title:'Get your Chat ID', desc:'Message @userinfobot on Telegram. It will reply with your ID. Then add:', code:'TELEGRAM_CHAT_ID=your_chat_id' },
  { n:4, title:'Restart KreativOS', desc:'Run:', code:'docker compose down && docker compose up -d' },
  { n:5, title:'Start chatting!', desc:'Open Telegram, find your bot, send /start. You can now send tasks from your phone.' },
]

export default function TelegramView() {
  const { selectedModel } = useStore()
  const [status, setStatus] = useState(null)
  const [testing, setTesting] = useState(false)
  const [testMsg, setTestMsg] = useState(null)

  useEffect(()=>{
    api.get('/api/telegram/status').then(setStatus).catch(()=>{})
  },[])

  const test = async () => {
    setTesting(true); setTestMsg(null)
    try {
      const r = await api.post('/api/telegram/test', { model: selectedModel })
      setTestMsg({ ok: r.success, text: r.success ? r.message : r.error })
    } catch(e) { setTestMsg({ ok:false, text: e.message }) }
    finally { setTesting(false) }
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-2xl mx-auto px-6 py-8">
        <div className="flex items-center gap-3 mb-2">
          <Bot size={20} className="text-sky-400"/>
          <h1 className="text-xl font-bold text-white">Telegram Bot</h1>
          {status && (
            <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${status.enabled ? 'bg-green-500/15 text-green-400' : 'bg-slate-500/15 text-slate-400'}`}>
              {status.enabled ? <><CheckCircle size={11}/>Active</> : <><XCircle size={11}/>Not configured</>}
            </span>
          )}
        </div>
        <p className="text-slate-500 text-sm mb-6">Control KreativOS from your phone via Telegram. Send tasks, get results — no browser needed.</p>

        {/* Status card */}
        {status && (
          <div className="glass rounded-xl border border-white/10 p-4 mb-5">
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="flex items-center gap-2">
                {status.bot_token_set ? <CheckCircle size={13} className="text-green-400"/> : <XCircle size={13} className="text-slate-600"/>}
                <span className="text-slate-400">Bot token</span>
              </div>
              <div className="flex items-center gap-2">
                {status.chat_id_set ? <CheckCircle size={13} className="text-green-400"/> : <XCircle size={13} className="text-slate-600"/>}
                <span className="text-slate-400">Chat ID whitelist</span>
              </div>
            </div>
            {status.enabled && (
              <div className="mt-3 pt-3 border-t border-white/10 flex items-center justify-between">
                <span className="text-xs text-slate-500">Bot is running and accepting messages</span>
                <button onClick={test} disabled={testing} className="btn-primary text-xs">
                  {testing ? 'Testing…' : 'Test Connection'}
                </button>
              </div>
            )}
            {testMsg && (
              <div className={`mt-2 text-xs px-3 py-2 rounded-lg ${testMsg.ok ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                {testMsg.text}
              </div>
            )}
          </div>
        )}

        {/* Available commands */}
        {status?.enabled && (
          <div className="glass rounded-xl border border-white/10 p-4 mb-5">
            <div className="text-xs text-slate-500 uppercase tracking-wider mb-3">Bot Commands</div>
            <div className="space-y-2 font-mono text-xs">
              {[
                ['/start',          'Show help and available commands'],
                ['/task <prompt>',  'Run an autonomous task with the current agent'],
                ['/agent <name>',   'Switch agent (coder/researcher/architect/devops)'],
                ['/status',         'Check if KreativOS backend is running'],
                ['(any message)',   'Chat with the current agent'],
              ].map(([cmd, desc])=>(
                <div key={cmd} className="flex gap-3">
                  <span className="text-accent-purple w-36 flex-shrink-0">{cmd}</span>
                  <span className="text-slate-400">{desc}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Setup steps */}
        {!status?.enabled && (
          <div>
            <div className="text-xs text-slate-600 uppercase tracking-wider mb-3">Setup Guide</div>
            <div className="space-y-3">
              {STEPS.map(s=>(
                <div key={s.n} className="glass rounded-xl border border-white/10 p-4">
                  <div className="flex items-start gap-3">
                    <div className="w-6 h-6 rounded-full bg-accent-purple/20 text-accent-purple text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                      {s.n}
                    </div>
                    <div>
                      <div className="text-sm font-medium text-white mb-1">{s.title}</div>
                      <div className="text-xs text-slate-400">{s.desc}</div>
                      {s.code && (
                        <code className="block mt-2 px-3 py-1.5 bg-surface-2 rounded-lg text-accent-green text-xs font-mono">
                          {s.code}
                        </code>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <a href="https://core.telegram.org/bots#how-do-i-create-a-bot" target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-xs text-accent-purple hover:underline mt-4">
              <ExternalLink size={12}/> Official Telegram Bot documentation
            </a>
          </div>
        )}
      </div>
    </div>
  )
}
