import useScrollReveal from './useScrollReveal'

const steps = [
  {
    num: '01',
    title: 'Upload Your Data',
    desc: 'Feed CHRONUS everything — voice recordings, journals, documents, transcripts, notes. Any format your knowledge lives in. The richer the input, the deeper the intelligence.',
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>,
  },
  {
    num: '02',
    title: 'Semantic Processing',
    desc: 'Our engine parses and structures your data — extracting meaning, relationships, and patterns that define how you think.',
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>,
  },
  {
    num: '03',
    title: 'Build Your Personal Intelligence Model',
    desc: 'CHRONUS trains a model on your unique knowledge graph — not generic internet data. The result is a version of your expertise that reasons, recalls, and responds exactly as you would.',
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>,
  },
  {
    num: '04',
    title: 'Ask Anything',
    desc: 'Query your model with natural language. Get answers grounded in your actual knowledge — with full source attribution.',
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>,
  },
  {
    num: '05',
    title: 'Get Voice & Text Responses',
    desc: 'Receive answers in the original voice of the preserved intelligence — not a generic AI voice. Every response carries the cadence, tone, and expression of the real person. Knowledge, exactly as it sounded.',
    icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/><path d="M19 10v2a7 7 0 01-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>,
  },
]

function StepCard({ step, index }) {
  const [ref, inView] = useScrollReveal(0.15)
  const isWide = index === 2

  return (
    <div
      ref={ref}
      className={`five-step-card ${isWide ? 'five-step-card--wide' : ''} ${inView ? 'in-view' : ''}`}
      style={{ transitionDelay: `${index * 80}ms` }}
    >
      <div className="five-step-num">{step.num}</div>
      <div className="five-step-icon">{step.icon}</div>
      <h3>{step.title}</h3>
      <p>{step.desc}</p>
    </div>
  )
}

export default function FiveSteps() {
  const [hRef, hIn] = useScrollReveal()

  return (
    <section className="five-section" id="five-steps">
      <div className="shell five-inner">
        <div ref={hRef} className={`five-header sr ${hIn ? 'in-view' : ''}`}>
          <div className="eyebrow eyebrow--dark">HOW IT WORKS</div>
          <h2 className="five-h2">Five steps to immortalize intelligence</h2>
          <p className="five-sub">From raw data to a living, breathing AI — here's how CHRONUS turns human knowledge into something that lasts forever.</p>
        </div>
        <div className="five-grid">
          {steps.map((step, i) => (
            <StepCard key={i} step={step} index={i} />
          ))}
        </div>
      </div>
    </section>
  )
}