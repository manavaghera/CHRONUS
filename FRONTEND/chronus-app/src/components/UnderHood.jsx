import useScrollReveal from './useScrollReveal'
import { useT } from '../i18n'

const items = [
  { icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><path d="M6 6h.01M6 18h.01"/></svg>, key: 'hood.i1' },
  { icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>, key: 'hood.i2' },
  { icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>, key: 'hood.i3' },
]

function Item({ item, delay }) {
  const t = useT()
  const [ref, inView] = useScrollReveal()
  return (
    <div ref={ref} className={`hood-item ${inView?'in-view':''}`} style={{transitionDelay:delay+'ms'}}>
      <div className="hood-icon">{item.icon}</div>
      <div><h4>{t(`${item.key}.title`)}</h4><p>{t(`${item.key}.desc`)}</p></div>
    </div>
  )
}

export default function UnderHood() {
  const t = useT()
  const [hRef, hIn] = useScrollReveal()
  return (
    <section className="hood-section" style={{ position: 'relative', zIndex: 10 }}>
      <div className="shell hood-inner">
        <div ref={hRef} className={`sr ${hIn?'in-view':''}`} style={{textAlign:'center',marginBottom:'3rem'}}>
          <div className="eyebrow eyebrow--dark" style={{justifyContent:'center'}}>{t('hood.eyebrow')}</div>
          <h2 style={{marginTop:'1rem',fontSize:'2.25rem',fontWeight:600,letterSpacing:'-.02em'}} className="line-clip"><span>{t('hood.title')}</span></h2>
        </div>
        <div className="hood-grid">{items.map((it,i) => <Item key={i} item={it} delay={i*80}/>)}</div>
      </div>
    </section>
  )
}