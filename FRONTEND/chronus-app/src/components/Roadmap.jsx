import useScrollReveal from './useScrollReveal'
import { useT } from '../i18n'

const phases = [
  { key: 'roadmap.p1' },
  { key: 'roadmap.p2' },
  { key: 'roadmap.p3' },
]

function Phase({ phase }) {
  const t = useT()
  const [ref, inView] = useScrollReveal()
  return (
    <div ref={ref} className={`roadmap-phase ${inView?'in-view':''}`}>
      <span className="rp-tag">{t(`${phase.key}.tag`)}</span>
      <h3>{t(`${phase.key}.title`)}</h3>
      <p>{t(`${phase.key}.desc`)}</p>
    </div>
  )
}

export default function Roadmap() {
  const t = useT()
  const [hRef, hIn] = useScrollReveal()
  return (
    <section className="roadmap-section" id="roadmap" style={{ position: 'relative', zIndex: 10 }}>
      <div className="shell roadmap-inner">
        <div ref={hRef} className={`sr ${hIn?'in-view':''}`}><div className="eyebrow eyebrow--dark">{t('nav.roadmap')}</div></div>
        <div className={`sr ${hIn?'in-view':''}`} style={{transitionDelay:'.1s',marginBottom:'3rem'}}>
          <h2 style={{maxWidth:'20ch',fontSize:'2.25rem',fontWeight:600,letterSpacing:'-.02em'}} className="line-clip"><span>{t('roadmap.title')}</span></h2>
        </div>
        <div className="roadmap-timeline">{phases.map((p,i) => <Phase key={i} phase={p}/>)}</div>
      </div>
    </section>
  )
}