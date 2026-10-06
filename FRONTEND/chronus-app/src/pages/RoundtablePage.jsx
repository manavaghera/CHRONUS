import { useEffect, useState } from 'react'
import { api } from '../api'
import { navigate } from '../router'
import { Emblem } from '../components/Emblems'
import { Sources } from '../components/ChatPanel'
import AnswerText from '../components/chat/AnswerText'
import SourceViewer from '../components/chat/SourceViewer'

const MAX_SEATS = 4
const IDEAS = ['What makes a life well lived?', 'How should we face failure?', 'What is the purpose of work?', 'What do you think about the future?']

function Seat({ entry, onOpen, reply }) {
  return (
    <article className={`rt-card${entry.fallback ? ' is-quiet' : ''}`}>
      <header className="rt-head">
        <span className="model-emblem"><Emblem id={entry.persona} name={entry.name} /></span>
        <div>
          <strong>{entry.name}</strong>
          {reply && <span className="rt-reply-to">replying to {entry.replying_to_name}</span>}
        </div>
      </header>
      <p className="rt-answer"><AnswerText text={entry.response} sources={entry.sources} onCite={(i) => onOpen(entry, i)} /></p>
      <div className="demo-msg-source">{entry.notice || `${entry.mode === 'natural' ? 'AI voice' : entry.mode === 'fallback' ? 'Not enough evidence' : 'Verbatim quotes'} · ${entry.confidence} confidence`}</div>
      <Sources sources={entry.sources} onOpen={(i) => onOpen(entry, i)} />
    </article>
  )
}

export default function RoundtablePage({ id }) {
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
        <div className="eyebrow eyebrow--accent">Roundtable</div>
        <h1 className="page-h1">One question, several minds</h1>
        <p className="page-sub">Seat two to four models and ask them the same thing. Each answers only from its own archive; in the second round each one responds to another, still in its own recorded words, or says it has nothing on that.</p>
      </section>
      <section className="shell page-section rt-layout">
        <div className="rt-seats" role="group" aria-label="Choose models">
          {personas.map(p => (
            <button key={p.id} className={`rt-seat${seats.includes(p.id) ? ' is-on' : ''}`} aria-pressed={seats.includes(p.id)}
              disabled={!seats.includes(p.id) && seats.length >= MAX_SEATS} onClick={() => toggle(p.id)}>
              <span className="model-emblem"><Emblem id={p.id} name={p.name} /></span>{p.name}
            </button>
          ))}
        </div>
        <form className="rt-ask" onSubmit={e => { e.preventDefault(); ask() }}>
          <input className="demo-chat-input" value={query} maxLength={1000} onChange={e => setQuery(e.target.value)} placeholder={seats.length < 2 ? 'Pick at least two models first' : 'Ask the table…'} />
          <button className="pill-btn pill-btn--dark" disabled={busy || seats.length < 2 || !query.trim()}><span className="pill-inner">{busy ? 'Asking…' : 'Ask'}</span></button>
        </form>
        <div className="rt-options">
          <label className="create-check"><input type="checkbox" checked={respond} onChange={e => setRespond(e.target.checked)} /><span>Let them respond to each other</span></label>
          <div className="seg" role="group" aria-label="Answer mode">
            <button className={mode === 'mix_method' || !allAi ? 'is-on' : ''} onClick={() => setMode('mix_method')}>Quotes only</button>
            <button className={mode === 'natural' && allAi ? 'is-on' : ''} disabled={!allAi} title={allAi ? '' : 'A seated model has AI voice turned off'} onClick={() => setMode('natural')}>AI voice</button>
          </div>
          <div className="rt-ideas">{IDEAS.map(q => <button key={q} className="demo-quick-btn" disabled={busy || seats.length < 2} onClick={() => ask(q)}>{q}</button>)}</div>
        </div>
        {error && <div className="page-alert">{error}</div>}
        {result?.support && <div className="nudge"><p>{result.support}</p></div>}
        {result && !result.support && (
          <>
            <h2 className="page-h2">Round one</h2>
            <div className="rt-grid">{result.answers.map(a => <Seat key={a.persona} entry={a} onOpen={(e, i) => setViewer({ persona: e.persona, source: e.sources[i], index: i })} />)}</div>
            {respond && (
              <>
                <h2 className="page-h2">Round two: replies</h2>
                {result.replies.length === 0 && <p className="page-note">No replies: nobody had a first answer to respond to.</p>}
                <div className="rt-grid">{result.replies.map(r => <Seat key={`${r.persona}-${r.replying_to}`} reply entry={r} onOpen={(e, i) => setViewer({ persona: e.persona, source: e.sources[i], index: i })} />)}</div>
              </>
            )}
          </>
        )}
        <button className="page-link" onClick={() => navigate('/models')}>Browse all models →</button>
      </section>
      {viewer?.source && <SourceViewer personaId={viewer.persona} source={viewer.source} index={viewer.index} onClose={() => setViewer(null)} />}
    </div>
  )
}
