import React, { useState, useEffect } from 'react'
import api from '../utils/api'

const STEPS = [
  {
    title: 'Welcome to KreativOS',
    description: 'Your local AI agent operating system. I can orchestrate multi-agent pipelines, generate documents, run code, and more — all running 100% locally.',
    action: 'Check Ollama Status'
  },
  {
    title: 'Pull Recommended Models',
    description: 'For the best experience, I recommend pulling at least one model. KreativOS works with any Ollama model.',
    action: 'Pull llama3.2:3b'
  },
  {
    title: 'Try Your First Task',
    description: 'Ask me to do something! Try: "Write a Python script that generates fibonacci numbers and save it as fib.py"',
    action: 'Start Using KreativOS'
  }
]

export default function OnboardingWizard({ onComplete }) {
  const [step, setStep] = useState(0)
  const [ollamaStatus, setOllamaStatus] = useState(null)
  const [pulling, setPulling] = useState(false)
  const [pullStatus, setPullStatus] = useState('')

  useEffect(() => {
    checkOllama()
  }, [])

  const checkOllama = async () => {
    try {
      const h = await api.get('/api/health')
      setOllamaStatus(h.ollama || 'unknown')
    } catch {
      setOllamaStatus('disconnected')
    }
  }

  const handleAction = async () => {
    if (step === 0) {
      await checkOllama()
      setStep(1)
    } else if (step === 1) {
      setPulling(true)
      setPullStatus('Pulling llama3.2:3b...')
      fetch('http://localhost:11434/api/pull', {
        method: 'POST',
        body: JSON.stringify({ name: 'llama3.2:3b' })
      }).then(r => {
        if (r.ok) setPullStatus('Pull complete!')
        else setPullStatus('Pull failed — you can pull models manually later')
      }).catch(() => setPullStatus('Ollama not reachable — pull manually later'))
      setStep(2)
    } else {
      localStorage.setItem('onboarding_done', 'true')
      onComplete()
    }
  }

  const skip = () => {
    localStorage.setItem('onboarding_done', 'true')
    onComplete()
  }

  const s = STEPS[step]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-8 max-w-lg w-full mx-4 shadow-2xl">
        <div className="flex gap-2 mb-6">
          {STEPS.map((_, i) => (
            <div key={i} className={`h-1 flex-1 rounded-full ${i <= step ? 'bg-teal-500' : 'bg-zinc-700'}`} />
          ))}
        </div>

        <h2 className="text-xl font-semibold text-white mb-2">{s.title}</h2>
        <p className="text-zinc-400 mb-6">{s.description}</p>

        {step === 0 && ollamaStatus && (
          <div className={`text-sm mb-4 ${ollamaStatus === 'disconnected' ? 'text-red-400' : 'text-green-400'}`}>
            Ollama: {ollamaStatus === 'disconnected' ? 'Not running' : 'Connected'}
          </div>
        )}

        {step === 1 && pullStatus && (
          <div className="text-sm text-zinc-400 mb-4">{pullStatus}</div>
        )}

        <div className="flex gap-3">
          <button onClick={handleAction}
            className="flex-1 px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white rounded-lg transition-colors">
            {s.action}
          </button>
          <button onClick={skip}
            className="px-4 py-2 text-zinc-400 hover:text-zinc-300 transition-colors">
            Skip
          </button>
        </div>
      </div>
    </div>
  )
}
