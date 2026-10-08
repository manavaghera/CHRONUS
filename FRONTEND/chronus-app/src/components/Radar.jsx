import { DIMENSIONS } from '../lib/data'
import { useT } from '../i18n'

// The personality map: six interview dimensions on a hexagon, the shape
// filled by how much of each has been answered (values 0..1).
const pt = (i, v) => {
  const a = ((-90 + 60 * i) * Math.PI) / 180
  return [150 + 110 * v * Math.cos(a), 150 + 110 * v * Math.sin(a)]
}
const poly = (vals) => vals.map((v, i) => pt(i, v).map(n => n.toFixed(1)).join(',')).join(' ')
const labelPos = (i, r) => {
  const a = ((-90 + 60 * i) * Math.PI) / 180
  return { left: `${(50 + r * Math.cos(a)).toFixed(2)}%`, top: `${(50 + r * Math.sin(a)).toFixed(2)}%` }
}

export default function Radar({ values, active = -1, onPick, labels = 'small', breathe = false, className = '' }) {
  const t = useT()
  const vals = values.map(v => Math.max(0.05, Math.min(1, v)))
  return (
    <div className={`radar ${labels === 'buttons' ? 'radar--big' : ''} ${className}`.trim()}>
      <svg viewBox="0 0 300 300" aria-hidden="true">
        {[0.25, 0.5, 0.75, 1].map(v => <polygon key={v} className="rg" points={poly([v, v, v, v, v, v])} />)}
        {DIMENSIONS.map((d, i) => {
          const [x, y] = pt(i, 1)
          return <line key={d.key} className={`ra${active === i ? ' is-on' : ''}`} x1="150" y1="150" x2={x.toFixed(1)} y2={y.toFixed(1)} />
        })}
        <polygon className={`rv-shape${breathe ? ' breathe' : ''}`} points={poly(vals)} />
        {vals.map((v, i) => {
          const [x, y] = pt(i, v)
          return <circle key={i} className={`rd${active === i ? ' is-on' : ''}`} cx={x.toFixed(1)} cy={y.toFixed(1)} r="4.5" />
        })}
      </svg>
      {DIMENSIONS.map((d, i) => (labels === 'buttons'
        ? <button key={d.key} type="button" className="rl-btn" style={labelPos(i, 47)} aria-pressed={active === i} onClick={() => onPick?.(i)}>
            {t(d.label)}<span>{t('{n} questions', { n: d.ids.length })}</span>
          </button>
        : <span key={d.key} className="rl" style={labelPos(i, 47)}>{t(d.short)}</span>))}
    </div>
  )
}
