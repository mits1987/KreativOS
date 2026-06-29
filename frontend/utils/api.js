/**
 * Phase 1 Fix: api.js
 *
 * Key fixes:
 *  - Retry with exponential backoff on GET calls ONLY (idempotent)
 *  - Streaming POST (chat) never auto-retries — would cause duplicate messages
 *  - SSE keepalive comments (": keepalive") are silently ignored
 *  - Connection lost indicator returned via thrown error for caller to handle
 */

const getBase    = () => localStorage.getItem('backendUrl') || 'http://localhost:8000'
const getHeaders = () => {
  const token = localStorage.getItem('authToken')
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

// ── Retry helper (GET only) ────────────────────────────────────────────────────
async function fetchWithRetry(url, opts, maxRetries = 3) {
  let lastError
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const r = await fetch(url, opts)
      if (!r.ok) throw new Error(`API ${r.status}`)
      return r
    } catch (err) {
      lastError = err
      if (attempt < maxRetries - 1) {
        // Exponential backoff with jitter: 1s, 2s, 4s ± 200ms
        const delay = Math.pow(2, attempt) * 1000 + Math.random() * 200
        await new Promise(res => setTimeout(res, delay))
      }
    }
  }
  throw lastError
}

export const api = {
  // ── GET with retry ───────────────────────────────────────────────────────────
  async get(path) {
    const r = await fetchWithRetry(`${getBase()}${path}`, { headers: getHeaders() })
    return r.json()
  },

  // ── POST / DELETE — no retry (not idempotent) ─────────────────────────────
  async post(path, body) {
    const r = await fetch(`${getBase()}${path}`, {
      method:  'POST',
      headers: getHeaders(),
      body:    JSON.stringify(body),
    })
    if (!r.ok) throw new Error(`API ${r.status}: ${await r.text()}`)
    return r.json()
  },

  async delete(path) {
    const r = await fetch(`${getBase()}${path}`, {
      method:  'DELETE',
      headers: getHeaders(),
    })
    if (!r.ok) throw new Error(`API ${r.status}`)
    return r.json()
  },

  // ── Streaming chat — NO retry, NO auto-reconnect ───────────────────────────
  // Retrying a streaming POST would send the message twice.
  // If the connection drops, the caller shows a "connection lost" indicator.
  async *streamChat(model, messages, agent, project = '', useWebSearch = false) {
    const r = await fetch(`${getBase()}/api/chat/stream`, {
      method:  'POST',
      headers: getHeaders(),
      body:    JSON.stringify({
        model,
        messages,
        agent,
        project,
        use_web_search: useWebSearch,
      }),
    })

    if (!r.ok) throw new Error(`Stream ${r.status}`)

    const reader = r.body.getReader()
    const dec    = new TextDecoder()
    let   buf    = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buf += dec.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop() || ''

      for (const line of lines) {
        // SSE comment keepalive — silently skip
        if (line.startsWith(': ')) continue

        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') return
          try {
            const p = JSON.parse(data)
            if (p.content) yield p.content
          } catch {
            // malformed chunk — skip
          }
        }
      }
    }
  },

  // ── Named helpers ─────────────────────────────────────────────────────────
  health:            () => api.get('/api/health'),
  healthReady:       () => api.get('/api/health/ready'),
  models:            () => api.get('/api/models'),
  agents:            () => api.get('/api/agents'),
  dashboard:         () => api.get('/api/dashboard'),

  // Auth
  login:             (u, p)    => api.post('/api/auth/login', { username: u, password: p }),
  listUsers:         ()        => api.get('/api/auth/users'),
  createUser:        (u, p, r) => api.post('/api/auth/users', { username: u, password: p, role: r }),
  deleteUser:        (u)       => api.delete(`/api/auth/users/${u}`),

  // Tasks
  runTask: (task, model, agent_type, use_ralph_loop = true, project = '') =>
    api.post('/api/task/run', { task, model, agent_type, use_ralph_loop, project }),

  // Pipeline
  pipelineTemplates: ()                       => api.get('/api/pipeline/templates'),
  runPipeline:       (task, model, t, proj)   => api.post('/api/pipeline/run', { task, model, template: t, project: proj }),

  // Memory
  projects:          (limit = 50, offset = 0) => api.get(`/api/memory/projects?limit=${limit}&offset=${offset}`),
  getMemory:         (p)                      => api.get(`/api/memory/${encodeURIComponent(p)}`),
  addNote:           (p, note)                => api.post(`/api/memory/${encodeURIComponent(p)}/note`, { note }),
  deleteMemory:      (p)                      => api.delete(`/api/memory/${encodeURIComponent(p)}`),

  // Web search
  webSearch:         (q, max = 5)             => api.get(`/api/search?q=${encodeURIComponent(q)}&max_results=${max}`),

  // Files — paginated
  files:             (limit = 50, offset = 0) => api.get(`/api/files/list?limit=${limit}&offset=${offset}`),
  readFile:          (n)                      => api.get(`/api/files/read/${encodeURIComponent(n)}`),
  deleteFile:        (n)                      => api.delete(`/api/files/delete/${encodeURIComponent(n)}`),
  writeFile:         (filename, content)      => api.post('/api/files/write', { filename, content }),

  // App builder
  buildApp:          (description, model, app_type, project = '') =>
    api.post('/api/appbuilder/generate', { description, model, app_type, project }),
  previewFile:       (f)                      => api.get(`/api/appbuilder/preview/${encodeURIComponent(f)}`),

  // Canvas
  getWorkflows:      ()                       => api.get('/api/canvas/workflows'),
  saveWorkflow:      (wf)                     => api.post('/api/canvas/workflows', wf),
  deleteWorkflow:    (id)                     => api.delete(`/api/canvas/workflows/${id}`),
  runWorkflow:       (id, model, task)        => api.post(`/api/canvas/run/${id}`, { model, task }),

  // Code review
  reviewCode:        (code, language, model, filename = '') =>
    api.post('/api/review', { code, language, model, filename }),

  // Skills
  skillLeaderboard:  ()                       => api.get('/api/skills/leaderboard'),
  agentSkillStats:   (agent)                  => api.get(`/api/skills/${agent}`),
  gradeOutput:       (task, output, agent, model) =>
    api.post('/api/skills/grade', { task, output, agent, model }),

  // Scheduler
  scheduledTasks:    ()                       => api.get('/api/scheduler/tasks'),
  createScheduled:   (t)                      => api.post('/api/scheduler/tasks', t),
  deleteScheduled:   (id)                     => api.delete(`/api/scheduler/tasks/${id}`),
  toggleScheduled:   (id)                     => api.post(`/api/scheduler/tasks/${id}/toggle`, {}),
  runDueTasks:       ()                       => api.post('/api/scheduler/run-due', {}),

  // Prompts
  getPrompts:        ()                       => api.get('/api/prompts'),
  savePrompt:        (p)                      => api.post('/api/prompts', p),
  deletePrompt:      (id)                     => api.delete(`/api/prompts/${id}`),

  // Audit — paginated
  getAudit:          (n = 100, offset = 0, q = '') =>
    api.get(`/api/audit?n=${n}&offset=${offset}${q ? `&q=${encodeURIComponent(q)}` : ''}`),

  // Backup
  createBackup:      ()                       => api.post('/api/backup/create', {}),
  listBackups:       ()                       => api.get('/api/backup/list'),
  deleteBackup:      (f)                      => api.delete(`/api/backup/${f}`),
  restoreBackup:     (f)                      => api.post(`/api/backup/restore/${f}`, {}),

  // Telegram
  telegramStatus:    ()                       => api.get('/api/telegram/status'),
  telegramTest:      (model)                  => api.post('/api/telegram/test', { model }),

  // Model hub
  featuredModels:    ()                       => api.get('/api/hub/featured'),
  searchHub:         (q)                      => api.get(`/api/hub/search?q=${encodeURIComponent(q)}`),

  // Code execution
  execute:           (code, language)         => api.post('/api/execute', { code, language }),

  // Office
  generateOffice:    (prompt, model, format, title = '', project = '') =>
    api.post('/api/office/generate', { prompt, model, format, title, project }),
}

export default api
