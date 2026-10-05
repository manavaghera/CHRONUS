// Client for the CHRONUS backend (CHRONUS/api_server.py). In development Vite
// proxies /api to it (vite.config.js); set VITE_API_BASE to call it elsewhere.
export const API = import.meta.env.VITE_API_BASE || '/api'

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
}

// Accepted by the backend (services/personas.py UPLOAD_TYPES)
export const UPLOAD_ACCEPT = '.txt,.md,.pdf,.csv,.json'
export const MAX_UPLOAD_MB = 10
