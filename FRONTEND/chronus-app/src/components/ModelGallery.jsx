import { useEffect, useState } from 'react'
import { api } from '../api'
import { navigate } from '../router'
import { Emblem } from './Emblems'
import useScrollReveal from './useScrollReveal'
import { useT } from '../i18n'
import './gallery.css'

// Shown until the server answers (or if it's offline), so the section is
// never empty. Same models as CHRONUS/models/.
const FALLBACK = [
  { id: 'elon_musk', name: 'Elon Musk', description: 'Built from his public interviews, about 10,000 tweets and two biographies.' },
  { id: 'albert_einstein', name: 'Albert Einstein', description: 'Physicist (1879-1955). Built from Relativity and his essays.' },
  { id: 'marie_curie', name: 'Marie Curie', description: 'Physicist and chemist (1867-1934). Built from her biography of Pierre Curie.' },
  { id: 'nikola_tesla', name: 'Nikola Tesla', description: 'Inventor (1856-1943). Built from his 1892 lecture on alternating currents.' },
  { id: 'mahatma_gandhi', name: 'Mahatma Gandhi', description: "Leader of India's independence movement (1869-1948). Built from Hind Swaraj and more." },
  { id: 'abraham_lincoln', name: 'Abraham Lincoln', description: '16th President of the United States (1809-1865). Built from his speeches and letters.' },
  { id: 'marcus_aurelius', name: 'Marcus Aurelius', description: 'Roman emperor and Stoic philosopher (121-180 AD). Built from his Meditations.' },
  { id: 'william_shakespeare', name: 'William Shakespeare', description: 'Playwright and poet (1564-1616). Built from his 154 sonnets.' },
]

// Warm, distinct backdrops per model
const TONES = {
  elon_musk: ['#1d2433', '#3b4a66'], albert_einstein: ['#2a2238', '#5b4a7a'], marie_curie: ['#16302b', '#2f6157'],
  nikola_tesla: ['#1b2440', '#3a56a0'], mahatma_gandhi: ['#3d2a12', '#9a6a2c'], abraham_lincoln: ['#2b2b2b', '#5d5148'],
  marcus_aurelius: ['#3a1f14', '#8d4a2b'], william_shakespeare: ['#2a1d2f', '#6e4560'],
}

function Card({ persona, index }) {
  const t = useT()
  const [ref, inView] = useScrollReveal(0.15)
  const [from, to] = TONES[persona.id] || ['#2a2522', '#6a4a35']
  const first = persona.name.split(' ')[0]
  return (
    <button ref={ref} className={`gallery-card ${inView ? 'in-view' : ''}`} style={{ transitionDelay: `${(index % 4) * 70}ms` }}
      onClick={() => navigate(`/chat/${persona.id}`)} aria-label={t('create.chatWith', { name: persona.name })}>
      <div className="gallery-art" style={{ background: `radial-gradient(circle at 70% 25%, ${to}, ${from} 70%)` }}>
        <span className="gallery-emblem"><Emblem id={persona.id} name={persona.name} /></span>
        {persona.memories > 0 && <span className="gallery-count">{t('common.memories', { count: persona.memories.toLocaleString() })}</span>}
      </div>
      <div className="gallery-text">
        <h3>{persona.name}</h3>
        <p>{persona.description}</p>
        <span className="gallery-cta">{t('gallery.ask', { name: first })}</span>
      </div>
    </button>
  )
}

export default function ModelGallery() {
  const t = useT()
  const [models, setModels] = useState(FALLBACK)
  const [hRef, hIn] = useScrollReveal()

  useEffect(() => {
    api.personas()
      .then(list => {
        const ready = list.filter(p => p.kind === 'pretrained' && p.status === 'ready')
        if (ready.length) setModels(ready.sort((a, b) => (a.id === 'elon_musk' ? -1 : b.id === 'elon_musk' ? 1 : a.name.localeCompare(b.name))))
      })
      .catch(() => {})
  }, [])

  return (
    <section className="gallery-section" id="gallery">
      <div className="shell gallery-inner">
        <div ref={hRef} className={`gallery-header sr ${hIn ? 'in-view' : ''}`}>
          <div>
            <div className="eyebrow eyebrow--accent">{t('gallery.eyebrow')}</div>
            <h2 className="gallery-h2">{t('gallery.title')}</h2>
          </div>
          <p>{t('gallery.intro')}</p>
        </div>
        <div className="gallery-grid">
          {models.map((p, i) => <Card key={p.id} persona={p} index={i} />)}
        </div>
        <div className="gallery-more">
          <button className="pill-btn pill-btn--outline" onClick={() => navigate('/models')}><span className="pill-inner">{t('gallery.more')}</span></button>
        </div>
      </div>
    </section>
  )
}
