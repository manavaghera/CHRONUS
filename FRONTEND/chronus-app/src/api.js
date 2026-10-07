// Client for the CHRONUS backend (CHRONUS/api_server.py). In development Vite
// proxies /api to it (vite.config.js); the production build is served by the
// backend itself (http://localhost:8001), so its API is on the same origin.
// Set VITE_API_BASE to call a backend somewhere else.
export const API = import.meta.env.VITE_API_BASE ?? (import.meta.env.DEV ? '/api' : '')

export const OFFLINE_MSG = "Can't reach the CHRONUS server. Start it with CHRONUS/start_server.bat or python CHRONUS/run_server.py (port 8001), then try again."

// Fired when the server asks for its access code (CHRONUS_ACCESS_CODE);
// App shows the sign-in screen.
export const LOGIN_EVENT = 'chronus:login-required'

export class ApiError extends Error {
  constructor(message, { status = 0, offline = false } = {}) {
    super(message)
    this.status = status
    this.offline = offline
  }
}

async function send(path, { method = 'GET', body, signal } = {}) {
  try {
    return await fetch(`${API}${path}`, {
      method,
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      credentials: 'same-origin',
      signal,
    })
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new ApiError(OFFLINE_MSG, { offline: true })
  }
}

async function failure(res) {
  let data = null
  try { data = await res.json() } catch { /* not JSON: proxy couldn't reach the backend */ }
  if (!data) return new ApiError(OFFLINE_MSG, { status: res.status, offline: true })
  if (res.status === 401 && data.login) window.dispatchEvent(new Event(LOGIN_EVENT))
  const detail = Array.isArray(data.detail) ? data.detail.map(d => d.msg).join('; ') : data.detail
  return new ApiError(detail || res.statusText, { status: res.status })
}

async function request(path, options) {
  const res = await send(path, options)
  if (!res.ok) throw await failure(res)
  return res.json()
}

// Audio endpoints: returns an object URL (revoke it when done)
async function requestAudio(path, body) {
  const res = await send(path, { method: 'POST', body })
  if (!res.ok) throw await failure(res)
  return URL.createObjectURL(await res.blob())
}

export function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1] || '')
    reader.onerror = () => reject(new ApiError(`Couldn't read ${file.name || 'the recording'}`))
    reader.readAsDataURL(file)
  })
}

const pid = (id) => encodeURIComponent(id)
// The uploaded file behind a memory: a voice note to play, a photo to see
export const originalUrl = (id, filename) => `${API}/personas/${pid(id)}/uploads/${encodeURIComponent(filename)}/original`

export const api = {
  health: () => request('/health'),
  chat: (body) => request('/chat', { method: 'POST', body }),
  personas: () => request('/personas'),
  persona: (id) => request(`/personas/${pid(id)}`),
  createPersona: (body) => request('/personas', { method: 'POST', body }),
  uploadDocument: async (id, file, authoredBy) => request(`/personas/${pid(id)}/documents`, {
    method: 'POST',
    body: { filename: file.name, content_base64: await fileToBase64(file), authored_by: authoredBy },
  }),
  // Background upload with progress: onProgress(fraction, message); resolves like uploadDocument
  uploadDocumentWithProgress: async (id, file, authoredBy, onProgress) => {
    const { job_id: jobId } = await request(`/personas/${pid(id)}/documents/async`, {
      method: 'POST',
      body: { filename: file.name, content_base64: await fileToBase64(file), authored_by: authoredBy },
    })
    for (;;) {
      await new Promise(r => setTimeout(r, 400))
      const job = await request(`/jobs/${jobId}`)
      onProgress?.(job.progress, job.message)
      if (job.status === 'done') return job.result
      if (job.status === 'failed') throw new ApiError(job.error || 'Upload failed', { status: 400 })
    }
  },
  answerInterview: (id, body) => request(`/personas/${pid(id)}/interview`, { method: 'POST', body }),
  buildPersona: (id) => request(`/personas/${pid(id)}/build`, { method: 'POST' }),
  deletePersona: (id) => request(`/personas/${pid(id)}`, { method: 'DELETE' }),
  interviewQuestions: () => request('/interview/questions'),
  // consent + cloud: both boxes on the Create page's voice step were ticked
  // language: the consent statement was shown, and is recorded, in it
  addVoice: async (id, wav, language = 'en') => request(`/personas/${pid(id)}/voice`, {
    method: 'POST', body: { content_base64: await fileToBase64(wav), consent: true, cloud: true, language },
  }),
  consentText: (lang) => request(`/consent-text?lang=${encodeURIComponent(lang)}`),
  voiceStatus: () => request('/voice/status'),
  removeVoice: (id) => request(`/personas/${pid(id)}/voice`, { method: 'DELETE' }),
  speak: (persona, text) => requestAudio('/speak', { persona, text }),
  demoVoice: (text) => requestAudio('/voice/demo', { text }),
  // Clone-voice page (services/voice_sandbox.py): consented, tracked, deletable
  sandboxVoices: () => request('/voice/sandbox'),
  sandboxClone: async (name, wav) => request('/voice/sandbox', {
    method: 'POST', body: { name, content_base64: await fileToBase64(wav), consent: true, cloud: true },
  }),
  sandboxDelete: (voiceId) => request(`/voice/sandbox/${pid(voiceId)}`, { method: 'DELETE' }),
  sandboxSpeak: (text, voiceId) => requestAudio('/voice/sandbox/speak', { text, voice_id: voiceId }),
  // Access code or accounts (services/access.py)
  authStatus: () => request('/auth/status'),
  login: (code, user) => request('/auth/login', { method: 'POST', body: { code, user: user || null } }),
  logout: () => request('/auth/logout', { method: 'POST' }),

  // Streaming chat (/chat/stream): onToken(text) for each piece of the draft;
  // resolves with the final /chat response
  chatStream: async (body, onToken, signal) => {
    const res = await send('/chat/stream', { method: 'POST', body, signal })
    if (!res.ok) throw await failure(res)
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let cut
      while ((cut = buffer.indexOf('\n\n')) >= 0) {
        const block = buffer.slice(0, cut)
        buffer = buffer.slice(cut + 2)
        const event = /^event: (.*)$/m.exec(block)?.[1]
        const data = JSON.parse(/^data: (.*)$/m.exec(block)?.[1] || 'null')
        if (event === 'token') onToken?.(data.text)
        else if (event === 'final') return data
        else if (event === 'error') throw new ApiError(data.detail, { status: data.status })
      }
    }
    throw new ApiError('The answer stream ended early', { status: 0 })
  },

  // Memory browser + citation context (services/memory_routes.py)
  memories: (id, params = {}) => request(`/personas/${pid(id)}/memories?${new URLSearchParams(params)}`),
  memory: (id, memoryId) => request(`/personas/${pid(id)}/memories/${pid(memoryId)}`),
  editMemory: (id, memoryId, text) => request(`/personas/${pid(id)}/memories/${pid(memoryId)}`, { method: 'PATCH', body: { text } }),
  deleteMemory: (id, memoryId) => request(`/personas/${pid(id)}/memories/${pid(memoryId)}`, { method: 'DELETE' }),
  neverQuote: (id, memoryId, never_quote) => request(`/personas/${pid(id)}/memories/${pid(memoryId)}/never-quote`,
    { method: 'PUT', body: { never_quote } }),
  // Memory history with undo (services/memory_history.py)
  memoryHistory: (id, memoryId) => request(`/personas/${pid(id)}/memories/${pid(memoryId)}/history`),
  restoreMemory: (id, memoryId, seq) => request(`/personas/${pid(id)}/memories/${pid(memoryId)}/restore`,
    { method: 'POST', body: { seq } }),
  history: (id) => request(`/personas/${pid(id)}/history`),
  // Consent that can change (services/consent.py)
  changeConsent: (id, action) => request(`/personas/${pid(id)}/consent`, { method: 'POST', body: { action } }),
  setOffLimits: (id, topics) => request(`/personas/${pid(id)}/off-limits`, { method: 'PUT', body: { topics } }),
  deleteDocument: (id, filename) => request(`/personas/${pid(id)}/documents/${pid(filename)}`, { method: 'DELETE' }),
  timeline: (id) => request(`/personas/${pid(id)}/timeline`),
  about: (id) => request(`/personas/${pid(id)}/about`),

  // Feedback, review queue, gaps, analytics (services/insights.py)
  feedback: (body) => request('/feedback', { method: 'POST', body }),
  reviewQueue: (persona, status = 'pending') => request(`/review?${new URLSearchParams({ ...(persona ? { persona } : {}), status })}`),
  approve: (feedbackId, answer) => request(`/review/${pid(feedbackId)}/approve`, { method: 'POST', body: answer ? { answer } : {} }),
  dismiss: (feedbackId) => request(`/review/${pid(feedbackId)}/dismiss`, { method: 'POST' }),
  gaps: (persona) => request(`/insights/gaps?persona=${pid(persona)}`),
  deleteHistory: (persona) => request(`/history${persona ? `?persona=${pid(persona)}` : ''}`, { method: 'DELETE' }),
  analytics: (persona, days = 30) => request(`/insights/analytics?${new URLSearchParams({ ...(persona ? { persona } : {}), days })}`),

  roundtable: (body) => request('/roundtable', { method: 'POST', body }),

  // Voice input (services/stt.py)
  transcribe: async (wav, language) => request('/transcribe', {
    method: 'POST', body: { content_base64: await fileToBase64(wav), language: language || null },
  }),
  // Adaptive interview follow-ups (services/followups.py)
  answerFollowup: (id, body) => request(`/personas/${pid(id)}/followup`, { method: 'POST', body }),

  // Encrypted .chronus backups (services/bundle.py); export returns a Blob
  exportModel: async (id, password) => {
    const res = await send(`/personas/${pid(id)}/export`, { method: 'POST', body: { password } })
    if (!res.ok) throw await failure(res)
    return res.blob()
  },
  importModel: async (file, password) => request('/personas/import', {
    method: 'POST', body: { content_base64: await fileToBase64(file), password },
  }),
}

// Save a Blob as a file download
export function download(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = Object.assign(document.createElement('a'), { href: url, download: filename })
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

// Accepted by the backend (services/personas.py UPLOAD_TYPES)
// Photos and scans of letters are read on the server's computer (services/originals.py)
export const UPLOAD_ACCEPT = '.txt,.md,.pdf,.docx,.csv,.json,.jpg,.jpeg,.png,.webp'
// Voice notes, when the server can transcribe locally (services/stt.py)
export const AUDIO_ACCEPT = '.wav,.mp3,.m4a,.ogg,.webm,.flac,.aac'
export const MAX_UPLOAD_MB = 10
