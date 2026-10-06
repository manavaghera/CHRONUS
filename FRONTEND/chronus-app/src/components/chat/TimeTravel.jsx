import { useEffect, useState } from 'react'
import { api } from '../../api'
import { ColumnChart } from '../charts'

// Time travel: answer only from memories dated within a range of years.
// The chart shows how many dated memories each year has; click a year to
// jump to it, or pick a range.
export default function TimeTravel({ personaId, value, onChange }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    api.timeline(personaId).then(d => !cancelled && setData(d)).catch(e => !cancelled && setError(e.message))
    return () => { cancelled = true }
  }, [personaId])

  if (error) return <div className="tt-panel"><p className="page-note">{error}</p></div>
  if (!data) return <div className="tt-panel"><p className="page-note">Loading the timeline…</p></div>
  const years = Object.keys(data.years).map(Number)
  if (!years.length) {
    return <div className="tt-panel"><p className="page-note">None of this model's memories are dated, so time travel isn't available.</p></div>
  }
  const first = Math.min(...years), last = Math.max(...years)
  const all = Array.from({ length: last - first + 1 }, (_, i) => first + i)
  const from = value?.from ?? first, to = value?.to ?? last
  const set = (f, t) => onChange({ from: Math.min(f, t), to: Math.max(f, t) })

  return (
    <div className="tt-panel">
      <ColumnChart
        label={`Dated memories per year (${data.dated.toLocaleString()} dated, ${data.undated.toLocaleString()} undated)`}
        data={all.map(y => ({ label: String(y), short: `'${String(y).slice(2)}`, value: data.years[y] || 0, tip: `memories from ${y}` }))}
        height={120} onPick={(d) => set(Number(d.label), Number(d.label))}
      />
      <div className="tt-controls">
        <label>From <select className="create-select" value={from} onChange={e => set(Number(e.target.value), to)}>{all.map(y => <option key={y}>{y}</option>)}</select></label>
        <label>to <select className="create-select" value={to} onChange={e => set(from, Number(e.target.value))}>{all.map(y => <option key={y}>{y}</option>)}</select></label>
        {value && <button className="demo-quick-btn" onClick={() => onChange(null)}>Any time</button>}
      </div>
      <p className="page-note">Undated memories (most interviews and books) are left out while a range is set.</p>
    </div>
  )
}
