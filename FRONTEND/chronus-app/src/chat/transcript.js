// Conversation history (kept in this browser only) and export.
import { plain } from './AnswerText'

const KEY = (personaId) => `chronus_chat_${personaId}`
const MAX_SAVED = 100

export function loadHistory(personaId) {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY(personaId)) || 'null')
    return Array.isArray(saved) ? saved : null
  } catch { return null }
}

export function saveHistory(personaId, msgs) {
  try {
    const keep = msgs.filter(m => !m.draft && !m.error).slice(-MAX_SAVED)
    localStorage.setItem(KEY(personaId), JSON.stringify(keep))
  } catch { /* storage full or blocked: history just isn't kept */ }
}

export function clearHistory(personaId) {
  try { localStorage.removeItem(KEY(personaId)) } catch { /* blocked */ }
}

export function toMarkdown(persona, msgs) {
  const lines = [`# Conversation with ${persona.name} (CHRONUS)`, '',
    `Exported ${new Date().toLocaleString()}. An AI simulation built from their recorded words; every answer lists its sources.`, '']
  for (const m of msgs) {
    if (m.type === 'user') { lines.push(`**You:** ${m.text}`, ''); continue }
    lines.push(`**${persona.name}:** ${plain(m.text)}`)
    if (m.meta) lines.push(`_${m.meta}_`)
    ;(m.sources || []).forEach((s, i) => lines.push(`${i + 1}. ${s.citation || s.source_file}${s.quote ? ` — "${s.quote}"` : ''}`))
    lines.push('')
  }
  return lines.join('\n')
}
