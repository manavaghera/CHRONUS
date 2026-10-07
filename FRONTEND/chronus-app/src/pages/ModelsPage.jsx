import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { navigate } from '../router'
import { Emblem } from '../components/Emblems'
import { useT } from '../i18n'
import '../components/gallery.css'

// Famous-figure models from the CHRONUS report (section 6.9). Ones the
// backend has built (CHRONUS/figures/build_figures.py) are listed as live
// models; the rest stay here as planned.
const PLANNED = [
  ['Albert Einstein', 'planned.einstein'],
  ['Mahatma Gandhi', 'planned.gandhi'],
  ['Nikola Tesla', 'planned.tesla'],
  ['Marcus Aurelius', 'planned.aurelius'],
  ['Steve Jobs', 'planned.jobs'],
  ['Marie Curie', 'planned.curie'],
  ['Abraham Lincoln', 'planned.lincoln'],
  ['William Shakespeare', 'planned.shakespeare'],
]

const ARROW = <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 17 17 7M8 7h9v9"/></svg>

function ModelCard({ persona, onDelete }) {
  const t = useT()
  const ready = persona.status === 'ready'
  return (
    <article className="model-card">
      <div className="model-card-top">
        <div className="model-emblem"><Emblem id={persona.id} name={persona.name} /></div>
        <span className={`model-status model-status--${ready ? 'ready' : 'draft'}`}>{ready ? t('models.ready') : t('models.draft')}</span>
      </div>
      <h3>{persona.name}</h3>
      {persona.description && <p>{persona.description}</p>}
      <div className="model-meta">
        <span>{t('common.memories', { count: persona.memories.toLocaleString() })}</span>
        {persona.kind === 'custom' && <span>{t('models.interview', { count: persona.interview_answered.length })}</span>}
        {persona.kind === 'custom' && !persona.allow_cloud_llm && <span title={t('models.localOnlyTip')}>{t('models.localOnly')}</span>}
        {persona.memorial && <span title={t('models.inMemoryTip')}>{t('models.inMemory')}</span>}
        {persona.license && <span title={persona.sources.map(s => s.title).join(', ')}>{persona.license.split(' (')[0]}</span>}
      </div>
      <div className="model-actions">
        {ready && <button className="pill-btn pill-btn--dark" onClick={() => navigate(`/chat/${persona.id}`)}><span className="pill-inner">{t('models.chat')}</span></button>}
        <button className="page-link" onClick={() => navigate(`/memories/${persona.id}`)}>{t('models.memories')}</button>
        {persona.kind === 'custom' && (
          <button className="pill-btn pill-btn--outline" onClick={() => navigate(`/create/${persona.id}`)}>
            <span className="pill-inner">{ready ? t('models.addMemories') : t('models.continue')}</span>
          </button>
        )}
        {onDelete && <button className="model-delete" onClick={() => onDelete(persona)}>{t('mem.delete')}</button>}
      </div>
    </article>
  )
}

function ImportCard({ onImported }) {
  const t = useT()
  const [file, setFile] = useState(null)
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try { const p = await api.importModel(file, password); setFile(null); setPassword(''); onImported(p) }
    catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return (
    <form className="model-card model-card--empty" onSubmit={submit}>
      <h3>{t('models.importTitle')}</h3>
      <p>{t('models.importText')}</p>
      <label className={`pill-btn pill-btn--outline create-file${busy ? ' is-disabled' : ''}`}>
        <span className="pill-inner">{file ? file.name : t('models.chooseFile')}</span>
        <input type="file" accept=".chronus" disabled={busy} onChange={e => { setFile(e.target.files[0] || null); e.target.value = '' }} />
      </label>
      {file && <input className="create-select" type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} placeholder={t('models.password')} aria-label={t('models.password')} />}
      {error && <div className="page-alert">{error}</div>}
      <div className="model-actions">
        <button className="pill-btn pill-btn--dark" disabled={!file || password.length < 8 || busy}><span className="pill-inner">{busy ? t('models.decrypting') : t('models.import')}</span></button>
      </div>
    </form>
  )
}

export default function ModelsPage() {
  const t = useT()
  const [personas, setPersonas] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    api.personas().then(p => { setPersonas(p); setError('') }).catch(e => setError(e.message))
  }, [])
  useEffect(load, [load])

  const remove = async (persona) => {
    const ok = window.confirm(t('models.deleteConfirm', { name: persona.name }))
    if (!ok) return
    try { await api.deletePersona(persona.id); load() } catch (e) { setError(e.message) }
  }

  const pretrained = (personas || []).filter(p => p.kind === 'pretrained')
  const custom = (personas || []).filter(p => p.kind === 'custom')
  const built = new Set(pretrained.map(p => p.name))
  const planned = PLANNED.filter(([name]) => !built.has(name))

  return (
    <div className="page">
      <section className="page-hero shell">
        <div className="eyebrow eyebrow--accent">{t('nav.models')}</div>
        <h1 className="page-h1">{t('models.title')}</h1>
        <p className="page-sub">{t('models.sub')}</p>
        <button className="pill-btn pill-btn--accent pill-btn--with-arrow" onClick={() => navigate('/create')}>
          <span className="pill-inner">{t('common.createOwn')}<span className="pill-badge pill-arrow-upright">{ARROW}</span></span>
        </button>
      </section>

      {error && <div className="shell"><div className="page-alert">{error}</div></div>}

      <section className="shell page-section">
        <h2 className="page-h2">{t('gallery.eyebrow')}</h2>
        <div className="model-grid">
          {personas === null && !error && <div className="model-card model-card--loading">{t('models.loading')}</div>}
          {pretrained.map(p => <ModelCard key={p.id} persona={p} />)}
        </div>
      </section>

      {planned.length > 0 && <section className="shell page-section">
        <h2 className="page-h2">{t('models.planned')}</h2>
        <p className="page-note">{t('models.plannedNote')}</p>
        <div className="model-grid">
          {planned.map(([name, note]) => (
            <article key={name} className="model-card model-card--planned">
              <div className="model-card-top"><div className="model-emblem"><Emblem id="" name={name} /></div><span className="model-status">{t('models.planned')}</span></div>
              <h3>{name}</h3>
              <p>{t(note)}</p>
            </article>
          ))}
        </div>
      </section>}

      <section className="shell page-section">
        <h2 className="page-h2">{t('models.yours')}</h2>
        <p className="page-note">{t('models.yoursNote')}</p>
        <div className="model-grid">
          {custom.map(p => <ModelCard key={p.id} persona={p} onDelete={remove} />)}
          {personas !== null && <ImportCard onImported={(p) => { load(); navigate(`/create/${p.id}`) }} />}
          {personas !== null && custom.length === 0 && (
            <article className="model-card model-card--empty">
              <h3>{t('models.noneTitle')}</h3>
              <p>{t('models.noneText')}</p>
              <div className="model-actions">
                <button className="pill-btn pill-btn--dark" onClick={() => navigate('/create')}><span className="pill-inner">{t('common.createModel')}</span></button>
              </div>
            </article>
          )}
        </div>
      </section>
    </div>
  )
}
