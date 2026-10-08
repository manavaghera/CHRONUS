import { useEffect, useState } from 'react'
import { api } from '../api'
import { navigate } from '../router'
import { tx, useLanguage, useT } from '../i18n'
import { SplitWords } from '../lib/motion'
import { useToast } from '../lib/toast'
import Icon from '../lib/Icon'
import { BarList, ColumnChart, StatTile } from '../components/Charts'
import { LEVELS, MODES } from '../chat/Conversation'

const RANGES = [[7, tx('7 days')], [30, tx('30 days')], [90, tx('90 days')]]
const REASONS = { not_their_words: tx('Not their words'), wrong_attribution: tx('Wrong source'), incorrect: tx('Factually wrong'), unhelpful: tx('Didn’t answer'), other: tx('Something else') }
const pct = (x) => `${Math.round(x * 100)}%`
const secs = (ms) => (ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`)

function useLoad(fn, deps) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let off = false
    setData(null); setError('')
    fn().then(d => !off && setData(d)).catch(e => !off && setError(e.message))
    return () => { off = true }
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps
  return [data, error, setData]
}

function Overview({ persona, days }) {
  const { t, lang } = useLanguage()
  const [d, error] = useLoad(() => api.analytics(persona, days), [persona, days])
  const short = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString(lang, { month: 'short', day: 'numeric' })
  if (error) return <div className="alert" role="alert">{error}</div>
  if (!d) return <p className="row gap8 note"><span className="spinner" />{t('Loading…')}</p>
  if (!d.total) return <div className="card empty-s"><Icon name="chart" size={30} /><p className="serif" style={{ fontSize: 28 }}>{t('No questions yet.')}</p><p className="small">{persona ? t('Numbers appear here as people talk with this model.') : t('Numbers appear here as people talk with your models.')}</p></div>
  return (
    <div className="ins">
      <div className="kpis">
        <StatTile label={t('Questions answered')} value={d.total.toLocaleString()} sub={t('in this range')} accent />
        <StatTile label={t('Said “I don’t know”')} value={pct(d.refusal_rate)} sub={t('{n} questions', { n: d.refused.toLocaleString() })} />
        <StatTile label={t('Median grounding')} value={d.grounding.median == null ? '–' : pct(d.grounding.median)} sub={t('answer words found in sources')} />
        <StatTile label={t('Typical answer time')} value={d.latency_ms.p50 == null ? '–' : secs(d.latency_ms.p50)} sub={d.latency_ms.p95 == null ? '' : t('95% within {time}', { time: secs(d.latency_ms.p95) })} />
        <StatTile label={t('Feedback')} value={t('{up} up · {down} down', { up: d.feedback.up, down: d.feedback.down })} sub={t('{n} waiting for review', { n: d.feedback.pending })} />
      </div>
      <div className="ins-grid">
        <div className="card ins-card"><ColumnChart label={t('Questions per day')} data={d.per_day.map(x => ({ label: x.date, short: short(x.date), value: x.count }))} /></div>
        <div className="card ins-card"><ColumnChart label={t('How grounded answers are')} data={d.grounding.buckets.map(b => ({ label: `${pct(b.from)}–${pct(b.to)}`, value: b.count }))} /></div>
        <div className="card ins-card"><BarList label={t('How questions were answered')} items={Object.entries(d.by_mode).map(([k, v]) => ({ label: t(MODES[k] || k), value: v }))} /></div>
        <div className="card ins-card"><BarList label={t('Confidence')} items={['high', 'medium', 'low'].filter(k => d.by_confidence[k]).map(k => ({ label: t(LEVELS[k]), value: d.by_confidence[k] }))} /></div>
        <div className="card ins-card wide"><BarList label={t('Most asked')} items={d.top_questions.map(q => ({ label: q.question, value: q.count }))} /></div>
      </div>
    </div>
  )
}

function Gaps({ persona, kind }) {
  const t = useT()
  const [d, error] = useLoad(() => api.gaps(persona), [persona])
  if (error) return <div className="alert" role="alert">{error}</div>
  if (!d) return <p className="row gap8 note"><span className="spinner" />{t('Loading…')}</p>
  if (!d.gaps.length) return <div className="card empty-s"><Icon name="check" size={30} /><p className="serif" style={{ fontSize: 28 }}>{t('No gaps yet.')}</p><p className="small">{t('Questions the archive can’t answer, or answers only with low confidence, collect here.')}</p></div>
  return (
    <div className="col gap12">
      <p className="small">{t('{n} of {total} questions couldn’t be answered well. Similar questions are grouped.', { n: d.unanswered, total: d.total_questions })}</p>
      {d.gaps.map(g => (
        <div key={g.question} className="card gap-card">
          <div className="row-sb"><p className="serif" style={{ fontSize: 22, lineHeight: 1.25 }}>“{g.question}”</p><span className="badge">{t('asked {n}×', { n: g.count })}</span></div>
          {g.examples.length > 0 && <p className="note">{t('Also:')} {g.examples.map(e => `“${e}”`).join(', ')}</p>}
          {kind === 'custom' && (
            <div className="row-sb wrap-row gap12 gap-fix">
              <span className="small">{g.suggestion ? t('Could be filled by interview {id}: “{question}”', { id: g.suggestion.id, question: t(g.suggestion.question) }) : t('Add a document that covers this.')}</span>
              <button type="button" className="btn btn-s btn-sm" onClick={() => navigate(`/create/${persona}`)}>{g.suggestion ? t('Answer it') : t('Add a document')}<Icon name="arrow" size={14} /></button>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function ReviewItem({ item, name, onDone }) {
  const { t, lang } = useLanguage()
  const toast = useToast()
  const [answer, setAnswer] = useState(item.answer)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const act = async (fn, msg) => {
    setBusy(true); setError('')
    try { await fn(); toast(msg); onDone(item.id) } catch (e) { setError(e.message); setBusy(false) }
  }
  return (
    <div className="card review">
      <div className="row-sb wrap-row gap8">
        <span className={`badge${item.rating === 'up' ? ' ok' : ' acc'}`}>{item.rating === 'up' ? t('Good answer') : item.reason ? t(REASONS[item.reason] || item.reason) : t('Problem')}</span>
        <span className="lab">{name} · {new Date(item.timestamp).toLocaleString(lang)}</span>
      </div>
      <p className="small"><b>{t('Question:')}</b> {item.question}</p>
      {item.can_approve
        ? <label className="fld">{t('Answer (edit before approving if needed)')}<textarea className="field" rows={4} maxLength={4000} value={answer} onChange={e => setAnswer(e.target.value)} /></label>
        : <p className="small"><b>{t('Answer:')}</b> {item.answer}</p>}
      {item.note && <p className="note">{t('Note: {note}', { note: item.note })}</p>}
      {error && <div className="alert" role="alert">{error}</div>}
      <div className="row wrap-row gap8">
        {item.can_approve && <button type="button" className="btn btn-p btn-sm" disabled={busy} title={t('Stored as a memory labelled “reviewed past answer”, never quoted as their own words')}
          onClick={() => act(() => api.approve(item.id, answer.trim() !== item.answer ? answer.trim() : undefined), t('Approved into memory'))}>{t('Approve into memory')}</button>}
        <button type="button" className="btn btn-s btn-sm" disabled={busy} onClick={() => act(() => api.dismiss(item.id), t('Dismissed'))}>{t('Dismiss')}</button>
      </div>
    </div>
  )
}

function Review({ persona, names }) {
  const t = useT()
  const [items, error, setItems] = useLoad(() => api.reviewQueue(persona || undefined), [persona])
  if (error) return <div className="alert" role="alert">{error}</div>
  if (!items) return <p className="row gap8 note"><span className="spinner" />{t('Loading…')}</p>
  if (!items.length) return <div className="card empty-s"><Icon name="check" size={30} /><p className="serif" style={{ fontSize: 28 }}>{t('Nothing waiting.')}</p><p className="small">{t('Thumbs up and down on answers land here for a person to review.')}</p></div>
  return (
    <div className="col gap12">
      <p className="small">{t('Approving a personal model’s answer stores it as a memory labelled “reviewed past answer”: it can help later answers but is never quoted as their own words. Pretrained models only learn from published sources, so their feedback can only be dismissed.')}</p>
      {items.map(i => <ReviewItem key={i.id} item={i} name={names[i.persona] || i.persona} onDone={(id) => setItems(list => list.filter(x => x.id !== id))} />)}
    </div>
  )
}

export default function InsightsPage({ id }) {
  const t = useT()
  const toast = useToast()
  const [personas, setPersonas] = useState([])
  const [days, setDays] = useState(30)
  const [tab, setTab] = useState('overview')
  const [refresh, setRefresh] = useState(0)
  const [confirm, setConfirm] = useState(false)
  useEffect(() => { api.personas().then(setPersonas).catch(() => {}) }, [])
  const persona = id || ''
  const current = personas.find(p => p.id === persona)

  const wipe = async () => {
    try { const r = await api.deleteHistory(persona || undefined); toast(t('Deleted {q} questions and {f} feedback entries', { q: r.questions_deleted, f: r.feedback_deleted })); setRefresh(n => n + 1) }
    catch (e) { toast(e.message) } finally { setConfirm(false) }
  }

  return (
    <div className="page">
      <section className="page-hero">
        <div className="page-hero-bg" aria-hidden="true" />
        <div className="wrap">
          <nav className="crumbs" aria-label={t('Breadcrumb')}><a href="#/">{t('Home')}</a><span aria-hidden="true">/</span><span>{t('Insights')}</span></nav>
          <span className="over">{t('Insights')}</span>
          <SplitWords as="h1" className="h1 h1-sm" text={t('How your models')} em={t('are doing.')} />
          <p className="lede">{t('What people ask, how grounded the answers are, what the archive can’t answer yet, and feedback waiting for a person to review.')}</p>
        </div>
      </section>
      <section className="sec" style={{ paddingTop: 8 }}>
        <div className="wrap col gap16">
          <div className="tbar">
            <label className="tchip sel"><Icon name="search" size={14} /><span className="sr-only">{t('Model')}</span>
              <select value={persona} onChange={e => navigate(e.target.value ? `/insights/${e.target.value}` : '/insights')}>
                <option value="">{t('All models')}</option>{personas.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select></label>
            {tab === 'overview' && <div className="seg" role="group" aria-label={t('Date range')}>{RANGES.map(([d, l]) => <button key={d} type="button" aria-pressed={days === d} onClick={() => setDays(d)}>{t(l)}</button>)}</div>}
            {current && <a className="btn btn-s btn-sm" href={`#/memories/${current.id}`}>{t('{name}’s memories', { name: current.name })}</a>}
          </div>
          <div className="dtabs" role="group" aria-label={t('Insights views')}>
            {[['overview', t('Overview')], ['gaps', t('Knowledge gaps')], ['review', t('Review queue')]].map(([k, l]) => <button key={k} type="button" className="dtab" aria-pressed={tab === k} onClick={() => setTab(k)}>{l}</button>)}
          </div>
          <div key={`${tab}-${refresh}`} className="tabpanel">
            {tab === 'overview' && <Overview persona={persona} days={days} />}
            {tab === 'gaps' && (persona ? <Gaps persona={persona} kind={current?.kind} /> : <p className="small">{t('Choose a model above to see what its archive can’t answer.')}</p>)}
            {tab === 'review' && <Review persona={persona} names={Object.fromEntries(personas.map(p => [p.id, p.name]))} />}
          </div>
          <div className="row wrap-row gap12 wipe">
            {confirm ? <>
              <span className="small">{t('Delete every question you asked {name}, and your feedback? This can’t be undone.', { name: current?.name || t('any model') })}</span>
              <button type="button" className="btn btn-a btn-sm" onClick={wipe}>{t('Delete')}</button>
              <button type="button" className="btn btn-s btn-sm" onClick={() => setConfirm(false)}>{t('Cancel')}</button>
            </> : <button type="button" className="linkbtn" onClick={() => setConfirm(true)}>{current ? t('Delete my question history with {name}', { name: current.name }) : t('Delete my question history')}</button>}
          </div>
        </div>
      </section>
    </div>
  )
}
