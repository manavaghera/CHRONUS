import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { navigate } from '../router'
import { BarList, ColumnChart, StatTile } from '../components/charts'
import '../components/charts.css'

const MODE_NAMES = {
  natural: 'AI voice', mix_method: 'Verbatim quotes', mix_method_fallback: 'Quotes (AI answer not used)',
  basic_info: 'Profile fact', fallback: 'Not enough evidence', support: 'Support shown',
}
const REASONS = { wrong_attribution: 'Wrong source', not_their_words: 'Not their words', incorrect: 'Factually wrong', unhelpful: "Didn't answer", other: 'Other' }
const RANGES = [[7, 'Last 7 days'], [30, 'Last 30 days'], [90, 'Last 90 days']]

const pct = (x) => `${Math.round(x * 100)}%`
const secs = (ms) => (ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`)
const shortDate = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })

function Overview({ persona, days }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let cancelled = false
    api.analytics(persona, days).then(d => !cancelled && setData(d)).catch(e => !cancelled && setError(e.message))
    return () => { cancelled = true }
  }, [persona, days])
  if (error) return <div className="page-alert">{error}</div>
  if (!data) return <p className="page-note">Loading…</p>
  if (!data.total) return <p className="page-note">No questions asked yet{persona ? ' to this model' : ''}. Numbers appear here as people chat.</p>
  return (
    <div className={`insights-overview${data ? '' : ' is-loading'}`}>
      <div className="kpi-row">
        <StatTile label="Questions answered" value={data.total.toLocaleString()} sub="all time" />
        <StatTile label="Said “I don't know”" value={pct(data.refusal_rate)} sub={`${data.refused.toLocaleString()} questions`} />
        <StatTile label="Median grounding" value={data.grounding.median == null ? '–' : pct(data.grounding.median)} sub="answer words found in sources" />
        <StatTile label="Typical answer time" value={data.latency_ms.p50 == null ? '–' : secs(data.latency_ms.p50)}
          sub={data.latency_ms.p95 == null ? '' : `95% under ${secs(data.latency_ms.p95)}`} />
        <StatTile label="Feedback" value={`👍 ${data.feedback.up} · 👎 ${data.feedback.down}`} sub={`${data.feedback.pending} waiting for review`} />
      </div>
      <div className="insights-grid">
        <div className="create-card">
          <ColumnChart label={`Questions per day, ${RANGES.find(r => r[0] === days)?.[1].toLowerCase()}`}
            data={data.per_day.map(d => ({ label: d.date, short: shortDate(d.date), value: d.count, tip: shortDate(d.date) }))} />
        </div>
        <div className="create-card">
          <ColumnChart label="How grounded answers are (share of words found in their sources)"
            data={data.grounding.buckets.map(b => ({ label: `${pct(b.from)}–${pct(b.to)}`, value: b.count, tip: `answers ${pct(b.from)}–${pct(b.to)} grounded` }))} />
        </div>
        <div className="create-card">
          <BarList label="How questions were answered" items={Object.entries(data.by_mode).map(([k, v]) => ({ label: MODE_NAMES[k] || k, value: v }))} />
        </div>
        <div className="create-card">
          <BarList label="Confidence" items={['high', 'medium', 'low'].filter(k => data.by_confidence[k]).map(k => ({ label: k, value: data.by_confidence[k] }))} />
        </div>
        <div className="create-card insights-wide">
          <BarList label="Most asked" items={data.top_questions.map(q => ({ label: q.question, value: q.count }))} />
        </div>
      </div>
    </div>
  )
}

function Gaps({ persona, kind }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let cancelled = false
    setData(null)
    api.gaps(persona).then(d => !cancelled && setData(d)).catch(e => !cancelled && setError(e.message))
    return () => { cancelled = true }
  }, [persona])
  if (error) return <div className="page-alert">{error}</div>
  if (!data) return <p className="page-note">Loading…</p>
  if (!data.gaps.length) return <p className="page-note">Nothing unanswered yet. Questions the archive can't answer (or answers only with low confidence) collect here.</p>
  return (
    <>
      <p className="page-note">{data.unanswered} of {data.total_questions} questions couldn't be answered well. Similar questions are grouped.</p>
      <ul className="gap-list">
        {data.gaps.map(g => (
          <li key={g.question} className="create-card">
            <div className="gap-top"><strong>“{g.question}”</strong><span className="gap-count">asked {g.count}×</span></div>
            {g.examples.length > 0 && <p className="page-note">Also: {g.examples.map(e => `“${e}”`).join(', ')}</p>}
            {kind === 'custom' && (
              <div className="gap-fix">
                {g.suggestion && <span>Could be filled by interview {g.suggestion.id}: “{g.suggestion.question}”</span>}
                <button className="page-link" onClick={() => navigate(`/create/${persona}`)}>{g.suggestion ? 'Answer it' : 'Add a document'} →</button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </>
  )
}

function ReviewItem({ item, onDone, names }) {
  const [answer, setAnswer] = useState(item.answer)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const act = async (fn) => {
    setBusy(true); setError('')
    try { await fn(); onDone(item.id) } catch (e) { setError(e.message); setBusy(false) }
  }
  return (
    <li className="create-card review-item">
      <div className="gap-top">
        <span className={`review-rating review-rating--${item.rating}`}>{item.rating === 'up' ? '👍 Good answer' : `👎 ${REASONS[item.reason] || 'Problem'}`}</span>
        <span className="page-note">{names[item.persona] || item.persona} · {new Date(item.timestamp).toLocaleString()}</span>
      </div>
      <p><strong>Q:</strong> {item.question}</p>
      {item.can_approve ? (
        <label className="review-answer">
          <span>Answer (edit before approving if needed)</span>
          <textarea className="create-select" rows={4} maxLength={4000} value={answer} onChange={e => setAnswer(e.target.value)} />
        </label>
      ) : <p className="review-answer-text"><strong>A:</strong> {item.answer}</p>}
      {item.note && <p className="page-note">Note: {item.note}</p>}
      {error && <div className="page-alert">{error}</div>}
      <div className="model-actions">
        {item.can_approve && (
          <button className="pill-btn pill-btn--dark" disabled={busy} onClick={() => act(() => api.approve(item.id, answer.trim() !== item.answer ? answer.trim() : undefined))}
            title="Store this answer as a memory labelled “reviewed past answer” (never quoted as their own words)">
            <span className="pill-inner">Approve into memory</span>
          </button>
        )}
        <button className="pill-btn pill-btn--outline" disabled={busy} onClick={() => act(() => api.dismiss(item.id))}><span className="pill-inner">Dismiss</span></button>
      </div>
    </li>
  )
}

function Review({ persona, names }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let cancelled = false
    setItems(null)
    api.reviewQueue(persona || undefined).then(d => !cancelled && setItems(d)).catch(e => !cancelled && setError(e.message))
    return () => { cancelled = true }
  }, [persona])
  if (error) return <div className="page-alert">{error}</div>
  if (!items) return <p className="page-note">Loading…</p>
  if (!items.length) return <p className="page-note">Nothing waiting. 👍 and 👎 on answers land here for a person to review.</p>
  return (
    <>
      <p className="page-note">Approving a custom model's answer stores it as a memory labelled “reviewed past answer”, so it can help later answers but is never quoted as their own words. Pretrained models only learn from published sources, so their feedback can only be dismissed.</p>
      <ul className="gap-list">{items.map(i => <ReviewItem key={i.id} item={i} names={names} onDone={(id) => setItems(list => list.filter(x => x.id !== id))} />)}</ul>
    </>
  )
}

function DeleteHistory({ persona, name, onDeleted }) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  useEffect(() => { setConfirming(false); setMessage('') }, [persona])
  const run = async () => {
    setBusy(true)
    try {
      const r = await api.deleteHistory(persona || undefined)
      setMessage(`Deleted ${r.questions_deleted} question${r.questions_deleted === 1 ? '' : 's'} and ${r.feedback_deleted} feedback item${r.feedback_deleted === 1 ? '' : 's'}.`)
      onDeleted()
    } catch (e) { setMessage(e.message) }
    setBusy(false); setConfirming(false)
  }
  return (
    <div className="history-delete">
      {confirming ? (
        <>
          <span>Delete every question you asked {name || 'any model'}, and your feedback? This can't be undone.</span>
          <button className="pill-btn pill-btn--dark" disabled={busy} onClick={run}><span className="pill-inner">{busy ? 'Deleting…' : 'Delete'}</span></button>
          <button className="pill-btn pill-btn--outline" disabled={busy} onClick={() => setConfirming(false)}><span className="pill-inner">Cancel</span></button>
        </>
      ) : (
        <button className="page-link" onClick={() => { setConfirming(true); setMessage('') }}>Delete my question history{name ? ` with ${name}` : ''}</button>
      )}
      {message && <span className="page-note" role="status">{message}</span>}
    </div>
  )
}

export default function InsightsPage({ id }) {
  const [personas, setPersonas] = useState([])
  const [persona, setPersona] = useState(id || '')
  const [days, setDays] = useState(30)
  const [tab, setTab] = useState('overview')
  const [refresh, setRefresh] = useState(0)
  useEffect(() => { api.personas().then(setPersonas).catch(() => {}) }, [])
  useEffect(() => { setPersona(id || '') }, [id])
  const choose = useCallback((value) => { setPersona(value); navigate(value ? `/insights/${value}` : '/insights') }, [])
  const kind = personas.find(p => p.id === persona)?.kind
  const name = personas.find(p => p.id === persona)?.name

  return (
    <div className="page">
      <section className="page-hero page-hero--compact shell">
        <div className="eyebrow eyebrow--accent">Insights</div>
        <h1 className="page-h1">How the models are doing</h1>
        <p className="page-sub">What people ask, how well answers are grounded, what the archives can't answer yet, and feedback waiting for a person to review. Built from this server's Q&amp;A log, which keeps questions for 90 days unless the server is set otherwise.</p>
      </section>
      <section className="shell page-section insights-layout">
        <div className="insights-filters">
          <select className="create-select" value={persona} onChange={e => choose(e.target.value)} aria-label="Model">
            <option value="">All models</option>
            {personas.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          {tab === 'overview' && (
            <div className="seg" role="group" aria-label="Date range">
              {RANGES.map(([d, l]) => <button key={d} className={days === d ? 'is-on' : ''} aria-pressed={days === d} onClick={() => setDays(d)}>{l}</button>)}
            </div>
          )}
        </div>
        <div className="tabs" role="tablist">
          {[['overview', 'Overview'], ['gaps', 'Knowledge gaps'], ['review', 'Review queue']].map(([t, l]) => (
            <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? 'is-on' : ''} onClick={() => setTab(t)}>{l}</button>
          ))}
        </div>
        {tab === 'overview' && <Overview key={refresh} persona={persona} days={days} />}
        {tab === 'gaps' && (persona ? <Gaps key={refresh} persona={persona} kind={kind} /> : <p className="page-note">Choose a model above to see what its archive can't answer.</p>)}
        {tab === 'review' && <Review key={refresh} persona={persona} names={Object.fromEntries(personas.map(p => [p.id, p.name]))} />}
        <DeleteHistory persona={persona} name={name} onDeleted={() => setRefresh(n => n + 1)} />
      </section>
    </div>
  )
}
