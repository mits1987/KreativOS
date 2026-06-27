const getBase = () => localStorage.getItem('backendUrl') || 'http://localhost:8000'
const getHeaders = () => {
  const token = localStorage.getItem('authToken')
  return { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }
}
export const api = {
  async get(path) {
    const r = await fetch(`${getBase()}${path}`, { headers: getHeaders() })
    if (!r.ok) throw new Error(`API ${r.status}`)
    return r.json()
  },
  async post(path, body) {
    const r = await fetch(`${getBase()}${path}`, { method:'POST', headers:getHeaders(), body:JSON.stringify(body) })
    if (!r.ok) throw new Error(`API ${r.status}: ${await r.text()}`)
    return r.json()
  },
  async delete(path) {
    const r = await fetch(`${getBase()}${path}`, { method:'DELETE', headers:getHeaders() })
    if (!r.ok) throw new Error(`API ${r.status}`)
    return r.json()
  },
  async *streamChat(model, messages, agent, project='', useWebSearch=false) {
    const r = await fetch(`${getBase()}/api/chat/stream`, {
      method:'POST', headers:getHeaders(),
      body: JSON.stringify({ model, messages, agent, project, use_web_search: useWebSearch }),
    })
    if (!r.ok) throw new Error(`Stream ${r.status}`)
    const reader = r.body.getReader()
    const dec = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      const lines = buf.split('\n'); buf = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') return
          try { const p = JSON.parse(data); if (p.content) yield p.content } catch {}
        }
      }
    }
  },
  // Core
  health:           () => api.get('/api/health'),
  models:           () => api.get('/api/models'),
  agents:           () => api.get('/api/agents'),
  dashboard:        () => api.get('/api/dashboard/v2'),
  // Auth
  login:            (u,p) => api.post('/api/auth/login', {username:u,password:p}),
  listUsers:        () => api.get('/api/auth/users'),
  createUser:       (u,p,r) => api.post('/api/auth/users', {username:u,password:p,role:r}),
  deleteUser:       (u) => api.delete(`/api/auth/users/${u}`),
  // Tasks
  runTask:          (task,model,agent_type,use_ralph_loop=true,project='') =>
                      api.post('/api/task/run', {task,model,agent_type,use_ralph_loop,project}),
  // Pipeline
  pipelineTemplates:() => api.get('/api/pipeline/templates'),
  runPipeline:      (task,model,template,project='') =>
                      api.post('/api/pipeline/run', {task,model,template,project}),
  // Memory
  projects:         () => api.get('/api/memory/projects'),
  getMemory:        (p) => api.get(`/api/memory/${encodeURIComponent(p)}`),
  addNote:          (p,note) => api.post(`/api/memory/${encodeURIComponent(p)}/note`, {note}),
  deleteMemory:     (p) => api.delete(`/api/memory/${encodeURIComponent(p)}`),
  // Web search
  webSearch:        (q,max=5) => api.get(`/api/search?q=${encodeURIComponent(q)}&max_results=${max}`),
  // App builder
  buildApp:         (description,model,app_type,project='') =>
                      api.post('/api/appbuilder/generate', {description,model,app_type,project}),
  previewFile:      (f) => api.get(`/api/appbuilder/preview/${encodeURIComponent(f)}`),
  // Canvas
  getWorkflows:     () => api.get('/api/canvas/workflows'),
  saveWorkflow:     (wf) => api.post('/api/canvas/workflows', wf),
  deleteWorkflow:   (id) => api.delete(`/api/canvas/workflows/${id}`),
  runWorkflow:      (id,model,task) => api.post(`/api/canvas/run/${id}`, {model,task}),
  // Office files (NEW)
  generateOffice:   (prompt,model,format,title='',project='') =>
                      api.post('/api/office/generate', {prompt,model,format,title,project}),
  // Code review
  reviewCode:       (code,language,model,filename='') =>
                      api.post('/api/review', {code,language,model,filename}),
  // Files
  files:            () => api.get('/api/files/list'),
  readFile:         (n) => api.get(`/api/files/read/${encodeURIComponent(n)}`),
  deleteFile:       (n) => api.delete(`/api/files/delete/${encodeURIComponent(n)}`),
  writeFile:        (filename,content) => api.post('/api/files/write', {filename,content}),
  // Skills (NEW)
  skillLeaderboard: () => api.get('/api/skills/leaderboard'),
  agentSkillStats:  (agent) => api.get(`/api/skills/${agent}`),
  gradeOutput:      (task,output,agent,model) =>
                      api.post('/api/skills/grade', {task,output,agent,model}),
  // Scheduler
  scheduledTasks:   () => api.get('/api/scheduler/tasks'),
  createScheduled:  (t) => api.post('/api/scheduler/tasks', t),
  deleteScheduled:  (id) => api.delete(`/api/scheduler/tasks/${id}`),
  toggleScheduled:  (id) => api.post(`/api/scheduler/tasks/${id}/toggle`, {}),
  runDueTasks:      () => api.post('/api/scheduler/run-due', {}),
  // Prompts (NEW)
  getPrompts:       () => api.get('/api/prompts'),
  savePrompt:       (p) => api.post('/api/prompts', p),
  deletePrompt:     (id) => api.delete(`/api/prompts/${id}`),
  // Audit (NEW)
  getAudit:         (n=100,q='') => api.get(`/api/audit?n=${n}${q?`&q=${encodeURIComponent(q)}`:''}`),
  // Backup (NEW)
  createBackup:     () => api.post('/api/backup/create', {}),
  listBackups:      () => api.get('/api/backup/list'),
  deleteBackup:     (f) => api.delete(`/api/backup/${f}`),
  restoreBackup:    (f) => api.post(`/api/backup/restore/${f}`, {}),
  // Telegram (NEW)
  telegramStatus:   () => api.get('/api/telegram/status'),
  telegramTest:     (model) => api.post('/api/telegram/test', {model}),
  // Model hub
  featuredModels:   () => api.get('/api/hub/featured'),
  searchHub:        (q) => api.get(`/api/hub/search?q=${encodeURIComponent(q)}`),
  // Code execution
  execute:          (code,language) => api.post('/api/execute', {code,language}),
}
export default api
