import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { navigate } from '../router'
import { SPARK } from '../components/ChatPanel'

// Planned pretrained models from the CHRONUS report (section 6.9). Not built
// in this repo yet, so they're shown as planned rather than as live models.
const PLANNED = [
  ['Albert Einstein', 'Letters, essays and lectures'],
  ['Mahatma Gandhi', 'Speeches, letters and his autobiography'],
  ['Nikola Tesla', 'Articles, patents and interviews'],
  ['Marcus Aurelius', 'Meditations'],
  ['Steve Jobs', 'Keynotes and interviews'],
  ['Marie Curie', 'Letters and scientific writing'],
  ['Abraham Lincoln', 'Speeches and letters'],
  ['William Shakespeare', 'Plays and sonnets'],
]

const ARROW = <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 17 17 7M8 7h9v9"/></svg>

function ModelCard({ persona, onDelete }) {
  const ready = persona.status === 'ready'
  return (
    <article className="model-card">
      <div className="model-card-top">
        <div className="demo-avatar">{SPARK}</div>
        <span className={`model-status model-status--${ready ? 'ready' : 'draft'}`}>{ready ? 'Ready' : 'Draft'}</span>
      </div>
      <h3>{persona.name}</h3>
      {persona.description && <p>{persona.description}</p>}
      <div className="model-meta">
        <span>{persona.memories.toLocaleString()} memories</span>
        {persona.kind === 'custom' && <span>{persona.interview_answered.length}/25 interview</span>}
        {persona.kind === 'custom' && !persona.allow_cloud_llm && <span title="Answers use verbatim quotes only; nothing is sent to a cloud AI">Local only</span>}
      </div>
      <div className="model-actions">
        {ready && <button className="pill-btn pill-btn--dark" onClick={() => navigate(`/chat/${persona.id}`)}><span className="pill-inner">Chat</span></button>}
        {persona.kind === 'custom' && (
          <button className="pill-btn pill-btn--outline" onClick={() => navigate(`/create/${persona.id}`)}>
            <span className="pill-inner">{ready ? 'Add memories' : 'Continue building'}</span>
          </button>
        )}
        {onDelete && <button className="model-delete" onClick={() => onDelete(persona)}>Delete</button>}
      </div>
    </article>
  )
}

export default function ModelsPage() {
  const [personas, setPersonas] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    api.personas().then(p => { setPersonas(p); setError('') }).catch(e => setError(e.message))
  }, [])
  useEffect(load, [load])

  const remove = async (persona) => {
    const ok = window.confirm(`Delete ${persona.name} permanently?\n\nThis removes every uploaded document, interview answer and memory of this model. It can't be undone.`)
    if (!ok) return
    try { await api.deletePersona(persona.id); load() } catch (e) { setError(e.message) }
  }

  const pretrained = (personas || []).filter(p => p.kind === 'pretrained')
  const custom = (personas || []).filter(p => p.kind === 'custom')

  return (
    <div className="page">
      <section className="page-hero shell">
        <div className="eyebrow eyebrow--accent">Models</div>
        <h1 className="page-h1">Talk to a preserved mind</h1>
        <p className="page-sub">Pretrained models built from public archives, and private models you build yourself from letters, journals and interviews. Every answer cites the memory it came from.</p>
        <button className="pill-btn pill-btn--accent pill-btn--with-arrow" onClick={() => navigate('/create')}>
          <span className="pill-inner">Create your own model<span className="pill-badge pill-arrow-upright">{ARROW}</span></span>
        </button>
      </section>

      {error && <div className="shell"><div className="page-alert">{error}</div></div>}

      <section className="shell page-section">
        <h2 className="page-h2">Pretrained models</h2>
        <div className="model-grid">
          {personas === null && !error && <div className="model-card model-card--loading">Loading models…</div>}
          {pretrained.map(p => <ModelCard key={p.id} persona={p} />)}
        </div>
      </section>

      <section className="shell page-section">
        <h2 className="page-h2">Planned</h2>
        <p className="page-note">From the CHRONUS research roadmap. These need their public archives collected and cleaned before they can be built.</p>
        <div className="model-grid">
          {PLANNED.map(([name, note]) => (
            <article key={name} className="model-card model-card--planned">
              <div className="model-card-top"><div className="demo-avatar">{SPARK}</div><span className="model-status">Planned</span></div>
              <h3>{name}</h3>
              <p>{note}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="shell page-section">
        <h2 className="page-h2">Your models</h2>
        <p className="page-note">Private models stay on this computer. Deleting one removes all of its data.</p>
        <div className="model-grid">
          {custom.map(p => <ModelCard key={p.id} persona={p} onDelete={remove} />)}
          {personas !== null && custom.length === 0 && (
            <article className="model-card model-card--empty">
              <h3>No custom models yet</h3>
              <p>Build one from someone's letters, journals and interview answers, with their consent.</p>
              <div className="model-actions">
                <button className="pill-btn pill-btn--dark" onClick={() => navigate('/create')}><span className="pill-inner">Create a model</span></button>
              </div>
            </article>
          )}
        </div>
      </section>
    </div>
  )
}
