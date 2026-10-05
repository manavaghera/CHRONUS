import useScrollReveal from './useScrollReveal'

const cards = [
  { icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>, title: 'No invented opinions', desc: 'Answers are anchored to retrieved material, not generated from a persona prompt.' },
  { icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M16 13H8M16 17H8M10 9H8"/></svg>, title: 'Source citations on every answer', desc: 'Every response is tagged — "From a letter, 1998" — so you always know the origin.' },
  { icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>, title: 'Session-aware design', desc: 'Intentionally built to avoid encouraging dependency — clear framing as a memory tool.' },
  { icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>, title: 'Your data stays governed', desc: 'Access, deletion, and export controls live with the family, not the platform.' },
]

function Card({ card, delay }) {
  const [ref, inView] = useScrollReveal()
  return (
    <div ref={ref} className={`trust-card ${inView?'in-view':''}`} style={{transitionDelay:delay+'ms'}}>
      <div className="tc-icon">{card.icon}</div>
      <h3>{card.title}</h3>
      <p>{card.desc}</p>
    </div>
  )
}

export default function TrustSection() {
  const [hRef, hIn] = useScrollReveal()
  return (
    <section className="trust-section" id="ethics" style={{ position: 'relative', zIndex: 10 }}>
      <div className="shell trust-inner">
        <div ref={hRef} className={`trust-header sr ${hIn?'in-view':''}`}>
          <div className="eyebrow eyebrow--dark">Trust &amp; Ethics</div>
          <h2 className="trust-h2 line-clip"><span>Designed for dignity</span></h2>
          <p className="trust-sub">Every answer comes with a visible source — so you always know where it came from.</p>
        </div>
        <div className="trust-grid">{cards.map((c,i) => <Card key={i} card={c} delay={i*80}/>)}</div>
      </div>
    </section>
  )
}