import { useEffect, useState } from 'react'
import { api } from '../api'

const VOICE = { first_person: 'in their own words', third_party: 'written by others', synthesized: 'synthesized summaries' }

// "About this model": what it's built from and how careful it is.
export default function AboutModel({ personaId }) {
  const [about, setAbout] = useState(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open || about) return
    api.about(personaId).then(setAbout).catch(e => setError(e.message))
  }, [open, about, personaId])

  return (
    <details className="about-model" onToggle={e => setOpen(e.currentTarget.open)}>
      <summary>About this model</summary>
      {error && <div className="page-alert">{error}</div>}
      {!about && !error && <p className="page-note">Loading…</p>}
      {about && (
        <div className="about-grid">
          <div>
            <h3>{about.memories.toLocaleString()} memories</h3>
            <ul className="about-list">
              {Object.entries(about.by_voice).sort((a, b) => b[1] - a[1]).map(([voice, n]) => (
                <li key={voice}><span className={`demo-voice demo-voice--${voice}`}>{VOICE[voice] || voice}</span> {n.toLocaleString()}</li>
              ))}
            </ul>
            {about.years && <p className="page-note">Dated memories span {about.years.first}–{about.years.last}.</p>}
          </div>
          <div>
            <h3>Main sources</h3>
            <ul className="about-list">
              {about.top_sources.map(s => <li key={s.source_file}><span className="about-file">{s.source_file === 'interview_protocol' ? 'Interview answers' : s.source_file}</span> {s.memories.toLocaleString()}</li>)}
            </ul>
            {about.sources?.length > 0 && (
              <p className="page-note">Texts: {about.sources.map((s, i) => (
                <span key={s.url || s.title}>{i > 0 && ', '}{s.url ? <a className="page-link" href={s.url} target="_blank" rel="noreferrer">{s.title}</a> : s.title}</span>
              ))}{about.license && ` · ${about.license}`}</p>
            )}
          </div>
          <div>
            <h3>How careful it is</h3>
            <p className="page-note">It answers only when a memory matches the question at least {Math.round((1 - about.threshold) * 100)}%; otherwise it says “I don't know”.</p>
            {about.kind === 'custom' && (
              <>
                <p className="page-note">Consent recorded {new Date(about.consent_given_at).toLocaleDateString()}: “{about.consent_statement}”</p>
                <p className="page-note">AI voice is {about.allow_cloud_llm ? 'on (excerpts are sent to a cloud AI service)' : 'off (verbatim quotes only; nothing leaves this computer)'}.{about.memorial ? ' Memorial mode is on.' : ''}</p>
              </>
            )}
          </div>
        </div>
      )}
    </details>
  )
}
