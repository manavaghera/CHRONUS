import useScrollReveal from './useScrollReveal'
import { useT } from '../i18n'

export default function WhySection() {
  const t = useT()
  const [ref, inView] = useScrollReveal(0.3)
  return (
    <section className="why-section" id="why" style={{ position: 'relative', zIndex: 10 }}>
      <div className="shell why-inner">
        <div className="why-grid">
          <div>
            <div className="why-big-text" ref={ref}>
              {[t('why.line1'), t('why.line2'), t('why.line3')].map((line, li) => (
                <span className="line-clip" key={li}><span>
                  {line.split(' ').map((w, wi) => <span key={wi}><span className={`char-reveal ${inView?'in-view':''}`} style={{transitionDelay:(li*2+wi)*80+'ms'}}>{w}</span>{' '}</span>)}
                </span></span>
              ))}
            </div>
          </div>
          <div>
            <div className="why-accent-line sr in-view" style={{transitionDelay:'.3s'}}/>
            <div className="why-body sr in-view" style={{transitionDelay:'.4s'}}>
              <p>{t('why.p1')}</p>
              <p>{t('why.p2')} <em>{t('why.idk')}</em></p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}