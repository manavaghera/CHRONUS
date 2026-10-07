import { useEffect, useRef, useState } from 'react'
import { useT } from '../i18n'
import './charts.css'

// Small single-series charts for Insights and time travel. One hue (the
// site accent, checked for contrast against the surface), thin marks with a
// 4px rounded data end, hairline grid, a tooltip on hover AND keyboard focus,
// and a table view so no value is hover-only.

const compact = (n) => (n >= 10000 ? `${(n / 1000).toFixed(n >= 100000 ? 0 : 1)}K` : n.toLocaleString())

export function StatTile({ label, value, sub }) {
  return (
    <div className="stat-tile">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  )
}

function niceMax(max) {
  if (max <= 0) return 1
  const pow = 10 ** Math.floor(Math.log10(max))
  const step = [1, 2, 2.5, 5, 10].find(s => s * pow >= max / 1) * pow
  return step >= max ? step : step * 2
}

// Columns rising from one baseline: data [{label, value, tip?}]
export function ColumnChart({ data, height = 160, label, format = compact, tickEvery, onPick, selected }) {
  const wrapRef = useRef(null)
  const [width, setWidth] = useState(480)
  const [hover, setHover] = useState(null)
  const [table, setTable] = useState(false)
  const t = useT()

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(200, e.contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const left = 34, bottom = 22, top = 8
  const plotW = width - left - 4, plotH = height - bottom - top
  const max = niceMax(Math.max(0, ...data.map(d => d.value)))
  const slot = plotW / Math.max(1, data.length)
  const barW = Math.max(2, Math.min(24, slot - 2))  // capped thickness; >= 2px surface gap between bars
  const y = (v) => top + plotH - (v / max) * plotH
  const every = tickEvery || Math.max(1, Math.ceil(data.length / Math.floor(plotW / 56)))

  const bar = (d, i) => {
    const x = left + i * slot + (slot - barW) / 2
    const h = (d.value / max) * plotH
    const r = Math.min(4, barW / 2, h)
    const yTop = top + plotH - h
    // rounded data end, square at the baseline
    const path = h <= 0 ? '' : `M${x},${top + plotH} V${yTop + r} Q${x},${yTop} ${x + r},${yTop} H${x + barW - r} Q${x + barW},${yTop} ${x + barW},${yTop + r} V${top + plotH} Z`
    return { x, path }
  }

  return (
    <figure className="chart" aria-label={label}>
      <div className="chart-head">
        <figcaption>{label}</figcaption>
        <button className="chart-toggle" onClick={() => setTable(on => !on)}>{table ? t('chart.chart') : t('chart.table')}</button>
      </div>
      {table ? (
        <table className="chart-table">
          <tbody>{data.map(d => <tr key={d.label}><th scope="row">{d.label}</th><td>{format(d.value)}</td></tr>)}</tbody>
        </table>
      ) : (
        <div className="chart-plot" ref={wrapRef} onPointerLeave={() => setHover(null)}>
          <svg width={width} height={height} role="img" aria-label={label}>
            {[0, max / 2, max].map(v => (
              <g key={v}>
                <line className="chart-grid" x1={left} x2={width - 4} y1={y(v)} y2={y(v)} />
                <text className="chart-tick" x={left - 6} y={y(v) + 3} textAnchor="end">{format(Math.round(v))}</text>
              </g>
            ))}
            {data.map((d, i) => {
              const { x, path } = bar(d, i)
              const active = hover === i || selected === d.label
              return (
                <g key={d.label} tabIndex={0} role="button" aria-label={`${d.label}: ${format(d.value)}`}
                  className={`chart-bar${active ? ' is-active' : ''}${onPick ? ' is-pickable' : ''}`}
                  onPointerEnter={() => setHover(i)} onFocus={() => setHover(i)} onBlur={() => setHover(null)}
                  onClick={() => onPick?.(d)} onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && onPick?.(d)}>
                  {/* hit target: the whole slot, bigger than the mark */}
                  <rect x={left + i * slot} y={top} width={slot} height={plotH} fill="transparent" />
                  {path && <path d={path} />}
                  {i % every === 0 && (
                    <text className="chart-tick" x={x + barW / 2} y={height - 6} textAnchor="middle">{d.short ?? d.label}</text>
                  )}
                </g>
              )
            })}
          </svg>
          {hover !== null && data[hover] && (
            <div className="chart-tip" style={{ left: Math.min(width - 150, Math.max(0, bar(data[hover], hover).x - 40)), top: 0 }}>
              <strong>{format(data[hover].value)}</strong>
              <span>{data[hover].tip || data[hover].label}</span>
            </div>
          )}
        </div>
      )}
    </figure>
  )
}

// Horizontal bars for a ranked list: items [{label, value, note?}]
export function BarList({ items, label, format = compact }) {
  const t = useT()
  const max = Math.max(1, ...items.map(i => i.value))
  return (
    <figure className="chart" aria-label={label}>
      <div className="chart-head"><figcaption>{label}</figcaption></div>
      {items.length === 0 ? <p className="chart-empty">{t('chart.empty')}</p> : (
        <ul className="barlist">
          {items.map(i => (
            <li key={i.label} title={`${i.label}: ${format(i.value)}`}>
              <span className="barlist-label">{i.label}</span>
              <span className="barlist-track"><span style={{ width: `${(i.value / max) * 100}%` }} /></span>
              <span className="barlist-value">{format(i.value)}</span>
            </li>
          ))}
        </ul>
      )}
    </figure>
  )
}
