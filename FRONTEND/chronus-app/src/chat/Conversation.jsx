import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, download } from '../api'
import { playExclusive, playUntilEnd, speakBrowser, stopCurrent } from '../audio'
import { tx, useT } from '../i18n'
import { initials } from '../lib/data'
import Icon from '../lib/Icon'
import AnswerText, { plain } from './AnswerText'
import TimeTravel from './TimeTravel'
import { clearHistory, loadHistory, saveHistory, toMarkdown } from './transcript'
import useVoiceInput from './useVoiceInput'
import Feedback from './Feedback'
import { downloadQuoteCard } from './quoteCard'

const MAX_HISTORY = 10
const NUDGE_AFTER_MS = 25 * 60 * 1000
export const MODES = { natural: tx('AI voice'), mix_method: tx('Verbatim quotes'), mix_method_fallback: tx('Verbatim quotes, AI answer not used'), basic_info: tx('Profile fact'), fallback: tx('Not enough evidence'), support: tx('Support information'), spirit: tx('In their spirit') }
export const LEVELS = { high: tx('High'), medium: tx('Medium'), low: tx('Low') }
const LANGUAGES = [['auto', tx('Same as question')], ['en', 'English'], ['hi', 'हिन्दी'], ['gu', 'ગુજરાતી'], ['mr', 'मराठी'], ['bn', 'বাংলা'], ['ta', 'தமிழ்'], ['te', 'తెలుగు'], ['ur', 'اردو'], ['es', 'Español'], ['fr', 'Français']]

// An answer as conversation history, with the memories it cited, so a
// follow-up ("tell me more") searches from them and skips quotes already shown
function turnOf(text, sources) {
  const memory_ids = (sources || []).map(s => s.memory_id).filter(id => /^[A-Za-z0-9_.:-]{1,100}$/.test(id || '')).slice(0, 10)
  return { role: 'assistant', content: plain(text).slice(0, 2000), memory_ids }
}

// Their cloned voice (custom models) or a labelled stand-in (public figures)
function Listen({ personaId, text, standIn }) {
  const t = useT()
  const [state, setState] = useState('idle')
  const [error, setError] = useState('')
  const audio = useRef(null)
  useEffect(() => () => audio.current?.pause(), [])
  const toggle = async () => {
    if (state === 'playing') { audio.current?.pause(); setState('idle'); return }
    setState('loading'); setError('')
    try {
      const url = await api.speak(personaId, plain(text))
      const a = new Audio(url)
      audio.current = a
      a.onended = a.onpause = () => { URL.revokeObjectURL(url); setState('idle') }
      await playExclusive(a, () => setState('idle'))
      setState('playing')
    } catch (e) { setState('idle'); setError(e.message) }
  }
  return (
    <>
      <button type="button" className={`mact${state === 'playing' ? ' is-on' : ''}`} disabled={state === 'loading'} onClick={toggle}
        title={standIn ? t('A synthetic stand-in voice, not a copy of theirs') : t('Their consented cloned voice')}>
        <Icon name={state === 'playing' ? 'stop' : 'speaker'} size={14} />
        {state === 'loading' ? t('Making audio…') : state === 'playing' ? t('Stop') : standIn ? t('Listen (stand-in voice)') : t('Listen in their voice')}
      </button>
      {error && <span className="note">{error}</span>}
    </>
  )
}

function ReadAloud({ text, lang }) {
  const t = useT()
  const [on, setOn] = useState(false)
  if (!window.speechSynthesis) return null
  return (
    <button type="button" className={`mact${on ? ' is-on' : ''}`} onClick={async () => {
      if (on) { window.speechSynthesis.cancel(); setOn(false); return }
      setOn(true); await speakBrowser(plain(text), lang); setOn(false)
    }}><Icon name="speaker" size={14} />{on ? t('Stop') : t('Read aloud')}</button>
  )
}

function Msg({ m, persona, voice, onCite, onSources, focused }) {
  const t = useT()
  const [copied, setCopied] = useState(false)
  if (m.type === 'user') return <div className="msg msg--user"><div className="bub">{m.text}</div></div>
  const copy = async () => { try { await navigator.clipboard.writeText(plain(m.text)); setCopied(true); setTimeout(() => setCopied(false), 1500) } catch { /* blocked */ } }
  const meta = m.mode && m.mode !== 'support' && m.confidence ? [m.notice, `${t(MODES[m.mode] || m.mode)} · ${t('{level} confidence', { level: t(LEVELS[m.confidence] || m.confidence || '') })}`].filter(Boolean).join(' · ') : (m.notice || m.meta)
  const n = m.sources?.length || 0
  return (
    <div className={`msg msg--ai${focused ? ' is-focus' : ''}${m.error ? ' is-error' : ''}`}>
      <span className="av av-sm" aria-hidden="true">{initials(persona.name)}</span>
      <div className="msg-main">
        <div className={`ans${m.mode === 'mix_method' || m.mode === 'mix_method_fallback' ? ' is-quote' : ''}${m.mode === 'spirit' ? ' is-spirit' : ''}`} lang={m.greeting ? undefined : m.language || 'en'}>
          {m.greeting ? m.text : <AnswerText text={m.text || ''} sources={m.sources} onCite={(i) => onCite(m, i)} />}
          {m.draft && <span className="caret" aria-hidden="true" />}
        </div>
        {m.helplines?.length > 0 && <ul className="helplines">{m.helplines.map(h => <li key={h.region}><b>{h.region}</b> {h.name}: {h.contact}{h.hours && ` (${h.hours})`}</li>)}</ul>}
        {m.original && <details className="mdet"><summary>{t('Original (English)')}</summary><p lang="en"><AnswerText text={m.original} sources={m.sources} onCite={(i) => onCite(m, i)} /></p></details>}
        {meta && <div className="lab">{meta}</div>}
        {m.why && m.why.threshold_match != null && (
          <details className="mdet"><summary>{t('Why this confidence?')}</summary>
            <p>{m.why.sources === 0
              ? (m.why.best_match == null ? t('This model has no memories to search yet.') : t('The closest memory matched {best}%, below this model’s {threshold}% threshold, so it said it doesn’t know.', { best: m.why.best_match, threshold: m.why.threshold_match }))
              : t('The best source matches {best}% (this model answers from {threshold}% up). Sources used: {n}, {own} in their own words.', { best: m.why.best_match, threshold: m.why.threshold_match, n: m.why.sources, own: m.why.own_words })}</p>
          </details>
        )}
        {m.sources && !m.error && !m.draft && !m.greeting && (
          <div className="mactions">
            {n > 0 && <button type="button" className={`mact${focused ? ' is-on' : ''}`} onClick={() => onSources(m)}><Icon name="doc" size={14} />{n === 1 ? t('1 source') : t('{n} sources', { n })}</button>}
            {voice ? <Listen personaId={persona.id} text={m.text} standIn={voice.standIn} /> : <ReadAloud text={m.text} lang={m.language} />}
            <button type="button" className="mact" onClick={copy}><Icon name={copied ? 'check' : 'copy'} size={14} />{copied ? t('Copied') : t('Copy')}</button>
            {m.mode !== 'support' && m.mode !== 'fallback' && (
              <button type="button" className="mact" title={t('Download this answer as an image')}
                onClick={() => downloadQuoteCard({ text: m.text, name: persona.name, source: m.sources?.[0]?.citation || m.sources?.[0]?.source_file, dark: document.querySelector('.nav.is-dark') !== null })}>
                <Icon name="download" size={14} />{t('Quote card')}</button>
            )}
            {m.mode !== 'support' && <Feedback entryId={m.id} personaId={persona.id} />}
          </div>
        )}
      </div>
    </div>
  )
}

export default function Conversation({ persona, greeting, quick, onCite, onSources, focusedId }) {
  const t = useT()
  const aiAllowed = persona.allow_cloud_llm !== false
  const voice = useMemo(() => (persona.voice || persona.stand_in_voice ? { standIn: !persona.voice } : null), [persona.voice, persona.stand_in_voice])
  const greet = { type: 'assistant', greeting: true, text: greeting, id: 'greeting' }
  const [msgs, setMsgs] = useState(() => { const saved = loadHistory(persona.id); return saved?.length ? [greet, ...saved.filter(m => !m.greeting)] : [greet] })
  const [away, setAway] = useState(false)
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const [mode, setMode] = useState(aiAllowed ? 'natural' : 'mix_method')
  const [online, setOnline] = useState(null)
  const [years, setYears] = useState(null)
  const [panel, setPanel] = useState(null)
  const [language, setLanguage] = useState('auto')
  const [length, setLength] = useState('normal')
  // "In their spirit": when nothing they said covers a question, an inferred
  // answer, labelled as such (services/spirit.py). Off until asked for.
  const spiritAllowed = aiAllowed && !!persona.person_settings?.allow_spirit
  const [spirit, setSpirit] = useState(false)
  const [talking, setTalking] = useState(false)
  const [nudge, setNudge] = useState(false)
  const [announce, setAnnounce] = useState('')
  const history = useRef((loadHistory(persona.id) || []).filter(m => !m.greeting).slice(-MAX_HISTORY)
    .map(m => (m.type === 'user' ? { role: 'user', content: plain(m.text).slice(0, 2000) } : turnOf(m.text, m.sources))))
  const body = useRef(null)
  const abort = useRef(null)
  const talkingRef = useRef(false)
  const voiceInput = useVoiceInput(language)
  const first = persona.name.split(' ')[0]

  useEffect(() => {
    let cancelled = false
    const check = () => api.health().then(() => !cancelled && setOnline(true)).catch(() => !cancelled && setOnline(false))
    check()
    const id = setInterval(check, 30000)
    return () => { cancelled = true; clearInterval(id); abort.current?.abort(); stopCurrent() }
  }, [])
  useEffect(() => { saveHistory(persona.id, msgs.filter(m => !m.greeting)) }, [msgs, persona.id])
  // Follow new messages unless the reader has scrolled up to reread
  useEffect(() => { if (body.current && !away) body.current.scrollTop = body.current.scrollHeight }, [msgs, typing, away])
  const onScroll = () => { const b = body.current; if (b) setAway(b.scrollHeight - b.scrollTop - b.clientHeight > 140) }
  useEffect(() => {
    if (persona.kind !== 'custom') return
    const id = setTimeout(() => setNudge(true), NUDGE_AFTER_MS)
    return () => clearTimeout(id)
  }, [persona.kind, nudge])

  const send = useCallback(async (text) => {
    const query = text.trim()
    if (!query || typing) return null
    setMsgs(p => [...p, { type: 'user', text: query, id: `u${Date.now()}` }])
    setInput(''); setTyping(true)
    const req = {
      query, mode, persona: persona.id, history: history.current.slice(-MAX_HISTORY),
      ...(years ? { year_from: years.from, year_to: years.to } : {}),
      ...(language !== 'auto' ? { language } : {}),
      ...(length !== 'normal' ? { length } : {}),
      ...(spirit && spiritAllowed && mode === 'natural' ? { spirit: true } : {}),
    }
    abort.current = new AbortController()
    try {
      let d
      if (mode === 'natural') {
        let draft = ''
        d = await api.chatStream(req, (tok) => {
          draft += tok
          setTyping(false)
          setMsgs(p => { const last = p[p.length - 1]; return last?.draft ? [...p.slice(0, -1), { ...last, text: draft }] : [...p, { type: 'assistant', text: draft, draft: true, id: 'draft' }] })
        }, abort.current.signal)
      } else d = await api.chat(req)
      setOnline(true)
      const msg = { type: 'assistant', text: d.answer, notice: d.notice, confidence: d.confidence, sources: d.sources, id: d.id || `a${Date.now()}`, mode: d.mode, helplines: d.helplines, language: d.language, original: d.original_answer || '', why: d.why }
      setMsgs(p => [...p.filter(m => !m.draft), msg])
      if (d.sources?.length) onSources(msg)
      setAnnounce(`${persona.name}: ${plain(d.answer)}`)
      history.current = [...history.current, { role: 'user', content: query }, turnOf(d.answer, d.sources)].slice(-MAX_HISTORY)
      return d
    } catch (e) {
      if (e.name === 'AbortError') return null
      setMsgs(p => [...p.filter(m => !m.draft), { type: 'assistant', error: true, id: `e${Date.now()}`, text: e.offline ? e.message : t('Something went wrong: {message}', { message: e.message }) }])
      if (e.offline) setOnline(false)
      return null
    } finally { setTyping(false) }
  }, [mode, typing, persona.id, persona.name, years, language, length, spirit, spiritAllowed, onSources, t])

  const speak = useCallback(async (d) => {
    const text = plain(d.answer)
    if (voice) { try { await playUntilEnd(await api.speak(persona.id, text)); return } catch { /* browser voice instead */ } }
    await speakBrowser(text, d.language)
  }, [voice, persona.id])

  // Hands-free: listen, ask, speak the answer, listen again
  const converse = useCallback(async () => {
    while (talkingRef.current) {
      let heard
      try { heard = await voiceInput.listen({ auto: true }) } catch { break }
      if (!talkingRef.current || !heard?.trim()) break
      const d = await send(heard)
      if (!d || d.mode === 'support' || !talkingRef.current) break
      await speak(d)
    }
    talkingRef.current = false; setTalking(false)
  }, [voiceInput, send, speak])
  const toggleTalk = () => {
    if (talking) { talkingRef.current = false; voiceInput.cancel(); stopCurrent(); window.speechSynthesis?.cancel(); setTalking(false); return }
    talkingRef.current = true; setTalking(true); converse()
  }
  const dictate = async () => {
    if (voiceInput.state === 'listening') { voiceInput.stop(); return }
    try { const heard = await voiceInput.listen(); if (heard) setInput(i => (i ? `${i} ${heard}` : heard)) } catch { /* shown below */ }
  }

  const exportMd = () => { download(new Blob([toMarkdown(persona, msgs.filter(m => !m.draft && !m.greeting))], { type: 'text/markdown' }), `chronus-${persona.id}-${new Date().toISOString().slice(0, 10)}.md`); setPanel(null) }
  const clear = () => { if (!window.confirm(t('Clear this conversation from this browser?'))) return; clearHistory(persona.id); history.current = []; setMsgs([greet]); setPanel(null) }

  return (
    <div className="convo">
      <div className="convo-h">
        <div className="row gap12" style={{ minWidth: 0 }}>
          <span className="av">{initials(persona.name)}</span>
          <div className="col" style={{ minWidth: 0 }}>
            <b className="convo-name">{persona.name}</b>
            <span className="lab">{persona.kind === 'custom' ? t('Your model') : t('Pretrained')} · {t('{n} memories', { n: persona.memories.toLocaleString() })}{persona.voice ? ` · ${t('cloned voice')}` : ''}</span>
          </div>
        </div>
        <span className={`live${online === false ? ' is-off' : ''}`}><i />{online === false ? t('Offline') : online ? t('Live') : t('Connecting')}</span>
      </div>
      <div className="toolbar" role="toolbar" aria-label={t('Answer options')}>
        <div className="seg" role="group" aria-label={t('Answer mode')}>
          <button type="button" aria-pressed={mode === 'natural'} disabled={!aiAllowed} title={aiAllowed ? t('Rephrased in their voice, with citations') : t('This model was created without the AI voice')} onClick={() => setMode('natural')}>{t('AI voice')}</button>
          <button type="button" aria-pressed={mode !== 'natural'} onClick={() => setMode('mix_method')}>{t('Quotes only')}</button>
        </div>
        <button type="button" className={`tchip${years ? ' is-on' : ''}`} aria-expanded={panel === 'time'} onClick={() => setPanel(p => (p === 'time' ? null : 'time'))}><Icon name="clock" size={14} />{years ? `${years.from}${years.to !== years.from ? `–${years.to}` : ''}` : t('Time travel')}</button>
        <label className="tchip sel"><Icon name="globe" size={14} /><span className="sr-only">{t('Answer language')}</span>
          <select value={language} onChange={e => setLanguage(e.target.value)} title={aiAllowed ? t('Answer language') : t('Translation needs the AI voice')}>{LANGUAGES.map(([v, l]) => <option key={v} value={v}>{t(l)}</option>)}</select></label>
        <label className="tchip sel"><span className="sr-only">{t('Answer length')}</span>
          <select value={length} onChange={e => setLength(e.target.value)}><option value="short">{t('Short')}</option><option value="normal">{t('Normal')}</option><option value="detailed">{t('Detailed')}</option></select></label>
        {spiritAllowed && mode === 'natural' && (
          <button type="button" className={`tchip${spirit ? ' is-on' : ''}`} aria-pressed={spirit} onClick={() => setSpirit(s => !s)}
            title={t('When they never talked about something, answer the way they likely would, clearly labelled as inferred')}>
            <Icon name="sparkle" size={14} />{t('In their spirit')}</button>
        )}
        {voiceInput.engine && <button type="button" className={`tchip${talking ? ' is-on' : ''}`} onClick={toggleTalk}><Icon name="mic" size={14} />{talking ? t('End conversation') : t('Talk hands-free')}</button>}
        <button type="button" className="tchip" aria-expanded={panel === 'more'} aria-label={t('More options')} onClick={() => setPanel(p => (p === 'more' ? null : 'more'))}><Icon name="dots" size={16} /></button>
      </div>
      {panel === 'time' && <TimeTravel personaId={persona.id} value={years} onChange={setYears} />}
      {panel === 'more' && (
        <div className="more">
          <button type="button" className="btn btn-s btn-sm" onClick={exportMd}>{t('Download as Markdown')}</button>
          <button type="button" className="btn btn-s btn-sm" onClick={clear}>{t('Clear conversation')}</button>
          <span className="note">{t('Kept only in this browser.')}</span>
        </div>
      )}
      <div className="sr-only" aria-live="polite" aria-atomic="true">{announce}</div>
      {away && <button type="button" className="jump" onClick={() => setAway(false)}><Icon name="arrow" size={14} className="rot90" />{t('Latest')}</button>}
      <div className="convo-b" ref={body} role="log" aria-label={t('Conversation with {name}', { name: persona.name })} onScroll={onScroll}>
        {nudge && (
          <div className="nudge" role="status">
            <p>{persona.memorial ? t('You’ve been talking with {name} for a while. It might be a good moment to rest, or to share a memory with someone who knew them too.', { name: persona.name }) : t('You’ve been here a while. A short break can help.')}</p>
            <div className="row gap8"><a className="btn btn-s btn-sm" href="#/models">{t('Take a break')}</a><button type="button" className="btn btn-s btn-sm" onClick={() => setNudge(false)}>{t('Keep going')}</button></div>
          </div>
        )}
        {msgs.map((m, i) => <Msg key={m.id || i} m={m.greeting ? { ...m, text: greeting } : m} persona={persona} voice={voice} focused={focusedId && m.id === focusedId}
          onCite={(msg, idx) => onCite(msg.sources?.[idx], idx)} onSources={onSources} />)}
        {typing && <div className="msg msg--ai"><span className="av av-sm" aria-hidden="true">{initials(persona.name)}</span><div className="typing"><i /><i /><i /></div></div>}
      </div>
      {quick.length > 0 && msgs.length < 4 && (
        <div className="quick">{quick.map(q => <button key={q} type="button" className="chip" disabled={typing} onClick={() => send(q)} lang="en">{q}</button>)}</div>
      )}
      <form className="composer" onSubmit={e => { e.preventDefault(); send(input) }}>
        <label className="sr-only" htmlFor="chat-in">{t('Message {name}', { name: persona.name })}</label>
        <input id="chat-in" className="field" maxLength={1000} autoComplete="off" value={input} onChange={e => setInput(e.target.value)}
          placeholder={voiceInput.state === 'listening' ? t('Listening…') : voiceInput.state === 'transcribing' ? t('Transcribing…') : t('Ask {name} anything…', { name: first })}
          onKeyDown={e => { if (e.key === 'Enter' && (e.nativeEvent.isComposing || e.keyCode === 229)) e.preventDefault() }} />
        {voiceInput.engine && !talking && (
          <button type="button" className={`icbtn mic${voiceInput.state !== 'idle' ? ' is-on' : ''}`} onClick={dictate} disabled={voiceInput.state === 'transcribing'}
            aria-label={voiceInput.state === 'listening' ? t('Stop dictating') : t('Dictate')}><Icon name={voiceInput.state === 'listening' ? 'stop' : 'mic'} /></button>
        )}
        <button className="send" disabled={!input.trim() || typing} aria-label={t('Send')}><Icon name="up" size={20} /></button>
      </form>
      {voiceInput.error && <p className="note" style={{ padding: '0 16px 12px' }}>{voiceInput.error}</p>}
    </div>
  )
}
