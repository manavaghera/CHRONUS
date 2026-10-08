import { useState } from 'react'
import { useT } from '../i18n'

// Small single-series charts in the site accent. Every value is reachable
// without hovering: bars are focusable, and each chart has a table view.
const compact = (n) => (n >= 10000 ? `${(n / 1000).toFixed(n >= 100000 ? 0 : 1)}K` : Number(n).toLocaleString())

export function StatTile({ label, value, sub, accent }) {
  return (
    <div className={`card stat-tile${accent ? ' is-acc' : ''}`}>
      <span className="lab">{label}</span>
      <b>{value}</b>
      {sub && <span className="note">{sub}</span>}
    </div>
  )
}

function Frame({ label, table, rows, children }) {
  const t = useT()
  const [asTable, setAsTable] = useState(false)
  return (
    <figure className="chart">
      <div className="row-sb"><figcaption className="lab" style={{ color: 'var(--ink)' }}>{label}</figcaption>
        <button type="button" className="linkbtn" onClick={() => setAsTable(v => !v)}>{asTable ? t('Chart') : t('Table')}</button></div>
      {asTable ? (
        <table className="chart-table"><tbody>{rows.map(([k, v]) => <tr key={k}><th scope="row">{k}</th><td>{v}</td></tr>)}</tbody></table>
      ) : children}
      {table}
    </figure>
  )
}

// Vertical columns: data [{ label, short?, value }]
export function ColumnChart({ label, data }) {
  const [hover, setHover] = useState(null)
  const max = Math.max(1, ...data.map(d => d.value))
  const every = Math.max(1, Math.ceil(data.length / 10))
  return (
    <Frame label={label} rows={data.map(d => [d.label, compact(d.value)])}>
      <div className="cols" onPointerLeave={() => setHover(null)}>
        {data.map((d, i) => (
          <button key={d.label} type="button" className={`col-bar${hover === i ? ' is-on' : ''}`} aria-label={`${d.label}: ${d.value}`}
            onPointerEnter={() => setHover(i)} onFocus={() => setHover(i)} onBlur={() => setHover(null)}>
            <i style={{ height: `${Math.max(d.value ? 3 : 0, (d.value / max) * 100)}%`, animationDelay: `${i * 18}ms` }} />
            {i % every === 0 && <span className="col-x">{d.short || d.label}</span>}
          </button>
        ))}
        {hover != null && data[hover] && (
          <span className="col-tip" style={{ left: `${((hover + 0.5) / data.length) * 100}%` }}>{data[hover].label}: <b>{compact(data[hover].value)}</b></span>
        )}
      </div>
    </Frame>
  )
}

// Horizontal bars: items [{ label, value }]
export function BarList({ label, items }) {
  const t = useT()
  const max = Math.max(1, ...items.map(d => d.value))
  if (!items.length) return <div className="chart"><span className="lab">{label}</span><p className="note">{t('Nothing yet.')}</p></div>
  return (
    <Frame label={label} rows={items.map(d => [d.label, compact(d.value)])}>
      <ul className="hbars">
        {items.map((d, i) => (
          <li key={d.label}>
            <div className="row-sb small"><span className="ell">{d.label}</span><b>{compact(d.value)}</b></div>
            <div className="hbar"><i style={{ width: `${(d.value / max) * 100}%`, animationDelay: `${i * 60}ms` }} /></div>
          </li>
        ))}
      </ul>
    </Frame>
  )
}
