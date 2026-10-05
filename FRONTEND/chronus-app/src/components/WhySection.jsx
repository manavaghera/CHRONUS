import useScrollReveal from './useScrollReveal'

export default function WhySection() {
  const [ref, inView] = useScrollReveal(0.3)
  return (
    <section className="why-section" id="why" style={{ position: 'relative', zIndex: 10 }}>
      <div className="shell why-inner">
        <div className="why-grid">
          <div>
            <div className="why-big-text" ref={ref}>
              {['Personal archives', 'disappear with', 'the person.'].map((line, li) => (
                <span className="line-clip" key={li}><span>
                  {line.split(' ').map((w, wi) => <span key={wi} className={`char-reveal ${inView?'in-view':''}`} style={{transitionDelay:(li*2+wi)*80+'ms'}}>{w}{' '}</span>)}
                </span></span>
              ))}
            </div>
          </div>
          <div>
            <div className="why-accent-line sr in-view" style={{transitionDelay:'.3s'}}/>
            <div className="why-body sr in-view" style={{transitionDelay:'.4s'}}>
              <p>Texts, voice notes, letters, photos — usually static, unsearchable, and fading. Everything about a person's presence vanishes with them.</p>
              <p>CHRONUS turns that static archive into something you can actually revisit and ask things of — without pretending it's the person. Every answer is traced back to something real, or it says <em>"I don't know."</em></p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}