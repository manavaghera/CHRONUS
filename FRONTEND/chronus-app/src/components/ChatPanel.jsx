import { useState, useRef, useEffect, useCallback } from 'react'
import { api } from '../api'

export const SPARK = <svg viewBox="0 0 48 48" fill="currentColor"><path d="M24 2c2.2 13.8 7.9 19.6 22 22-14.1 2.4-19.8 8.2-22 22-2.2-13.8-7.9-19.6-22-22 14.1-2.4 19.8-8.2 22-22Z"/></svg>

const MAX_HISTORY = 10

const MODE_LABELS = {
  natural: 'AI voice',
  mix_method: 'Verbatim quotes',
  mix_method_fallback: 'Verbatim quotes, AI unavailable',
  basic_info: 'Profile fact',
  fallback: 'Not enough evidence',
}

const DEFAULT_VOICE_LABELS = { first_person: 'own words', third_party: 'written by others', synthesized: 'synthesized' }

function Sources({ sources, voiceLabels }) {
  if (!sources?.length) return null
  return (
    <details className="demo-sources">
      <summary>Sources ({sources.length})</summary>
      {sources.map((s, i) => (
        <div key={i} className="demo-source">
          <div className="demo-msg-source">
            {s.citation || s.source_file}
            {s.voice && <span className={`demo-voice demo-voice--${s.voice}`}>{voiceLabels[s.voice] || s.voice}</span>}
            {s.distance != null && <span className="demo-match">match {Math.max(0, Math.round((1 - s.distance) * 100))}%</span>}
          </div>
          {s.quote && <div className="demo-msg-quote">{s.quote}</div>}
        </div>
      ))}
    </details>
  )
}

function Msg({ m, voiceLabels }) {
  return (
    <div className={`demo-msg demo-msg--${m.type}`}>
      <div className="demo-msg-avatar">{m.type === 'assistant' ? SPARK : 'You'}</div>
      <div>
        {/* Plain text child, not innerHTML: answers quote real documents */}
        <div className={`demo-msg-bubble demo-msg-bubble--text${m.error ? ' demo-msg-bubble--error' : ''}`}>{m.text}</div>
        {m.meta && <div className="demo-msg-source">{m.meta}</div>}
        <Sources sources={m.sources} voiceLabels={voiceLabels} />
      </div>
    </div>
  )
}

/**
 * Chat with one CHRONUS model.
 * persona: { id, name, memories?, allowAiVoice? } — allowAiVoice false hides
 * the cloud AI mode (custom models are local-first unless their creator opts in).
 */
export default function ChatPanel({ persona, greeting, quick = [], tall = false, voiceLabels = DEFAULT_VOICE_LABELS }) {
  const aiAllowed = persona.allowAiVoice !== false
  const [msgs, setMsgs] = useState(() => [{ type: 'assistant', text: greeting, meta: 'Model initialization' }])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const [mode, setMode] = useState(aiAllowed ? 'natural' : 'mix_method')
  const [status, setStatus] = useState({ online: null, memories: persona.memories || 0 })
  const history = useRef([])
  const bodyRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    const check = () => api.health()
      .then(() => !cancelled && setStatus(s => ({ ...s, online: true })))
      .catch(() => !cancelled && setStatus(s => ({ ...s, online: false })))
    check()
    const id = setInterval(check, 30000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight
  }, [msgs, typing])

  const send = useCallback(async (text) => {
    const query = text.trim()
    if (!query || typing) return
    setMsgs(p => [...p, { type: 'user', text: query }])
    setInput('')
    setTyping(true)
    try {
      const d = await api.chat({ query, mode, persona: persona.id, history: history.current.slice(-MAX_HISTORY) })
      setStatus({ online: true, memories: d.collection_size })
      setMsgs(p => [...p, {
        type: 'assistant',
        text: d.answer,
        meta: d.notice || `${MODE_LABELS[d.mode] || d.mode} · ${d.confidence} confidence`,
        sources: d.sources,
      }])
      history.current = [...history.current, { role: 'user', content: query }, { role: 'assistant', content: d.answer.slice(0, 2000) }].slice(-MAX_HISTORY)
    } catch (e) {
      setMsgs(p => [...p, { type: 'assistant', error: true, text: e.offline ? e.message : `Error: ${e.message}` }])
      if (e.offline) setStatus(s => ({ ...s, online: false }))
    } finally {
      setTyping(false)
    }
  }, [mode, typing, persona.id])

  return (
    <div className={`demo-chat${tall ? ' demo-chat--page' : ''}`}>
      <div className="demo-chat-header">
        <div className="demo-persona">
          <div className="demo-avatar">{SPARK}</div>
          <div>
            <div className="demo-name">{persona.name}</div>
            <div className="demo-id">chronus-model:{persona.id}{status.memories ? ` · ${status.memories.toLocaleString()} memories` : ''}</div>
          </div>
        </div>
        <div className={`demo-live-badge${status.online === false ? ' demo-live-badge--off' : ''}`}>
          <span className="demo-live-dot"/>{status.online === false ? 'Offline' : status.online ? 'Live' : 'Connecting'}
        </div>
      </div>
      <div className="demo-chat-body" ref={bodyRef}>
        {msgs.map((m, i) => <Msg key={i} m={m} voiceLabels={voiceLabels} />)}
        {typing && <div className="demo-msg demo-msg--assistant"><div className="demo-msg-avatar">{SPARK}</div><div className="demo-msg-bubble"><div className="demo-typing"><span/><span/><span/></div></div></div>}
      </div>
      <div className="demo-chat-modes" role="group" aria-label="Answer mode">
        <button className={`demo-quick-btn${mode === 'natural' ? ' demo-quick-btn--active' : ''}`} aria-pressed={mode === 'natural'}
          disabled={!aiAllowed} onClick={() => setMode('natural')}
          title={aiAllowed ? 'AI answers in their voice, built from their own words' : 'Off for this model: it would send excerpts to a cloud AI service'}>
          AI voice
        </button>
        <button className={`demo-quick-btn${mode === 'mix_method' ? ' demo-quick-btn--active' : ''}`} aria-pressed={mode === 'mix_method'}
          onClick={() => setMode('mix_method')} title="Only verbatim quotes from the sources, no AI writing">
          Quotes only
        </button>
      </div>
      {quick.length > 0 && (
        <div className="demo-quick-actions">
          {quick.map(q => <button key={q} className="demo-quick-btn" disabled={typing} onClick={() => send(q)}>{q}</button>)}
        </div>
      )}
      <div className="demo-chat-footer">
        <input className="demo-chat-input" value={input} maxLength={1000} onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send(input)} placeholder={`Ask ${persona.name.split(' ')[0]} anything...`} />
        <button className="demo-send-btn" disabled={!input.trim() || typing} onClick={() => send(input)} aria-label="Send"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4z"/></svg></button>
      </div>
    </div>
  )
}
