import useScrollReveal from './useScrollReveal'

const phases = [
  { tag: 'Today', title: 'Local-first memory assistant', desc: 'A consent-based, source-cited, voice-authentic conversational agent running entirely on your device.' },
  { tag: 'Coming Next', title: 'Secure family collaboration', desc: 'Multiple relatives contributing memories safely through federated, encrypted architecture.' },
  { tag: 'Research Frontier', title: 'Neuromorphic & quantum-inspired memory', desc: 'Experimental work on brain-inspired dual-memory consolidation — clearly labeled as R&D, not product.' },
]

function Phase({ phase }) {
  const [ref, inView] = useScrollReveal()
  return (
    <div ref={ref} className={`roadmap-phase ${inView?'in-view':''}`}>
      <span className="rp-tag">{phase.tag}</span>
      <h3>{phase.title}</h3>
      <p>{phase.desc}</p>
    </div>
  )
}

export default function Roadmap() {
  const [hRef, hIn] = useScrollReveal()
  return (
    <section className="roadmap-section" id="roadmap" style={{ position: 'relative', zIndex: 10 }}>
      <div className="shell roadmap-inner">
        <div ref={hRef} className={`sr ${hIn?'in-view':''}`}><div className="eyebrow eyebrow--dark">Roadmap</div></div>
        <div className={`sr ${hIn?'in-view':''}`} style={{transitionDelay:'.1s',marginBottom:'3rem'}}>
          <h2 style={{maxWidth:'20ch',fontSize:'2.25rem',fontWeight:600,letterSpacing:'-.02em'}} className="line-clip"><span>Where this is headed</span></h2>
        </div>
        <div className="roadmap-timeline">{phases.map((p,i) => <Phase key={i} phase={p}/>)}</div>
      </div>
    </section>
  )
}