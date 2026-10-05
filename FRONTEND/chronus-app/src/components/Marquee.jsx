export default function Marquee() {
  const items = ['Consent-first','Human-reviewed','Nothing invented','Source-cited','Privacy-preserving','Not a resurrection','A remembering']
  const doubled = [...items, ...items]
  return (
    <section className="marquee-section" aria-hidden="true">
      <div className="marquee-track">
        {doubled.map((t, i) => <span key={i} className="marquee-item"><span className="mq-dot"/>{t}</span>)}
      </div>
    </section>
  )
}