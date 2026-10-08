import { useEffect, useState } from 'react'
import { api } from '../api'
import { useT } from '../i18n'

// Answer only from memories dated within a range of years. Bars show how
// many dated memories each year has; click one to jump to that year.
export default function TimeTravel({ personaId, value, onChange }) {
  const t = useT()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let cancelled = false
    api.timeline(personaId).then(d => !cancelled && setData(d)).catch(e => !cancelled && setError(e.message))
    return () => { cancelled = true }
  }, [personaId])

  if (error) return <div className="tt"><p className="note">{error}</p></div>
  if (!data) return <div className="tt row gap8"><span className="spinner" /><span className="note">{t('Loading the timeline…')}</span></div>
  const years = Object.keys(data.years).map(Number)
  if (!years.length) return <div className="tt"><p className="note">{t('None of this model’s memories are dated yet, so time travel has nothing to filter.')}</p></div>
  const first = Math.min(...years), last = Math.max(...years)
  const all = Array.from({ length: last - first + 1 }, (_, i) => first + i)
  const max = Math.max(...Object.values(data.years))
  const from = value?.from ?? first, to = value?.to ?? last
  const set = (f, l) => onChange({ from: Math.min(f, l), to: Math.max(f, l) })
  return (
    <div className="tt">
      <div className="tt-bars" role="group" aria-label={t('{n} dated memories by year', { n: data.dated })}>
        {all.map(y => (
          <button key={y} type="button" className={`tt-bar${y >= from && y <= to ? ' is-on' : ''}`} title={t('{year}: {n} memories', { year: y, n: data.years[y] || 0 })}
            aria-label={t('{year}: {n} memories', { year: y, n: data.years[y] || 0 })} onClick={() => set(y, y)}>
            <i style={{ height: `${Math.max(4, ((data.years[y] || 0) / max) * 100)}%` }} />
          </button>
        ))}
      </div>
      <div className="row wrap-row gap12">
        <label className="fld row gap8">{t('From')} <select className="field sm" value={from} onChange={e => set(Number(e.target.value), to)}>{all.map(y => <option key={y}>{y}</option>)}</select></label>
        <label className="fld row gap8">{t('To')} <select className="field sm" value={to} onChange={e => set(from, Number(e.target.value))}>{all.map(y => <option key={y}>{y}</option>)}</select></label>
        {value && <button type="button" className="btn btn-s btn-sm" onClick={() => onChange(null)}>{t('Any year')}</button>}
        <span className="note">{t('{dated} dated · {undated} undated', { dated: data.dated.toLocaleString(), undated: data.undated.toLocaleString() })}</span>
      </div>
    </div>
  )
}
