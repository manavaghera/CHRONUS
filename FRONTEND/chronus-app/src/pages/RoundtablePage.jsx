import { useEffect, useState } from 'react'
import { api } from '../api'
import { useT } from '../i18n'
import { FIGURES, initials } from '../lib/data'
import { SplitWords } from '../lib/motion'
import Icon from '../lib/Icon'
import AnswerText from '../chat/AnswerText'
import SourceViewer from '../chat/SourceViewer'
import { LEVELS, MODES } from '../chat/Conversation'

const MAX = 4
// Questions stay in English, like the archives they search
const IDEAS = ['What makes a life well lived?', 'How should we face failure?', 'What is the purpose of work?', 'What do you think about the future?']
const mono = (p) => FIGURES[p.id]?.mono || initials(p.name)

// Seats placed around a circle, the table in the middle
function Table({ seats, personas, speaking, t }) {
  return (
    <div className={`rtable${speaking ? ' is-talking' : ''}`} aria-hidden="true">
      <div className="rt-ring" />
      <div className="rt-core"><Icon name="logo" size={30} /><span className="lab">{t('{n} / {max} seats', { n: seats.length, max: MAX })}</span></div>
      {Array.from({ length: MAX }, (_, i) => {
        const p = personas.find(x => x.id === seats[i])
        const a = ((-90 + i * 90) * Math.PI) / 180
        return (
          <span key={i} className={`rt-seat${p ? ' is-on' : ''}`} style={{ left: `${50 + 42 * Math.cos(a)}%`, top: `${50 + 42 * Math.sin(a)}%`, animationDelay: `${i * 0.35}s` }}>
            {p ? mono(p) : '+'}
          </span>
        )
      })}
    </div>
  )
}

function Answer({ entry, reply, onOpen }) {
  const t = useT()
  const mode = entry.mode === 'natural' ? 'natural' : entry.mode === 'fallback' ? 'fallback' : 'mix_method'
  return (
    <article className={`card rt-ans${entry.fallback ? ' is-quiet' : ''}`}>
      <div className="row gap12">
        <span className="av av-sm">{FIGURES[entry.persona]?.mono || initials(entry.name)}</span>
        <div className="col"><b>{entry.name}</b>{reply && <span className="lab">{t('replying to {name}', { name: entry.replying_to_name })}</span>}</div>
      </div>
      <p className={`rt-text${entry.mode === 'natural' ? '' : ' is-quote'}`} lang="en"><AnswerText text={entry.response} sources={entry.sources} onCite={(i) => onOpen(entry, i)} /></p>
      <span className="lab">{entry.notice || `${t(MODES[mode])} · ${t('{level} confidence', { level: t(LEVELS[entry.confidence] || entry.confidence) })}`}</span>
      {entry.sources?.length > 0 && (
        <div className="row wrap-row gap8">{entry.sources.map((s, i) => (
          <button key={i} type="button" className="mact" onClick={() => onOpen(entry, i)}><span className="cite" style={{ margin: 0 }}>{i + 1}</span><span className="ell" style={{ maxWidth: 220 }} lang="en">{s.citation || s.source_file}</span></button>
        ))}</div>
      )}
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
  useEffect(() => { api.personas().then(l => setPersonas(l.filter(p => p.status === 'ready'))).catch(e => setError(e.message)) }, [])

  const toggle = (pid) => setSeats(s => (s.includes(pid) ? s.filter(x => x !== pid) : s.length < MAX ? [...s, pid] : s))
  const allAi = seats.length > 0 && seats.every(pid => personas.find(p => p.id === pid)?.allow_cloud_llm)
  const ask = async (q = query) => {
    if (!q.trim() || seats.length < 2) return
    setQuery(q); setBusy(true); setError(''); setResult(null)
    try { setResult(await api.roundtable({ query: q.trim(), personas: seats, mode: allAi ? mode : 'mix_method', respond })) }
    catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  const open = (entry, i) => setViewer({ persona: entry.persona, source: entry.sources[i], index: i })
  const groups = [[t('Your models'), personas.filter(p => p.kind === 'custom')], [t('Pretrained'), personas.filter(p => p.kind !== 'custom')]]

  return (
    <div className="page">
      <section className="page-hero">
        <div className="page-hero-bg" aria-hidden="true" />
        <div className="wrap"><div className="ph-grid">
          <div className="l">
            <nav className="crumbs" aria-label={t('Breadcrumb')}><a href="#/">{t('Home')}</a><span aria-hidden="true">/</span><span>{t('Roundtable')}</span></nav>
            <span className="over">{t('Roundtable')}</span>
            <SplitWords as="h1" className="h1 h1-sm" text={t('One question,')} em={t('several minds.')} />
            <p className="lede">{t('Seat two to four models and ask them the same thing. Each answers only from its own archive; in the second round each responds to another, still in its own recorded words, or says it has nothing on that.')}</p>
          </div>
          <div className="r"><Table seats={seats} personas={personas} speaking={busy} t={t} /></div>
        </div></div>
      </section>
      <section className="sec" style={{ paddingTop: 8 }}>
        <div className="wrap col gap16">
          {groups.filter(([, l]) => l.length).map(([label, list]) => (
            <div key={label} className="col gap10">
              <span className="lab">{label}</span>
              <div className="chips" role="group" aria-label={label}>
                {list.map(p => (
                  <button key={p.id} type="button" className="chip seat-chip" aria-pressed={seats.includes(p.id)} disabled={!seats.includes(p.id) && seats.length >= MAX} onClick={() => toggle(p.id)}>
                    <span className="av av-xs">{mono(p)}</span>{p.name}
                  </button>
                ))}
              </div>
            </div>
          ))}
          <form className="rt-ask" onSubmit={e => { e.preventDefault(); ask() }}>
            <label className="sr-only" htmlFor="rt-q">{t('Question for the table')}</label>
            <input id="rt-q" className="field" maxLength={1000} autoComplete="off" value={query} onChange={e => setQuery(e.target.value)} placeholder={seats.length < 2 ? t('Seat at least two models first') : t('Ask the table…')} />
            <button className="btn btn-a" disabled={busy || seats.length < 2 || !query.trim()}>{busy ? t('Asking…') : t('Ask')}<Icon name="arrow" /></button>
          </form>
          <div className="row wrap-row gap12">
            <button type="button" className="switch inline" role="switch" aria-checked={respond} onClick={() => setRespond(r => !r)}><span className="tr" /><span className="t1">{t('Let them respond to each other')}</span></button>
            <div className="seg" role="group" aria-label={t('Answer mode')}>
              <button type="button" aria-pressed={mode === 'mix_method' || !allAi} onClick={() => setMode('mix_method')}>{t('Quotes only')}</button>
              <button type="button" aria-pressed={mode === 'natural' && allAi} disabled={!allAi} title={allAi ? '' : t('A seated model has the AI voice turned off')} onClick={() => setMode('natural')}>{t('AI voice')}</button>
            </div>
          </div>
          <div className="row wrap-row gap8">{IDEAS.map(q => <button key={q} type="button" className="chip" lang="en" disabled={busy || seats.length < 2} onClick={() => ask(q)}>{q}</button>)}</div>
          {error && <div className="alert" role="alert">{error}</div>}
          {busy && <div className="row gap12 small"><span className="spinner" />{t('Each model is searching its own archive…')}</div>}
          {result?.support && <div className="nudge"><p>{result.support}</p></div>}
          {result && !result.support && (
            <>
              <h2 className="h3" style={{ marginTop: 16 }}>{t('Round one')}</h2>
              <div className="rt-grid">{result.answers.map(a => <Answer key={a.persona} entry={a} onOpen={open} />)}</div>
              {respond && <>
                <h2 className="h3" style={{ marginTop: 16 }}>{t('Round two · replies')}</h2>
                {!result.replies.length && <p className="small">{t('No replies: nobody had a first answer to respond to.')}</p>}
                <div className="rt-grid">{result.replies.map(r => <Answer key={`${r.persona}-${r.replying_to}`} reply entry={r} onOpen={open} />)}</div>
              </>}
            </>
          )}
        </div>
      </section>
      {viewer?.source && <SourceViewer personaId={viewer.persona} source={viewer.source} index={viewer.index} onClose={() => setViewer(null)} />}
    </div>
  )
}
