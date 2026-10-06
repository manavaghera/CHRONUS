import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, download } from '../api'
import { playExclusive, playUntilEnd, speakBrowser, stopCurrent } from '../audio'
import AnswerText, { plain } from './chat/AnswerText'
import Feedback from './chat/Feedback'
import SourceViewer from './chat/SourceViewer'
import TimeTravel from './chat/TimeTravel'
import { clearHistory, loadHistory, saveHistory, toMarkdown } from './chat/transcript'
import useVoiceInput from './chat/useVoiceInput'
import './chat/chat.css'

export const SPARK = <svg viewBox="0 0 48 48" fill="currentColor"><path d="M24 2c2.2 13.8 7.9 19.6 22 22-14.1 2.4-19.8 8.2-22 22-2.2-13.8-7.9-19.6-22-22 14.1-2.4 19.8-8.2 22-22Z"/></svg>

const MAX_HISTORY = 10
// Gentle break reminder for personal (and memorial) models
const NUDGE_AFTER_MS = 25 * 60 * 1000

const MODE_LABELS = {
  natural: 'AI voice',
  mix_method: 'Verbatim quotes',
  // The AI's draft was unreachable or not backed by the sources (grounding guard)
  mix_method_fallback: 'Verbatim quotes, AI answer not used',
  basic_info: 'Profile fact',
  fallback: 'Not enough evidence',
  support: 'Support information',
}

const LANGUAGES = [['auto', 'Same as question'], ['en', 'English'], ['hi', 'हिन्दी'], ['gu', 'ગુજરાતી'], ['mr', 'मराठी'],
  ['bn', 'বাংলা'], ['ta', 'தமிழ்'], ['te', 'తెలుగు'], ['ur', 'اردو'], ['es', 'Español'], ['fr', 'Français']]

const DEFAULT_VOICE_LABELS = { first_person: 'own words', third_party: 'written by others', synthesized: 'synthesized' }

export function Sources({ sources, voiceLabels = DEFAULT_VOICE_LABELS, onOpen, open }) {
  if (!sources?.length) return null
  return (
    <details className="demo-sources" open={open || undefined}>
      <summary>Sources ({sources.length})</summary>
      {sources.map((s, i) => (
        <div key={i} className="demo-source">
          <div className="demo-msg-source">
            <span className="src-num">{i + 1}</span>
            {s.citation || s.source_file}
            {s.voice && <span className={`demo-voice demo-voice--${s.voice}`}>{voiceLabels[s.voice] || s.voice}</span>}
            {s.distance != null && <span className="demo-match">match {Math.max(0, Math.round((1 - s.distance) * 100))}%</span>}
          </div>
          {s.quote && <div className="demo-msg-quote">{s.quote}</div>}
          {s.memory_id && <button className="src-open" onClick={() => onOpen(i)}>View in context</button>}
        </div>
      ))}
    </details>
  )
}

// Server voice: the consented cloned voice of a custom model, or for public
// figures a synthetic stand-in voice that is labelled as not theirs
function Listen({ personaId, text, standIn }) {
  const [state, setState] = useState('idle')
  const [error, setError] = useState('')
  const audioRef = useRef(null)
  useEffect(() => () => audioRef.current?.pause(), [])
  const toggle = async () => {
    if (state === 'playing') { audioRef.current?.pause(); setState('idle'); return }
    setState('loading'); setError('')
    try {
      const url = await api.speak(personaId, plain(text))
      const audio = new Audio(url)
      audioRef.current = audio
      audio.onended = audio.onpause = () => { URL.revokeObjectURL(url); setState('idle') }
      await playExclusive(audio, () => setState('idle'))
      setState('playing')
    } catch (e) { setState('idle'); setError(e.message) }
  }
  const label = standIn ? '▶ Listen (stand-in voice, not theirs)' : '▶ Listen in their voice'
  return (
    <div>
      <button className="demo-listen" disabled={state === 'loading'} onClick={toggle}
        title={standIn ? "A synthetic voice chosen for this model. It is not a recording or copy of the real person's voice." : undefined}>
        {state === 'loading' ? 'Generating voice…' : state === 'playing' ? '■ Stop' : label}
      </button>
      {error && <div className="demo-msg-source">{error}</div>}
    </div>
  )
}

// Any model: the browser's built-in speech voice. Clearly a computer voice,
// so it imitates nobody, and it needs no download or licence.
function ReadAloud({ text, lang }) {
  const [speaking, setSpeaking] = useState(false)
  if (typeof window === 'undefined' || !window.speechSynthesis) return null
  const toggle = async () => {
    if (speaking) { window.speechSynthesis.cancel(); setSpeaking(false); return }
    setSpeaking(true)
    await speakBrowser(plain(text), lang)
    setSpeaking(false)
  }
  return <button className="demo-listen" onClick={toggle}>{speaking ? '■ Stop' : '🔊 Read aloud'}</button>
}

function Msg({ m, voiceLabels, voice, personaId, onOpenSource }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try { await navigator.clipboard.writeText(plain(m.text)); setCopied(true); setTimeout(() => setCopied(false), 1500) } catch { /* no clipboard */ }
  }
  const bubble = ['demo-msg-bubble', 'demo-msg-bubble--text', m.error && 'demo-msg-bubble--error', m.draft && 'is-draft',
    m.mode === 'support' && 'is-support'].filter(Boolean).join(' ')
  return (
    <div className={`demo-msg demo-msg--${m.type}`}>
      <div className="demo-msg-avatar">{m.type === 'assistant' ? SPARK : 'You'}</div>
      <div className="demo-msg-main">
        {/* Plain text children, not innerHTML: answers quote real documents */}
        <div className={bubble} lang={m.language && m.language !== 'en' ? m.language : undefined}>
          {m.type === 'assistant' ? <AnswerText text={m.text} sources={m.sources} onCite={onOpenSource} /> : m.text}
          {m.draft && <span className="draft-caret" aria-hidden="true" />}
        </div>
        {m.helplines?.length > 0 && (
          <ul className="helplines">
            {m.helplines.map(h => <li key={h.region}><strong>{h.region}</strong> {h.name}: {h.contact}{h.hours && ` (${h.hours})`}</li>)}
          </ul>
        )}
        {m.original && (
          <details className="original-answer"><summary>Original (English)</summary><AnswerText text={m.original} sources={m.sources} onCite={onOpenSource} /></details>
        )}
        {m.meta && <div className="demo-msg-source">{m.meta}</div>}
        {m.why && m.why.threshold_match != null && (
          <details className="why">
            <summary>Why this confidence?</summary>
            {m.why.sources === 0
              ? <p>{m.why.best_match == null ? 'This model has no memories to search yet.' : `The closest memory matched ${m.why.best_match}%, and this model only answers above ${m.why.threshold_match}%. So instead of guessing, it says it doesn't know.`}</p>
              : <p>The best source matches the question {m.why.best_match}% (this model answers from {m.why.threshold_match}% up). {m.why.sources} source{m.why.sources === 1 ? '' : 's'} used, {m.why.own_words} in their own words. Higher matches and own words mean higher confidence.</p>}
          </details>
        )}
        <Sources sources={m.sources} voiceLabels={voiceLabels} onOpen={onOpenSource} />
        {m.sources && !m.error && !m.draft && (
          <div className="demo-voice-row">
            {voice ? <Listen personaId={voice.personaId} text={m.text} standIn={voice.standIn} /> : <ReadAloud text={m.text} lang={m.language} />}
            <button className="demo-listen" onClick={copy}>{copied ? '✓ Copied' : 'Copy'}</button>
            {m.mode !== 'support' && <Feedback entryId={m.id} personaId={personaId} />}
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * Chat with one CHRONUS model.
 * persona: { id, name, kind?, memorial?, memories?, allowAiVoice?, hasVoice?, standInVoice? } —
 * allowAiVoice false hides the cloud AI mode (custom models are local-first
 * unless their creator opts in); hasVoice / standInVoice add a Listen button.
 * persist: keep the conversation in this browser (the Chat page does; the
 * landing-page demo doesn't).
 */
export default function ChatPanel({ persona, greeting, quick = [], tall = false, voiceLabels = DEFAULT_VOICE_LABELS, persist = false }) {
  const aiAllowed = persona.allowAiVoice !== false
  const voice = useMemo(() => (persona.hasVoice || persona.standInVoice ? { personaId: persona.id, standIn: !persona.hasVoice } : null),
    [persona.hasVoice, persona.standInVoice, persona.id])
  const greetingMsg = { type: 'assistant', text: greeting, meta: 'Model initialization' }
  const [msgs, setMsgs] = useState(() => (persist && loadHistory(persona.id)) || [greetingMsg])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const [mode, setMode] = useState(aiAllowed ? 'natural' : 'mix_method')
  const [status, setStatus] = useState({ online: null, memories: persona.memories || 0 })
  const [years, setYears] = useState(null)
  const [panel, setPanel] = useState(null)  // 'time' | 'more' | null
  const [language, setLanguage] = useState('auto')
  const [length, setLength] = useState('normal')
  const [viewer, setViewer] = useState(null)  // { source, index }
  const [conversation, setConversation] = useState(false)
  const [nudge, setNudge] = useState(false)
  const [announce, setAnnounce] = useState('')
  const history = useRef(persist ? (loadHistory(persona.id) || []).filter(m => !m.meta?.startsWith('Model')).slice(-MAX_HISTORY)
    .map(m => ({ role: m.type === 'user' ? 'user' : 'assistant', content: plain(m.text).slice(0, 2000) })) : [])
  const bodyRef = useRef(null)
  const abortRef = useRef(null)
  const conversationRef = useRef(false)
  const voiceInput = useVoiceInput(language)

  useEffect(() => {
    let cancelled = false
    const check = () => api.health()
      .then(() => !cancelled && setStatus(s => ({ ...s, online: true })))
      .catch(() => !cancelled && setStatus(s => ({ ...s, online: false })))
    check()
    const id = setInterval(check, 30000)
    return () => { cancelled = true; clearInterval(id); abortRef.current?.abort(); stopCurrent() }
  }, [])

  useEffect(() => { if (persist) saveHistory(persona.id, msgs) }, [msgs, persist, persona.id])

  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight
  }, [msgs, typing])

  // Break reminder for personal models (wellbeing): after a long session
  useEffect(() => {
    if (persona.kind !== 'custom') return
    const id = setTimeout(() => setNudge(true), NUDGE_AFTER_MS)
    return () => clearTimeout(id)
  }, [persona.kind, nudge])

  const speakAnswer = useCallback(async (d) => {
    const text = plain(d.answer)
    if (voice) {
      try { await playUntilEnd(await api.speak(persona.id, text)); return } catch { /* fall back to the browser voice */ }
    }
    await speakBrowser(text, d.language)
  }, [voice, persona.id])

  const send = useCallback(async (text) => {
    const query = text.trim()
    if (!query || typing) return null
    setMsgs(p => [...p, { type: 'user', text: query }])
    setInput('')
    setTyping(true)
    const body = {
      query, mode, persona: persona.id, history: history.current.slice(-MAX_HISTORY),
      ...(years ? { year_from: years.from, year_to: years.to } : {}),
      ...(language !== 'auto' ? { language } : {}),
      ...(length !== 'normal' ? { length } : {}),
    }
    abortRef.current = new AbortController()
    try {
      let d
      if (mode === 'natural') {
        // Stream the AI voice's draft; the final answer replaces it
        let draft = ''
        d = await api.chatStream(body, (t) => {
          draft += t
          setTyping(false)
          setMsgs(p => {
            const last = p[p.length - 1]
            return last?.draft ? [...p.slice(0, -1), { ...last, text: draft }] : [...p, { type: 'assistant', text: draft, draft: true }]
          })
        }, abortRef.current.signal)
      } else {
        d = await api.chat(body)
      }
      setStatus({ online: true, memories: d.collection_size })
      const meta = d.mode === 'support' ? d.notice : [d.notice, `${MODE_LABELS[d.mode] || d.mode} · ${d.confidence} confidence`].filter(Boolean).join(' · ')
      setMsgs(p => [...p.filter(m => !m.draft), {
        type: 'assistant', text: d.answer, meta, sources: d.sources, id: d.id, mode: d.mode,
        helplines: d.helplines, language: d.language, original: d.original_answer || '', why: d.why,
      }])
      setAnnounce(`${persona.name}: ${plain(d.answer)}`)  // read out by screen readers once, not token by token
      history.current = [...history.current, { role: 'user', content: query }, { role: 'assistant', content: plain(d.answer).slice(0, 2000) }].slice(-MAX_HISTORY)
      return d
    } catch (e) {
      if (e.name === 'AbortError') return null
      setMsgs(p => [...p.filter(m => !m.draft), { type: 'assistant', error: true, text: e.offline ? e.message : `Error: ${e.message}` }])
      if (e.offline) setStatus(s => ({ ...s, online: false }))
      return null
    } finally {
      setTyping(false)
    }
  }, [mode, typing, persona.id, persona.name, years, language, length])

  // Hands-free conversation: listen -> ask -> speak the answer -> listen again
  const converse = useCallback(async () => {
    while (conversationRef.current) {
      let heard
      try { heard = await voiceInput.listen({ auto: true }) } catch { break }
      if (!conversationRef.current || !heard?.trim()) break
      const d = await send(heard)
      if (!d || d.mode === 'support' || !conversationRef.current) break
      await speakAnswer(d)
    }
    conversationRef.current = false
    setConversation(false)
  }, [voiceInput, send, speakAnswer])

  const toggleConversation = () => {
    if (conversation) { conversationRef.current = false; voiceInput.cancel(); stopCurrent(); window.speechSynthesis?.cancel(); setConversation(false); return }
    conversationRef.current = true
    setConversation(true)
    converse()
  }

  const dictate = async () => {
    if (voiceInput.state === 'listening') { voiceInput.stop(); return }
    try { const text = await voiceInput.listen(); if (text) setInput(i => (i ? `${i} ${text}` : text)) } catch { /* error shown below */ }
  }

  const exportMarkdown = () => {
    download(new Blob([toMarkdown(persona, msgs.filter(m => !m.draft))], { type: 'text/markdown' }),
      `chronus-${persona.id}-${new Date().toISOString().slice(0, 10)}.md`)
    setPanel(null)
  }
  const printChat = () => {
    setPanel(null)
    document.body.classList.add('printing-chat')
    const done = () => { document.body.classList.remove('printing-chat'); window.removeEventListener('afterprint', done) }
    window.addEventListener('afterprint', done)
    setTimeout(() => window.print(), 50)
  }
  const clear = () => {
    if (!window.confirm('Clear this conversation from this browser?')) return
    clearHistory(persona.id)
    history.current = []
    setMsgs([greetingMsg])
    setPanel(null)
  }

  const voiceNote = voiceInput.engine === 'browser' ? "Uses your browser's speech recognition, which may send audio to its provider" : 'Transcribed on this computer'

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

      <div className="chat-toolbar" role="toolbar" aria-label="Chat options">
        <button className={`chip-btn${years ? ' is-on' : ''}${panel === 'time' ? ' is-open' : ''}`} onClick={() => setPanel(p => (p === 'time' ? null : 'time'))} aria-expanded={panel === 'time'}>
          ⏳ {years ? `${years.from}${years.to !== years.from ? `–${years.to}` : ''}` : 'Time travel'}
        </button>
        <label className="chip-select" title={aiAllowed ? 'Answer language (translated by AI)' : 'Other languages need AI voice for this model'}>
          🌐
          <select value={language} onChange={e => setLanguage(e.target.value)} aria-label="Answer language">
            {LANGUAGES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label className="chip-select" title="How long answers should be">
          ¶
          <select value={length} onChange={e => setLength(e.target.value)} aria-label="Answer length">
            <option value="short">Short</option>
            <option value="normal">Normal length</option>
            <option value="detailed">Detailed</option>
          </select>
        </label>
        {voiceInput.engine && (
          <button className={`chip-btn${conversation ? ' is-on' : ''}`} onClick={toggleConversation} title={`Talk hands-free: it listens, answers aloud, then listens again. ${voiceNote}.`}>
            {conversation ? '■ End conversation' : '🎧 Voice conversation'}
          </button>
        )}
        <button className={`chip-btn${panel === 'more' ? ' is-open' : ''}`} onClick={() => setPanel(p => (p === 'more' ? null : 'more'))} aria-expanded={panel === 'more'}>⋯ Save</button>
      </div>
      {panel === 'time' && <TimeTravel personaId={persona.id} value={years} onChange={setYears} />}
      {panel === 'more' && (
        <div className="more-panel">
          <button className="demo-quick-btn" onClick={exportMarkdown}>Download as Markdown</button>
          <button className="demo-quick-btn" onClick={printChat}>Print / save as PDF</button>
          {persist && <button className="demo-quick-btn" onClick={clear}>Clear conversation</button>}
          <span className="page-note">{persist ? 'Conversations are kept in this browser only.' : 'This demo conversation is not saved.'}</span>
        </div>
      )}

      <div className="sr-only" aria-live="polite" aria-atomic="true">{announce}</div>
      <div className="demo-chat-body" ref={bodyRef} role="log" aria-live="off" aria-label={`Conversation with ${persona.name}`}>
        {nudge && (
          <div className="nudge" role="status">
            <p>You've been talking with {persona.name}'s {persona.memorial ? 'remembered words' : 'memories'} for a while. This is an archive, not the person. It's okay to take a break, or to talk to someone close to you.</p>
            <div><button className="demo-quick-btn" onClick={() => { window.location.hash = '' }}>Take a break</button><button className="demo-quick-btn" onClick={() => setNudge(false)}>Keep going</button></div>
          </div>
        )}
        {msgs.map((m, i) => <Msg key={i} m={m} voiceLabels={voiceLabels} voice={voice} personaId={persona.id} onOpenSource={(idx) => setViewer({ source: m.sources?.[idx], index: idx })} />)}
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
          onKeyDown={e => {
            // Enter while an IME (Hindi, Gujarati, Japanese...) is composing picks a word; don't send half of it
            if (e.key === 'Enter' && !e.nativeEvent.isComposing && e.keyCode !== 229) send(input)
          }} placeholder={voiceInput.state === 'listening' ? 'Listening…' : voiceInput.state === 'transcribing' ? 'Transcribing…' : `Ask ${persona.name.split(' ')[0]} anything...`} />
        {voiceInput.engine && !conversation && (
          <button className={`demo-mic-btn${voiceInput.state !== 'idle' ? ' is-on' : ''}`} onClick={dictate} disabled={voiceInput.state === 'transcribing'}
            aria-label={voiceInput.state === 'listening' ? 'Stop dictating' : 'Dictate a question'} title={voiceNote}>
            {voiceInput.state === 'listening' ? '■' : '🎙'}
          </button>
        )}
        <button className="demo-send-btn" disabled={!input.trim() || typing} onClick={() => send(input)} aria-label="Send"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4z"/></svg></button>
      </div>
      {voiceInput.error && <div className="chat-voice-error">{voiceInput.error}</div>}
      {viewer?.source && <SourceViewer personaId={persona.id} source={viewer.source} index={viewer.index} onClose={() => setViewer(null)} />}
    </div>
  )
}
