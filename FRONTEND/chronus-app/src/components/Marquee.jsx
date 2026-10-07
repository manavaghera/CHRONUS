import { useT } from '../i18n'

const ITEMS = ['mq.consent', 'mq.reviewed', 'mq.nothingInvented', 'mq.cited', 'mq.privacy', 'mq.notResurrection', 'mq.remembering']

export default function Marquee() {
  const t = useT()
  const items = ITEMS.map(key => t(key))
  const doubled = [...items, ...items]
  return (
    <section className="marquee-section" aria-hidden="true">
      <div className="marquee-track">
        {doubled.map((t, i) => <span key={i} className="marquee-item"><span className="mq-dot"/>{t}</span>)}
      </div>
    </section>
  )
}