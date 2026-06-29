/**
 * Phase 1 Fix: api.js
 *
 * Key fixes:
 *  - Retry with exponential backoff on GET calls ONLY (idempotent)
 *  - Streaming POST (chat) never auto-retries — would cause duplicate messages
 *  - SSE keepalive comments (": keepalive") are silently ignored
 *  - Connection lost indicator returned via thrown error for caller to handle
 *  - 401 responses auto-clear auth and redirect to login
 */

const getBase    = () => localStorage.getItem('backendUrl') || ''
const getHeaders = () => {
  const token = localStorage.getItem('authToken')
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

const handle401 = (r) => {
  if (r.status === 401) {
    localStorage.removeItem('authToken')
    localStorage.removeItem('authUser')
    // Force full page reload so React re-mounts with auth state cleared
    window.location.reload()
  }
}

// ── Retry helper (GET only) ────────────────────────────────────────────────────
async function fetchWithRetry(url, opts, maxRetries = 3) {
  let lastError
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const r = await fetch(url, opts)
      // Return 4xx immediately — callers handle 401/403; retrying won't help
      if (r.status >= 400 && r.status < 500) return r
      if (!r.ok) throw new Error(`API ${r.status}`)  // 5xx → retry
      return r
    } catch (err) {
      if (err.message?.startsWith('API ')) throw err  // HTTP error, no retry
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
    handle401(r)
    if (!r.ok) {
      if (r.status === 403) {
        const body = await r.json().catch(() => ({}))
        if (body && body.status === 'pending') {
          throw { code: 'PERMISSION_REQUIRED', ...body }
        }
      }
      throw new Error(`API ${r.status}`)
    }
    return r.json()
  },

  // ── POST / DELETE — no retry (not idempotent) ─────────────────────────────
  async post(path, body) {
    const r = await fetch(`${getBase()}${path}`, {
      method:  'POST',
      headers: getHeaders(),
      body:    JSON.stringify(body),
    })
    handle401(r)
    if (!r.ok) {
      if (r.status === 403) {
        const errBody = await r.json().catch(() => ({}))
        if (errBody?.status === 'pending') {
          throw { code: 'PERMISSION_REQUIRED', ...errBody }
        }
        throw new Error(`API 403: ${errBody?.detail || 'Forbidden'}`)
      }
      throw new Error(`API ${r.status}: ${await r.text().catch(() => '')}`)
    }
    return r.json()
  },

  async delete(path) {
    const r = await fetch(`${getBase()}${path}`, {
      method:  'DELETE',
      headers: getHeaders(),
    })
    handle401(r)
    if (!r.ok) {
      if (r.status === 403) {
        const errBody = await r.json().catch(() => ({}))
        if (errBody?.status === 'pending') {
          throw { code: 'PERMISSION_REQUIRED', ...errBody }
        }
      }
      throw new Error(`API ${r.status}`)
    }
    if (r.status === 204) return {}
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

    if (!r.ok) {
      handle401(r)
      throw new Error(`Stream ${r.status}`)
    }

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

  // ── Orchestrator — streaming SSE ─────────────────────────────────────────
  async *streamOrchestrate(task, model, project = '') {
    const r = await fetch(`${getBase()}/api/orchestrate`, {
      method: 'POST', headers: getHeaders(),
      body: JSON.stringify({ task, model, project }),
    })
    if (!r.ok) { handle401(r); throw new Error(`Orchestrate ${r.status}`) }
    const reader = r.body.getReader()
    const dec    = new TextDecoder()
    let   buf    = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      const lines = buf.split('\n'); buf = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const raw = line.slice(6)
        if (raw === '[DONE]') return
        try { yield JSON.parse(raw) } catch {}
      }
    }
  },

  // ── Named helpers ─────────────────────────────────────────────────────────
  health:            () => api.get('/api/health'),

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

  // Pipeline — streaming SSE
  pipelineTemplates: () => api.get('/api/pipeline/templates'),
  async *streamPipeline(task, model, template, project = '', skip_ralph = false) {
    const r = await fetch(`${getBase()}/api/pipeline/run`, {
      method: 'POST', headers: getHeaders(),
      body: JSON.stringify({ task, model, template, project, skip_ralph }),
    })
    if (!r.ok) { handle401(r); throw new Error(`Pipeline ${r.status}`) }
    const reader = r.body.getReader()
    const dec    = new TextDecoder()
    let   buf    = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      const lines = buf.split('\n'); buf = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const raw = line.slice(6)
        if (raw === '[DONE]') return
        try { yield JSON.parse(raw) } catch {}
      }
    }
  },

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

  // Scheduler
  scheduledTasks:    ()                       => api.get('/api/scheduler/tasks'),
  createScheduled:   (t)                      => api.post('/api/scheduler/tasks', t),
  deleteScheduled:   (id)                     => api.delete(`/api/scheduler/tasks/${id}`),
  toggleScheduled:   (id)                     => api.post(`/api/scheduler/tasks/${id}/toggle`, {}),
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

  // Permissions
  pendingPermissions: () => api.get('/api/permissions/pending'),
  respondPermission: (req_id, decision) =>
    api.post('/api/permissions/respond', { req_id, decision }),
  workspace: () => api.get('/api/permissions/workspace'),
}

export default api
