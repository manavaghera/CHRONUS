import useScrollReveal from './useScrollReveal'

const items = [
  { text: 'Remember', variant: 'light' },
  { text: 'Protect', variant: 'accent' },
  { icon: true, variant: 'dark' },
  { text: 'Honor', variant: 'ghost' },
]

// One component per tile: hooks can't be called inside .map()
function BandItem({ item, index }) {
  const [ref, inView] = useScrollReveal(0.15)
  return (
    <li ref={ref} className={`band-item ${inView ? 'in-view' : ''}`} style={{ transitionDelay: index * 120 + 'ms' }}>
      <div className={`band-tile band--${item.variant}`}>
        {item.icon ? <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg> : item.text}
      </div>
    </li>
  )
}

export default function Band() {
  return (
    <section className="band" style={{ position: 'relative', zIndex: 10 }}>
      <ul className="shell band-list">
        {items.map((item, i) => <BandItem key={i} item={item} index={i} />)}
      </ul>
    </section>
  )
}
