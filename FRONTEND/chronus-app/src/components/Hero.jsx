import { useEffect, useState } from 'react'
import { api } from '../api'
import { navigate } from '../router'
import MemoryField from './MemoryField'
import AnswerPreview from './AnswerPreview'
import './hero.css'

// What CHRONUS actually runs on (see CHRONUS/requirements.txt)
const BUILT_ON = ['Sentence-BERT', 'ChromaDB', 'FastAPI', 'React', 'Kokoro TTS', 'Qwen2.5 + LoRA']

const ARROW = <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 17 17 7M8 7h9v9" /></svg>

// Live numbers from the server; hidden while it's offline rather than guessed
function useArchiveStats() {
  const [stats, setStats] = useState(null)
  useEffect(() => {
    let cancelled = false
    api.personas().then(list => {
      if (cancelled) return
      const ready = list.filter(p => p.status === 'ready')
      setStats({ models: ready.length, memories: ready.reduce((n, p) => n + (p.memories || 0), 0) })
    }).catch(() => {})
    return () => { cancelled = true }
  }, [])
  return stats
}

export default function Hero({ scrollToId }) {
  const stats = useArchiveStats()
  return (
    <section id="home" className="hero">
      <div className="hero-bg" aria-hidden="true" />
      <MemoryField />
      <div className="hero-watermark" aria-hidden="true">CHRONUS</div>

      <div className="shell hero-content">
        <div className="hero-left">
          <div className="hero-eyebrow">Memory, not mimicry</div>
          <h1 className="hero-h1">
            <span className="line-clip hero-line"><span>Their words.</span></span>
            <span className="line-clip hero-line"><span style={{ transitionDelay: '.12s' }}>Their voice.</span></span>
            <span className="line-clip hero-line"><span style={{ transitionDelay: '.24s' }} className="hero-h1-accent">Never invented.</span></span>
          </h1>
          <p className="hero-sub">
            CHRONUS answers in a person's own words, drawn from their interviews, letters and books.
            Every reply shows its source, and when the archive is silent, it says so.
          </p>
          <div className="hero-ctas">
            <button className="pill-btn pill-btn--dark pill-btn--with-arrow" onClick={() => navigate('/create')}>
              <span className="pill-inner">Create a model with consent<span className="pill-badge pill-arrow-upright">{ARROW}</span></span>
            </button>
            <button className="pill-btn pill-btn--outline" onClick={() => scrollToId('demo')}><span className="pill-inner">Try the live demo</span></button>
          </div>
          <ul className="hero-facts">
            {stats && <li><strong>{stats.models}</strong> models ready to talk to</li>}
            {stats && <li><strong>{stats.memories.toLocaleString()}</strong> source-tagged memories</li>}
            <li>Every factual answer cites its source, or says “I don't know”</li>
          </ul>
        </div>

        <div className="hero-right">
          <AnswerPreview />
          <div className="hero-built">
            <span>Built on</span>
            <ul>{BUILT_ON.map(n => <li key={n}>{n}</li>)}</ul>
          </div>
        </div>
      </div>

      <div className="hero-status">
        <div className="shell hero-status-inner">
          <span>Research since 2024</span>
          <span className="status-center">Parul University — B.Tech Project</span>
          <button onClick={() => scrollToId('demo')}>Scroll to explore &darr;</button>
        </div>
      </div>
    </section>
  )
}
