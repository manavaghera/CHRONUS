// Client for the CHRONUS backend (CHRONUS/api_server.py). In development Vite
// proxies /api to it (vite.config.js); the production build is served by the
// backend itself (http://localhost:8001), so its API is on the same origin.
// Set VITE_API_BASE to call a backend somewhere else.
export const API = import.meta.env.VITE_API_BASE ?? (import.meta.env.DEV ? '/api' : '')

export const OFFLINE_MSG = "Can't reach the CHRONUS server. Start it with CHRONUS\\start_server.bat (port 8001), then try again."

export class ApiError extends Error {
  constructor(message, { status = 0, offline = false } = {}) {
    super(message)
    this.status = status
    this.offline = offline
  }
}

async function request(path, { method = 'GET', body } = {}) {
  let res
  try {
    res = await fetch(`${API}${path}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(OFFLINE_MSG, { offline: true })
  }
  let data = null
  try { data = await res.json() } catch { /* not JSON: proxy couldn't reach the backend */ }
  if (!res.ok) {
    if (!data) throw new ApiError(OFFLINE_MSG, { status: res.status, offline: true })
    const detail = Array.isArray(data.detail) ? data.detail.map(d => d.msg).join('; ') : data.detail
    throw new ApiError(detail || res.statusText, { status: res.status })
  }
  return data
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result).split(',')[1] || '')
    reader.onerror = () => reject(new ApiError(`Couldn't read ${file.name}`))
    reader.readAsDataURL(file)
  })
}

export const api = {
  health: () => request('/health'),
  chat: (body) => request('/chat', { method: 'POST', body }),
  personas: () => request('/personas'),
  persona: (id) => request(`/personas/${encodeURIComponent(id)}`),
  createPersona: (body) => request('/personas', { method: 'POST', body }),
  uploadDocument: async (id, file, authoredBy) => request(`/personas/${encodeURIComponent(id)}/documents`, {
    method: 'POST',
    body: { filename: file.name, content_base64: await fileToBase64(file), authored_by: authoredBy },
  }),
  answerInterview: (id, body) => request(`/personas/${encodeURIComponent(id)}/interview`, { method: 'POST', body }),
  buildPersona: (id) => request(`/personas/${encodeURIComponent(id)}/build`, { method: 'POST' }),
  deletePersona: (id) => request(`/personas/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  interviewQuestions: () => request('/interview/questions'),
  // consent + cloud: both boxes on the Create page's voice step were ticked
  addVoice: async (id, file) => request(`/personas/${encodeURIComponent(id)}/voice`, {
    method: 'POST', body: { content_base64: await fileToBase64(file), consent: true, cloud: true },
  }),
  voiceStatus: () => request('/voice/status'),
  removeVoice: (id) => request(`/personas/${encodeURIComponent(id)}/voice`, { method: 'DELETE' }),
  // Returns an object URL for the spoken answer (a .wav blob)
  speak: async (persona, text) => {
    let res
    try {
      res = await fetch(`${API}/speak`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ persona, text }) })
    } catch {
      throw new ApiError(OFFLINE_MSG, { offline: true })
    }
    if (!res.ok) {
      let detail = res.statusText
      try { detail = (await res.json()).detail || detail } catch { /* not JSON */ }
      throw new ApiError(detail, { status: res.status })
    }
    return URL.createObjectURL(await res.blob())
  },
  demoVoice: async (text) => {
    let res
    try {
      res = await fetch(`${API}/voice/demo`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) })
    } catch {
      throw new ApiError(OFFLINE_MSG, { offline: true })
    }
    if (!res.ok) {
      let detail = res.statusText
      try { detail = (await res.json()).detail || detail } catch { /* not JSON */ }
      throw new ApiError(detail, { status: res.status })
    }
    return URL.createObjectURL(await res.blob())
  },
  quickClone: async (file) => {
    const formData = new FormData()
    formData.append('audio', file)
    let res
    try {
      res = await fetch(`${API}/voice/quick-clone`, { method: 'POST', body: formData })
    } catch {
      throw new ApiError(OFFLINE_MSG, { offline: true })
    }
    if (!res.ok) {
      let detail = res.statusText
      try { detail = (await res.json()).detail || detail } catch { /* not JSON */ }
      throw new ApiError(detail, { status: res.status })
    }
    return (await res.json()).voice_id
  },
  quickSpeak: async (text, voice_id) => {
    let res
    try {
      res = await fetch(`${API}/voice/quick-speak`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice_id })
      })
    } catch {
      throw new ApiError(OFFLINE_MSG, { offline: true })
    }
    if (!res.ok) {
      let detail = res.statusText
      try { detail = (await res.json()).detail || detail } catch { /* not JSON */ }
      throw new ApiError(detail, { status: res.status })
    }
    return URL.createObjectURL(await res.blob())
  },
}

// Accepted by the backend (services/personas.py UPLOAD_TYPES)
export const UPLOAD_ACCEPT = '.txt,.md,.pdf,.docx,.csv,.json'
export const MAX_UPLOAD_MB = 10
