import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { tx, useT } from '../i18n'
import { FIGURES, initials } from '../lib/data'
import { Reveal, SplitWords, tiltHandlers } from '../lib/motion'
import Icon from '../lib/Icon'

const FIELDS = [tx('All'), tx('Science'), tx('Politics'), tx('Philosophy'), tx('Literature'), tx('Business')]
const TICKS = [100, 1000, 1500, 1600, 1700, 1800, 1900, 2000]
// Squeeze 100–1500 AD into the first 16% so the busy centuries get room
const pos = (y) => (y <= 1500 ? ((y - 100) / 1400) * 16 : 16 + ((y - 1500) / 526) * 84)
const yearOf = (v) => Math.round(v <= 160 ? 100 + (v / 160) * 1400 : 1500 + ((v - 160) / 840) * 526)

export default function PretrainedPage() {
  const t = useT()
  const [list, setList] = useState(null)
  const [error, setError] = useState('')
  const [q, setQ] = useState('')
  const [field, setField] = useState('All')
  const [yv, setYv] = useState(807)
  const [yearOn, setYearOn] = useState(false)
  useEffect(() => { api.personas().then(p => setList(p.filter(x => x.kind === 'pretrained'))).catch(e => { setError(e.message); setList([]) }) }, [])

  const yearLabel = (y) => (y < 1000 ? t('{y} AD', { y }) : String(y))
  const year = yearOf(yv)
  const alive = (f) => f && f.b <= year && year <= (f.d || 2026)
  const shown = useMemo(() => (list || []).filter(p => {
    const f = FIGURES[p.id] || {}
    const s = q.trim().toLowerCase()
    return (field === 'All' || f.field === field) && (!s || `${p.name} ${p.description} ${(p.sources || []).map(x => x.title).join(' ')}`.toLowerCase().includes(s))
  }), [list, q, field])
  const living = (list || []).filter(p => alive(FIGURES[p.id])).map(p => p.name)
  const tilt = tiltHandlers(10)

  return (
    <div className="page">
      <section className="page-hero">
        <div className="page-hero-bg" aria-hidden="true" />
        <div className="wrap">
          <nav className="crumbs" aria-label={t('Breadcrumb')}><a href="#/">{t('Home')}</a><span aria-hidden="true">/</span><span>{t('Pretrained models')}</span></nav>
          <div className="ph-grid">
            <div className="l">
              <span className="over">{t('Included with CHRONUS')}</span>
              <SplitWords as="h1" className="h1" text={t('Try it on history')} em={t('before you preserve someone.')} />
              <p className="lede">{t('Each figure answers only from its own public-domain writing or public record, and cites every time. When you are ready, preserve someone from your own life.')}</p>
            </div>
            <Reveal className="r col">
              <div className="pstat"><span className="lab">{t('Models')}</span><b>{list ? list.length : '–'}</b></div>
              <div className="pstat"><span className="lab">{t('Ready to talk')}</span><b>{list ? list.filter(p => p.status === 'ready').length : '–'}</b></div>
              <a className="btn btn-a" href="#/create" style={{ marginTop: 16 }}>{t('Preserve someone')}<Icon name="arrow" /></a>
            </Reveal>
          </div>
          <Reveal className="card scrub" delay={1}>
            <div className="sc-top">
              <div className="col gap8"><span className="lab">{t('Who was alive in')}</span><span className="yrbig" aria-live="polite">{yearLabel(year)}</span></div>
              <p className="small" style={{ flex: '1 1 300px' }}>{!yearOn ? t('Drag through time to see which of these people were alive in a given year.') : living.length ? t('Alive in {year}: {names}.', { year: yearLabel(year), names: living.join(', ') }) : t('None of them were alive in {year}.', { year: yearLabel(year) })}</p>
              {yearOn && <button type="button" className="btn btn-s btn-sm" onClick={() => setYearOn(false)}>{t('Show everyone')}</button>}
            </div>
            <div className="lanes" aria-hidden="true">
              {(list || []).filter(p => FIGURES[p.id]).map(p => {
                const f = FIGURES[p.id], l = pos(f.b), r = pos(f.d || 2026), end = l > 86
                const on = yearOn && alive(f)
                return (
                  <div key={p.id} className="lrow">
                    <span className={`lname${end ? ' end' : ''}${on ? ' is-on' : ''}`} style={{ left: `${end ? r : l}%` }}>{p.name}</span>
                    <i className={`lbar${on ? ' is-on' : ''}`} style={{ left: `${l}%`, width: `${Math.max(0.5, r - l)}%` }} />
                  </div>
                )
              })}
              <i className="ycur" style={{ left: `${yv / 10}%` }} />
            </div>
            <div className="ticks" aria-hidden="true">{TICKS.map(y => <span key={y} style={{ left: `${pos(y)}%` }}>{yearLabel(y)}</span>)}</div>
            <label className="sr-only" htmlFor="yr">{t('Choose a year')}</label>
            <input id="yr" className="yr-rng" type="range" min="0" max="1000" value={yv} aria-valuetext={yearLabel(year)} onChange={e => { setYv(Number(e.target.value)); setYearOn(true) }} />
          </Reveal>
        </div>
      </section>
      <section className="sec" style={{ paddingTop: 24 }} aria-label={t('Pretrained models')}>
        <div className="wrap">
          <div className="tbar">
            <label className="search" htmlFor="pq"><Icon name="search" size={17} /><span className="sr-only">{t('Search models')}</span>
              <input id="pq" type="search" autoComplete="off" placeholder={t('Search by name or work')} value={q} onChange={e => setQ(e.target.value.slice(0, 60))} /></label>
            <div className="seg" role="group" aria-label={t('Field')}>{FIELDS.map(f => <button key={f} type="button" aria-pressed={field === f} onClick={() => setField(f)}>{t(f)}</button>)}</div>
            <span className="lab" aria-live="polite">{t('Showing {n} of {total}', { n: shown.length, total: list?.length || 0 })}</span>
          </div>
          {error && <div className="alert" role="alert">{error}</div>}
          <div className={`pgrid${yearOn ? ' is-yr' : ''}`}>
            {list === null && [0, 1, 2, 3].map(i => <div key={i} className="card pcard2 is-skel" />)}
            {shown.map((p, i) => {
              const f = FIGURES[p.id] || {}
              return (
                <a key={p.id} className={`card pcard2 tilt${yearOn && !alive(f) ? ' is-dim' : ''}`} href={p.status === 'ready' ? `#/chat/${p.id}` : '#/pretrained'} data-cursor={t('Talk')} style={{ animationDelay: `${(i % 4) * 0.07}s` }} {...tilt}>
                  <span className="row-sb"><span className="lab">0{i + 1}</span>{f.field && <span className="badge">{t(f.field)}</span>}</span>
                  <span className="pc-av"><i className="pc-ring" /><span>{f.mono || initials(p.name)}</span></span>
                  <span className="serif pc-name">{p.name}</span>
                  <span className="lab">{f.years ? t(f.years) : ''}</span>
                  <span className="small pc-desc" lang="en">{p.description}</span>
                  <span className="pc-foot"><span className="prov"><i className={`pm${p.id === 'elon_musk' ? ' dash' : ''}`} />{p.sources?.length ? (p.sources.length === 1 ? t('1 work') : t('{n} works', { n: p.sources.length })) : t('Public record')}</span>
                    <span className="pc-go">{p.status === 'ready' ? t('Talk') : t('Not built')}<Icon name="arrow" size={15} /></span></span>
                  <span className="glare" aria-hidden="true" />
                </a>
              )
            })}
          </div>
          {list && !shown.length && !error && (
            <div className="card empty-s"><p className="serif" style={{ fontSize: 30 }}>{t('No model matches that.')}</p><button type="button" className="btn btn-s btn-sm" onClick={() => { setQ(''); setField('All') }}>{t('Clear filters')}</button></div>
          )}
        </div>
      </section>
    </div>
  )
}
