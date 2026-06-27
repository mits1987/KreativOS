@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  * { box-sizing: border-box; }
  body {
    background-color: #0a0a0f;
    color: #e2e8f0;
    font-family: 'Inter', system-ui, sans-serif;
    margin: 0;
    overflow: hidden;
    height: 100vh;
  }
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: #12121a; }
  ::-webkit-scrollbar-thumb { background: #2a2a3f; border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: #3a3a5f; }
}

@layer components {
  .glass {
    background: rgba(26, 26, 38, 0.8);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.06);
  }
  .glass-hover:hover {
    background: rgba(34, 34, 51, 0.9);
    border-color: rgba(255,255,255,0.1);
  }
  .glow-purple { box-shadow: 0 0 20px rgba(139, 92, 246, 0.15); }
  .glow-green { box-shadow: 0 0 20px rgba(16, 185, 129, 0.15); }
  .btn-primary {
    @apply bg-accent-purple hover:bg-purple-500 text-white font-medium px-4 py-2 rounded-lg transition-all duration-150 text-sm;
  }
  .btn-ghost {
    @apply hover:bg-surface-3 text-slate-400 hover:text-white px-3 py-2 rounded-lg transition-all duration-150 text-sm;
  }
  .input-base {
    @apply bg-surface-2 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-accent-purple/50 focus:ring-1 focus:ring-accent-purple/30 transition-all;
  }
  .tag {
    @apply text-xs px-2 py-0.5 rounded-full font-medium;
  }
  .sidebar-item {
    @apply flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-all duration-150 text-sm text-slate-400 hover:text-white hover:bg-surface-3;
  }
  .sidebar-item.active {
    @apply bg-surface-3 text-white;
  }
}

/* Typing cursor */
.typing-cursor::after {
  content: '▋';
  animation: blink 1s step-end infinite;
  color: #8b5cf6;
}
@keyframes blink { 50% { opacity: 0; } }

/* Code blocks */
pre { margin: 0 !important; border-radius: 8px !important; }
code { font-family: 'JetBrains Mono', monospace !important; font-size: 13px !important; }

/* Message animations */
.message-enter { animation: slideUp 0.25s ease-out; }
@keyframes slideUp {
  from { transform: translateY(10px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

/* Agent indicator pulse */
.agent-pulse {
  animation: agentPulse 2s ease-in-out infinite;
}
@keyframes agentPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
