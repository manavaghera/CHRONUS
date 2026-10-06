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
  answerInterview: (id, body) => request(`/personas/${pid(id)}/interview`, { method: 'POST', body }),
  buildPersona: (id) => request(`/personas/${pid(id)}/build`, { method: 'POST' }),
  deletePersona: (id) => request(`/personas/${pid(id)}`, { method: 'DELETE' }),
  interviewQuestions: () => request('/interview/questions'),
  // consent + cloud: both boxes on the Create page's voice step were ticked
  addVoice: async (id, wav) => request(`/personas/${pid(id)}/voice`, {
    method: 'POST', body: { content_base64: await fileToBase64(wav), consent: true, cloud: true },
  }),
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
  // Access code (services/access.py)
  authStatus: () => request('/auth/status'),
  login: (code) => request('/auth/login', { method: 'POST', body: { code } }),
  logout: () => request('/auth/logout', { method: 'POST' }),
}

// Accepted by the backend (services/personas.py UPLOAD_TYPES)
export const UPLOAD_ACCEPT = '.txt,.md,.pdf,.docx,.csv,.json'
export const MAX_UPLOAD_MB = 10
