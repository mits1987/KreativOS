/**
 * VoiceButton — Phase 6: Voice Input + Output
 * 
 * Strategy (Issue 3 fix — Vosk properly integrated):
 * 1. PRIMARY: Browser Web Speech API (Chrome/Edge, online) — zero setup
 * 2. FALLBACK: Vosk via backend WebSocket (Firefox, offline) — needs vosk installed
 * 3. TTS Output: Browser SpeechSynthesis (all browsers, no API key)
 */
import React, { useState, useRef, useEffect } from 'react'
import { Mic, MicOff, Loader, Volume2, VolumeX } from 'lucide-react'
import clsx from 'clsx'

// ── Text-to-Speech (Phase 6 — Voice Output) ─────────────────────────────────
export function useTTS() {
  const [speaking, setSpeaking] = useState(false)
  const [enabled, setEnabled] = useState(() => localStorage.getItem('ttsEnabled') === 'true')

  const speak = (text) => {
    if (!enabled || !window.speechSynthesis) return
    window.speechSynthesis.cancel()
    // Strip markdown before speaking
    const clean = text
      .replace(/```[\s\S]*?```/g, 'code block.')
      .replace(/[#*`_~>\[\]]/g, '')
      .replace(/\n+/g, ' ')
      .slice(0, 800)  // limit to ~1 min of speech
    const utt = new SpeechSynthesisUtterance(clean)
    utt.rate  = parseFloat(localStorage.getItem('ttsRate') || '1')
    utt.pitch = 1
    const voices = window.speechSynthesis.getVoices()
    const preferred = voices.find(v => v.lang.startsWith('en') && v.localService)
    if (preferred) utt.voice = preferred
    utt.onstart = () => setSpeaking(true)
    utt.onend   = () => setSpeaking(false)
    utt.onerror = () => setSpeaking(false)
    window.speechSynthesis.speak(utt)
  }

  const stop = () => { window.speechSynthesis?.cancel(); setSpeaking(false) }

  const toggle = () => {
    const next = !enabled
    setEnabled(next)
    localStorage.setItem('ttsEnabled', String(next))
    if (!next) stop()
  }

  return { speak, stop, speaking, enabled, toggle }
}

// ── Vosk backend STT (offline fallback) ──────────────────────────────────────
async function voskTranscribe(audioBlob, backendUrl) {
  const formData = new FormData()
  formData.append('audio', audioBlob, 'audio.webm')
  const r = await fetch(`${backendUrl}/api/voice/transcribe`, {
    method: 'POST', body: formData
  })
  if (!r.ok) throw new Error('Vosk backend unavailable')
  const data = await r.json()
  return data.transcript || ''
}

// ── Main VoiceButton component ────────────────────────────────────────────────
export default function VoiceButton({ onTranscript, backendUrl = 'http://localhost:8000' }) {
  const [state, setState]         = useState('idle') // idle|listening|processing|error
  const [transcript, setTranscript] = useState('')
  const [useVosk, setUseVosk]     = useState(false)
  const recognitionRef            = useRef(null)
  const mediaRecorderRef          = useRef(null)
  const chunksRef                 = useRef([])

  // Detect which STT to use
  useEffect(() => {
    const hasBrowserSTT = !!(window.SpeechRecognition || window.webkitSpeechRecognition)
    setUseVosk(!hasBrowserSTT)  // use Vosk only if browser STT unavailable
  }, [])

  // Setup browser STT
  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return
    const r = new SR()
    r.continuous    = false
    r.interimResults = true
    r.lang          = 'en-US'
    r.onstart = () => setState('listening')
    r.onresult = (e) => {
      const t = Array.from(e.results).map(r => r[0].transcript).join('')
      setTranscript(t)
      if (e.results[e.results.length - 1].isFinal) {
        onTranscript(t)
        setState('idle')
        setTranscript('')
      }
    }
    r.onerror  = (e) => { console.error('STT error:', e.error); setState('error'); setTimeout(() => setState('idle'), 2000) }
    r.onend    = () => { if (state === 'listening') setState('idle') }
    recognitionRef.current = r
  }, [onTranscript])

  // Vosk recording via MediaRecorder
  const startVosk = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream)
      chunksRef.current = []
      mr.ondataavailable = e => chunksRef.current.push(e.data)
      mr.onstop = async () => {
        setState('processing')
        stream.getTracks().forEach(t => t.stop())
        try {
          const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
          const text = await voskTranscribe(blob, backendUrl)
          if (text) { onTranscript(text); setTranscript('') }
          else setTranscript('(no speech detected)')
        } catch(e) {
          setTranscript('Vosk not available — use Chrome/Edge for browser STT')
        } finally {
          setTimeout(() => { setState('idle'); setTranscript('') }, 2000)
        }
      }
      mr.start()
      mediaRecorderRef.current = mr
      setState('listening')
    } catch(e) {
      setState('error')
      setTimeout(() => setState('idle'), 2000)
    }
  }

  const stopVosk = () => {
    mediaRecorderRef.current?.stop()
  }

  const toggle = () => {
    if (state === 'listening') {
      if (useVosk) stopVosk()
      else { recognitionRef.current?.stop(); setState('idle') }
    } else if (state === 'idle') {
      if (useVosk) startVosk()
      else {
        if (!recognitionRef.current) {
          alert('Voice input: Use Chrome or Edge browser for best experience.\n\nFirefox users: Make sure the KrestivOS backend is running with Vosk installed.')
          return
        }
        try { recognitionRef.current.start() } catch(e) { setState('error') }
      }
    }
  }

  const colors = {
    idle:       'text-slate-400 hover:text-white',
    listening:  'text-red-400',
    processing: 'text-accent-amber',
    error:      'text-red-500',
  }

  return (
    <div className="relative flex items-center gap-1">
      <button onClick={toggle} title={
        state === 'listening' ? 'Click to stop' :
        useVosk ? 'Voice input (Vosk offline)' : 'Voice input (Browser STT)'
      }
        className={clsx('p-2 rounded-lg hover:bg-surface-3 transition-all', colors[state])}>
        {state === 'listening'  ? <MicOff size={16} className="animate-pulse"/> :
         state === 'processing' ? <Loader size={16} className="animate-spin"/> :
         <Mic size={16} />}
      </button>
      {transcript && (
        <div className="absolute bottom-full mb-2 left-0 bg-surface-3 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-slate-300 whitespace-nowrap max-w-xs truncate shadow-xl z-50">
          {transcript}
        </div>
      )}
    </div>
  )
}

// ── TTS Toggle Button (Phase 6 — standalone) ──────────────────────────────────
export function TTSButton({ tts }) {
  return (
    <button onClick={tts.toggle} title={tts.enabled ? 'Disable voice output' : 'Enable voice output'}
      className={clsx('p-2 rounded-lg hover:bg-surface-3 transition-all',
        tts.enabled ? 'text-accent-purple' : 'text-slate-600',
        tts.speaking && 'animate-pulse')}>
      {tts.enabled ? <Volume2 size={16}/> : <VolumeX size={16}/>}
    </button>
  )
}
