import { useEffect, useState } from 'react'
import { api } from '../api'
import { useT } from '../i18n'

// "About this model": what it's built from and how careful it is.
export default function AboutModel({ personaId }) {
  const t = useT()
  const [about, setAbout] = useState(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open || about) return
    api.about(personaId).then(setAbout).catch(e => setError(e.message))
  }, [open, about, personaId])

  return (
    <details className="about-model" onToggle={e => setOpen(e.currentTarget.open)}>
      <summary>{t('about.title')}</summary>
      {error && <div className="page-alert">{error}</div>}
      {!about && !error && <p className="page-note">{t('common.loading')}</p>}
      {about && (
        <div className="about-grid">
          <div>
            <h3>{t('common.memories', { count: about.memories.toLocaleString() })}</h3>
            <ul className="about-list">
              {Object.entries(about.by_voice).sort((a, b) => b[1] - a[1]).map(([voice, n]) => (
                <li key={voice}><span className={`demo-voice demo-voice--${voice}`}>{t.label('aboutVoices', voice)}</span> {n.toLocaleString()}</li>
              ))}
            </ul>
            {about.years && <p className="page-note">{t('about.span', { first: about.years.first, last: about.years.last })}</p>}
          </div>
          <div>
            <h3>{t('about.sources')}</h3>
            <ul className="about-list">
              {about.top_sources.map(s => <li key={s.source_file}><span className="about-file">{s.source_file === 'interview_protocol' ? t('about.interview') : s.source_file}</span> {s.memories.toLocaleString()}</li>)}
            </ul>
            {about.sources?.length > 0 && (
              <p className="page-note">{t('about.texts')} {about.sources.map((s, i) => (
                <span key={s.url || s.title}>{i > 0 && ', '}{s.url ? <a className="page-link" href={s.url} target="_blank" rel="noreferrer">{s.title}</a> : s.title}</span>
              ))}{about.license && ` · ${about.license}`}</p>
            )}
          </div>
          <div>
            <h3>{t('about.careful')}</h3>
            <p className="page-note">{t('about.threshold', { pct: Math.round((1 - about.threshold) * 100) })}</p>
            {about.kind === 'custom' && (
              <>
                <p className="page-note">{t('about.consent', { date: new Date(about.consent_given_at).toLocaleDateString(), statement: about.consent_statement })}</p>
                <p className="page-note">{about.allow_cloud_llm ? t('about.aiOn') : t('about.aiOff')}{about.memorial ? ` ${t('about.memorial')}` : ''}</p>
              </>
            )}
          </div>
        </div>
      )}
    </details>
  )
}
