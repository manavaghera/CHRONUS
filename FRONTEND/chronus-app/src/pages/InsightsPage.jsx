import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { navigate } from '../router'
import { BarList, ColumnChart, StatTile } from '../components/charts'
import { useT } from '../i18n'
import '../components/charts.css'

// Days; their names, and those of answer modes and feedback reasons, are in strings/
const RANGES = [7, 30, 90]

const pct = (x) => `${Math.round(x * 100)}%`
const secs = (ms) => (ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`)
const shortDate = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })

function Overview({ persona, days }) {
  const t = useT()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let cancelled = false
    api.analytics(persona, days).then(d => !cancelled && setData(d)).catch(e => !cancelled && setError(e.message))
    return () => { cancelled = true }
  }, [persona, days])
  if (error) return <div className="page-alert">{error}</div>
  if (!data) return <p className="page-note">{t('common.loading')}</p>
  if (!data.total) return <p className="page-note">{persona ? t('ins.noneModel') : t('ins.noneAll')}</p>
  return (
    <div className={`insights-overview${data ? '' : ' is-loading'}`}>
      <div className="kpi-row">
        <StatTile label={t('ins.answered')} value={data.total.toLocaleString()} sub={t('ins.allTime')} />
        <StatTile label={t('ins.idk')} value={pct(data.refusal_rate)} sub={t('ins.questions', { count: data.refused.toLocaleString() })} />
        <StatTile label={t('ins.grounding')} value={data.grounding.median == null ? '–' : pct(data.grounding.median)} sub={t('ins.groundingSub')} />
        <StatTile label={t('ins.time')} value={data.latency_ms.p50 == null ? '–' : secs(data.latency_ms.p50)}
          sub={data.latency_ms.p95 == null ? '' : t('ins.p95', { time: secs(data.latency_ms.p95) })} />
        <StatTile label={t('ins.feedback')} value={`👍 ${data.feedback.up} · 👎 ${data.feedback.down}`} sub={t('ins.waiting', { count: data.feedback.pending })} />
      </div>
      <div className="insights-grid">
        <div className="create-card">
          <ColumnChart label={t('ins.perDay', { range: t(`range.${days}`).toLowerCase() })}
            data={data.per_day.map(d => ({ label: d.date, short: shortDate(d.date), value: d.count, tip: shortDate(d.date) }))} />
        </div>
        <div className="create-card">
          <ColumnChart label={t('ins.groundedChart')}
            data={data.grounding.buckets.map(b => ({ label: `${pct(b.from)}–${pct(b.to)}`, value: b.count, tip: t('ins.groundedTip', { from: pct(b.from), to: pct(b.to) }) }))} />
        </div>
        <div className="create-card">
          <BarList label={t('ins.howAnswered')} items={Object.entries(data.by_mode).map(([k, v]) => ({ label: t.label('mode', k), value: v }))} />
        </div>
        <div className="create-card">
          <BarList label={t('ins.confidence')} items={['high', 'medium', 'low'].filter(k => data.by_confidence[k]).map(k => ({ label: t.label('conf', k), value: data.by_confidence[k] }))} />
        </div>
        <div className="create-card insights-wide">
          <BarList label={t('ins.mostAsked')} items={data.top_questions.map(q => ({ label: q.question, value: q.count }))} />
        </div>
      </div>
    </div>
  )
}

function Gaps({ persona, kind }) {
  const t = useT()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let cancelled = false
    setData(null)
    api.gaps(persona).then(d => !cancelled && setData(d)).catch(e => !cancelled && setError(e.message))
    return () => { cancelled = true }
  }, [persona])
  if (error) return <div className="page-alert">{error}</div>
  if (!data) return <p className="page-note">{t('common.loading')}</p>
  if (!data.gaps.length) return <p className="page-note">{t('gaps.none')}</p>
  return (
    <>
      <p className="page-note">{t('gaps.summary', { unanswered: data.unanswered, total: data.total_questions })}</p>
      <ul className="gap-list">
        {data.gaps.map(g => (
          <li key={g.question} className="create-card">
            <div className="gap-top"><strong>“{g.question}”</strong><span className="gap-count">{t('gaps.asked', { count: g.count })}</span></div>
            {g.examples.length > 0 && <p className="page-note">{t('gaps.also', { list: g.examples.map(e => `“${e}”`).join(', ') })}</p>}
            {kind === 'custom' && (
              <div className="gap-fix">
                {g.suggestion && <span>{t('gaps.couldFill', { id: g.suggestion.id, question: g.suggestion.question })}</span>}
                <button className="page-link" onClick={() => navigate(`/create/${persona}`)}>{g.suggestion ? t('gaps.answerIt') : t('gaps.addDoc')} →</button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </>
  )
}

function ReviewItem({ item, onDone, names }) {
  const t = useT()
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
        <span className={`review-rating review-rating--${item.rating}`}>{item.rating === 'up' ? t('review.good') : `👎 ${item.reason ? t.label('reason', item.reason) : t('review.problem')}`}</span>
        <span className="page-note">{names[item.persona] || item.persona} · {new Date(item.timestamp).toLocaleString()}</span>
      </div>
      <p><strong>{t('review.q')}</strong> {item.question}</p>
      {item.can_approve ? (
        <label className="review-answer">
          <span>{t('review.edit')}</span>
          <textarea className="create-select" rows={4} maxLength={4000} value={answer} onChange={e => setAnswer(e.target.value)} />
        </label>
      ) : <p className="review-answer-text"><strong>{t('review.a')}</strong> {item.answer}</p>}
      {item.note && <p className="page-note">{t('review.note', { note: item.note })}</p>}
      {error && <div className="page-alert">{error}</div>}
      <div className="model-actions">
        {item.can_approve && (
          <button className="pill-btn pill-btn--dark" disabled={busy} onClick={() => act(() => api.approve(item.id, answer.trim() !== item.answer ? answer.trim() : undefined))}
            title={t('review.approveTip')}>
            <span className="pill-inner">{t('review.approve')}</span>
          </button>
        )}
        <button className="pill-btn pill-btn--outline" disabled={busy} onClick={() => act(() => api.dismiss(item.id))}><span className="pill-inner">{t('review.dismiss')}</span></button>
      </div>
    </li>
  )
}

function Review({ persona, names }) {
  const t = useT()
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let cancelled = false
    setItems(null)
    api.reviewQueue(persona || undefined).then(d => !cancelled && setItems(d)).catch(e => !cancelled && setError(e.message))
    return () => { cancelled = true }
  }, [persona])
  if (error) return <div className="page-alert">{error}</div>
  if (!items) return <p className="page-note">{t('common.loading')}</p>
  if (!items.length) return <p className="page-note">{t('review.none')}</p>
  return (
    <>
      <p className="page-note">{t('review.explain')}</p>
      <ul className="gap-list">{items.map(i => <ReviewItem key={i.id} item={i} names={names} onDone={(id) => setItems(list => list.filter(x => x.id !== id))} />)}</ul>
    </>
  )
}

function DeleteHistory({ persona, name, onDeleted }) {
  const t = useT()
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  useEffect(() => { setConfirming(false); setMessage('') }, [persona])
  const run = async () => {
    setBusy(true)
    try {
      const r = await api.deleteHistory(persona || undefined)
      setMessage(t('hist.deleted', { questions: r.questions_deleted, feedback: r.feedback_deleted }))
      onDeleted()
    } catch (e) { setMessage(e.message) }
    setBusy(false); setConfirming(false)
  }
  return (
    <div className="history-delete">
      {confirming ? (
        <>
          <span>{t('hist.confirm', { name: name || t('hist.anyModel') })}</span>
          <button className="pill-btn pill-btn--dark" disabled={busy} onClick={run}><span className="pill-inner">{busy ? t('common.deleting') : t('mem.delete')}</span></button>
          <button className="pill-btn pill-btn--outline" disabled={busy} onClick={() => setConfirming(false)}><span className="pill-inner">{t('common.cancel')}</span></button>
        </>
      ) : (
        <button className="page-link" onClick={() => { setConfirming(true); setMessage('') }}>{name ? t('hist.linkWith', { name }) : t('hist.link')}</button>
      )}
      {message && <span className="page-note" role="status">{message}</span>}
    </div>
  )
}

export default function InsightsPage({ id }) {
  const t = useT()
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
        <div className="eyebrow eyebrow--accent">{t('nav.insights')}</div>
        <h1 className="page-h1">{t('ins.title')}</h1>
        <p className="page-sub">{t('ins.sub')}</p>
      </section>
      <section className="shell page-section insights-layout">
        <div className="insights-filters">
          <select className="create-select" value={persona} onChange={e => choose(e.target.value)} aria-label={t('ins.model')}>
            <option value="">{t('common.allModels')}</option>
            {personas.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          {tab === 'overview' && (
            <div className="seg" role="group" aria-label={t('ins.dateRange')}>
              {RANGES.map(d => <button key={d} className={days === d ? 'is-on' : ''} aria-pressed={days === d} onClick={() => setDays(d)}>{t(`range.${d}`)}</button>)}
            </div>
          )}
        </div>
        <div className="tabs" role="tablist">
          {['overview', 'gaps', 'review'].map(name => (
            <button key={name} role="tab" aria-selected={tab === name} className={tab === name ? 'is-on' : ''} onClick={() => setTab(name)}>{t(`ins.${name}`)}</button>
          ))}
        </div>
        {tab === 'overview' && <Overview key={refresh} persona={persona} days={days} />}
        {tab === 'gaps' && (persona ? <Gaps key={refresh} persona={persona} kind={kind} /> : <p className="page-note">{t('gaps.choose')}</p>)}
        {tab === 'review' && <Review key={refresh} persona={persona} names={Object.fromEntries(personas.map(p => [p.id, p.name]))} />}
        <DeleteHistory persona={persona} name={name} onDeleted={() => setRefresh(n => n + 1)} />
      </section>
    </div>
  )
}
