import { useEffect, useState } from 'react'
import { api } from '../api'
import { navigate } from '../router'
import { Emblem } from '../components/Emblems'
import { Sources } from '../components/ChatPanel'
import AnswerText from '../components/chat/AnswerText'
import SourceViewer from '../components/chat/SourceViewer'
import { useT } from '../i18n'

const MAX_SEATS = 4
// Questions stay in English, like the archives they search
const IDEAS = ['What makes a life well lived?', 'How should we face failure?', 'What is the purpose of work?', 'What do you think about the future?']

function Seat({ entry, onOpen, reply }) {
  const t = useT()
  return (
    <article className={`rt-card${entry.fallback ? ' is-quiet' : ''}`}>
      <header className="rt-head">
        <span className="model-emblem"><Emblem id={entry.persona} name={entry.name} /></span>
        <div>
          <strong>{entry.name}</strong>
          {reply && <span className="rt-reply-to">{t('rt.replyingTo', { name: entry.replying_to_name })}</span>}
        </div>
      </header>
      <p className="rt-answer"><AnswerText text={entry.response} sources={entry.sources} onCite={(i) => onOpen(entry, i)} /></p>
      <div className="demo-msg-source">{entry.notice || `${t.label('mode', ['natural', 'fallback'].includes(entry.mode) ? entry.mode : 'mix_method')} · ${t('conf.label', { level: t.label('conf', entry.confidence) })}`}</div>
      <Sources sources={entry.sources} onOpen={(i) => onOpen(entry, i)} personaId={entry.persona} />
    </article>
  )
}

export default function RoundtablePage({ id }) {
  const t = useT()
  const [personas, setPersonas] = useState([])
  const [seats, setSeats] = useState(id ? [id] : [])
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState('mix_method')
  const [respond, setRespond] = useState(true)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [viewer, setViewer] = useState(null)

  useEffect(() => { api.personas().then(list => setPersonas(list.filter(p => p.status === 'ready'))).catch(e => setError(e.message)) }, [])

  const toggle = (pid) => setSeats(s => (s.includes(pid) ? s.filter(x => x !== pid) : s.length < MAX_SEATS ? [...s, pid] : s))
  const allAi = seats.every(pid => personas.find(p => p.id === pid)?.allow_cloud_llm)

  const ask = async (q = query) => {
    if (!q.trim() || seats.length < 2) return
    setQuery(q); setBusy(true); setError(''); setResult(null)
    try { setResult(await api.roundtable({ query: q.trim(), personas: seats, mode: allAi ? mode : 'mix_method', respond })) }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="page">
      <section className="page-hero page-hero--compact shell">
        <div className="eyebrow eyebrow--accent">{t('nav.roundtable')}</div>
        <h1 className="page-h1">{t('rt.title')}</h1>
        <p className="page-sub">{t('rt.sub')}</p>
      </section>
      <section className="shell page-section rt-layout">
        <div className="rt-seats" role="group" aria-label={t('rt.choose')}>
          {personas.map(p => (
            <button key={p.id} className={`rt-seat${seats.includes(p.id) ? ' is-on' : ''}`} aria-pressed={seats.includes(p.id)}
              disabled={!seats.includes(p.id) && seats.length >= MAX_SEATS} onClick={() => toggle(p.id)}>
              <span className="model-emblem"><Emblem id={p.id} name={p.name} /></span>{p.name}
            </button>
          ))}
        </div>
        <form className="rt-ask" onSubmit={e => { e.preventDefault(); ask() }}>
          <input className="demo-chat-input" value={query} maxLength={1000} onChange={e => setQuery(e.target.value)} placeholder={seats.length < 2 ? t('rt.pickTwo') : t('rt.askTable')} />
          <button className="pill-btn pill-btn--dark" disabled={busy || seats.length < 2 || !query.trim()}><span className="pill-inner">{busy ? t('rt.asking') : t('rt.ask')}</span></button>
        </form>
        <div className="rt-options">
          <label className="create-check"><input type="checkbox" checked={respond} onChange={e => setRespond(e.target.checked)} /><span>{t('rt.respond')}</span></label>
          <div className="seg" role="group" aria-label={t('common.answerMode')}>
            <button className={mode === 'mix_method' || !allAi ? 'is-on' : ''} onClick={() => setMode('mix_method')}>{t('chat.quotesOnly')}</button>
            <button className={mode === 'natural' && allAi ? 'is-on' : ''} disabled={!allAi} title={allAi ? '' : t('rt.aiOff')} onClick={() => setMode('natural')}>{t('chat.aiVoice')}</button>
          </div>
          <div className="rt-ideas">{IDEAS.map(q => <button key={q} className="demo-quick-btn" disabled={busy || seats.length < 2} onClick={() => ask(q)}>{q}</button>)}</div>
        </div>
        {error && <div className="page-alert">{error}</div>}
        {result?.support && <div className="nudge"><p>{result.support}</p></div>}
        {result && !result.support && (
          <>
            <h2 className="page-h2">{t('rt.round1')}</h2>
            <div className="rt-grid">{result.answers.map(a => <Seat key={a.persona} entry={a} onOpen={(e, i) => setViewer({ persona: e.persona, source: e.sources[i], index: i })} />)}</div>
            {respond && (
              <>
                <h2 className="page-h2">{t('rt.round2')}</h2>
                {result.replies.length === 0 && <p className="page-note">{t('rt.noReplies')}</p>}
                <div className="rt-grid">{result.replies.map(r => <Seat key={`${r.persona}-${r.replying_to}`} reply entry={r} onOpen={(e, i) => setViewer({ persona: e.persona, source: e.sources[i], index: i })} />)}</div>
              </>
            )}
          </>
        )}
        <button className="page-link" onClick={() => navigate('/models')}>{t('rt.browseAll')}</button>
      </section>
      {viewer?.source && <SourceViewer personaId={viewer.persona} source={viewer.source} index={viewer.index} onClose={() => setViewer(null)} />}
    </div>
  )
}
