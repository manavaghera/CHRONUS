import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { navigate } from '../router'
import SourceViewer from '../components/chat/SourceViewer'
import { Emblem } from '../components/Emblems'
import { DeletedMemories, VersionList } from '../components/MemoryHistory'
import { useT } from '../i18n'

const PAGE = 20

function MemoryCard({ item, personaId, onChanged, onOpen }) {
  const t = useT()
  const [editing, setEditing] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [text, setText] = useState(item.text)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const save = async () => {
    setBusy(true); setError('')
    try { onChanged(await api.editMemory(personaId, item.id, text)); setEditing(false) } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  const remove = async () => {
    if (!window.confirm(t('mem.deleteConfirm'))) return
    setBusy(true); setError('')
    try { await api.deleteMemory(personaId, item.id); onChanged(null) } catch (e) { setError(e.message); setBusy(false) }
  }
  // Kept in the archive, but never quoted in an answer (services/consent.py)
  const toggleNeverQuote = async () => {
    setBusy(true); setError('')
    try { onChanged(await api.neverQuote(personaId, item.id, !item.never_quote)) } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <article className="mem-card">
      <div className="mem-top">
        <span className={`demo-voice demo-voice--${item.voice}`}>{t.label('voices', item.voice)}</span>
        <span className="mem-cite">{item.citation}</span>
        {item.distance != null && <span className="mem-match">{t('chat.match', { pct: Math.max(0, Math.round((1 - item.distance) * 100)) })}</span>}
        {item.edited_at && <span className="mem-edited">{t('mem.edited')}</span>}
        {item.never_quote && <span className="mem-edited">{t('mem.neverQuoted')}</span>}
      </div>
      {editing ? (
        <textarea className="create-select" rows={5} maxLength={4000} value={text} onChange={e => setText(e.target.value)} />
      ) : (
        <p className="mem-text">{item.text}</p>
      )}
      {error && <div className="page-alert">{error}</div>}
      <div className="mem-actions">
        <button className="page-link" onClick={() => onOpen(item)}>{t('chat.viewInContext')}</button>
        {item.editable && !editing && <button className="page-link" onClick={() => setEditing(true)}>{t('mem.edit')}</button>}
        {item.editable && !editing && <button className="page-link" onClick={() => setShowHistory(h => !h)}>{showHistory ? t('mem.hideHistory') : t('mem.history')}</button>}
        {item.editable && !editing && (
          <button className="page-link" disabled={busy} onClick={toggleNeverQuote}>{item.never_quote ? t('mem.allowQuoting') : t('mem.neverQuote')}</button>
        )}
        {editing && <button className="demo-quick-btn" disabled={busy || text.trim().length < 3} onClick={save}>{busy ? t('iv.saving') : t('iv.save')}</button>}
        {editing && <button className="demo-quick-btn" onClick={() => { setEditing(false); setText(item.text) }}>{t('common.cancel')}</button>}
        {item.editable && !editing && <button className="model-delete" disabled={busy} onClick={remove}>{t('mem.delete')}</button>}
      </div>
      {showHistory && <VersionList personaId={personaId} memoryId={item.id} onRestored={(restored) => { onChanged(restored); setShowHistory(false) }} />}
    </article>
  )
}

export default function MemoriesPage({ id }) {
  const t = useT()
  const [persona, setPersona] = useState(null)
  const [query, setQuery] = useState('')
  const [applied, setApplied] = useState('')
  const [source, setSource] = useState('')
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [viewer, setViewer] = useState(null)
  const [changes, setChanges] = useState(0)  // refreshes the deleted list

  const loadPersona = useCallback(() => api.persona(id).then(setPersona).catch(e => setError(e.message)), [id])
  useEffect(() => { loadPersona() }, [loadPersona])

  const load = useCallback(async (offset = 0) => {
    setLoading(true); setError('')
    try {
      const params = { limit: PAGE, offset, ...(applied ? { q: applied } : {}), ...(source ? { source } : {}) }
      const page = await api.memories(id, params)
      setItems(prev => (offset ? [...prev, ...page.items] : page.items))
      setTotal(page.total)
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }, [id, applied, source])
  useEffect(() => { load(0) }, [load])

  const removeDoc = async (filename) => {
    if (!window.confirm(t('mem.removeConfirm', { file: filename }))) return
    try { await api.deleteDocument(id, filename); loadPersona(); load(0) } catch (e) { setError(e.message) }
  }

  const custom = persona?.kind === 'custom'
  const sources = custom ? [...persona.uploads.map(u => u.filename), 'interview_protocol', 'reviewed_answers'] : []

  return (
    <div className="page">
      <section className="page-hero page-hero--compact shell">
        <button className="page-back" onClick={() => navigate(persona ? `/chat/${persona.id}` : '/models')}>{t('mem.back')}</button>
        <div className="eyebrow eyebrow--accent">{t('mem.eyebrow')}</div>
        <h1 className="page-h1 mem-h1">
          {persona && <span className="model-emblem"><Emblem id={persona.id} name={persona.name} /></span>}
          {persona ? t('mem.knows', { name: persona.name }) : t('mem.eyebrow')}
        </h1>
        <p className="page-sub">{t('mem.sub')} {custom ? t('mem.subCustom') : t('mem.subPretrained')}</p>
      </section>

      <section className="shell page-section mem-layout">
        <form className="mem-filters" onSubmit={e => { e.preventDefault(); setApplied(query.trim()) }}>
          <input className="create-select" type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder={t('mem.search')} />
          {sources.length > 0 && (
            <select className="create-select" value={source} onChange={e => setSource(e.target.value)} aria-label={t('mem.source')}>
              <option value="">{t('mem.allSources')}</option>
              {sources.map(s => <option key={s} value={s}>{s === 'interview_protocol' ? t('about.interview') : s === 'reviewed_answers' ? t('mem.reviewed') : s}</option>)}
            </select>
          )}
          <button className="pill-btn pill-btn--dark"><span className="pill-inner">{t('mem.searchBtn')}</span></button>
          {applied && <button type="button" className="demo-quick-btn" onClick={() => { setQuery(''); setApplied('') }}>{t('mem.clear')}</button>}
        </form>
        <p className="page-note">{loading ? t('common.loading') : applied ? t('mem.closest', { count: total.toLocaleString(), query: applied }) : t('common.memories', { count: total.toLocaleString() })}</p>
        {error && <div className="page-alert">{error}</div>}

        {custom && persona.uploads.length > 0 && (
          <details className="create-card mem-docs">
            <summary>{t('mem.docs', { count: persona.uploads.length })}</summary>
            <ul className="create-list">
              {persona.uploads.map(u => (
                <li key={u.filename}>
                  <span>{u.filename}</span>
                  <span>{t('common.memories', { count: u.memories })} <button className="model-delete" onClick={() => removeDoc(u.filename)}>{t('mem.remove')}</button></span>
                </li>
              ))}
            </ul>
          </details>
        )}

        {custom && <DeletedMemories personaId={id} refreshKey={changes} onRestored={() => { setChanges(n => n + 1); load(0) }} />}

        <div className="mem-list">
          {items.map(item => (
            <MemoryCard key={item.id} item={item} personaId={id} onOpen={setViewer}
              onChanged={(updated) => { setChanges(n => n + 1); setItems(list => (updated ? list.map(x => (x.id === updated.id ? { ...x, ...updated } : x)) : list.filter(x => x.id !== item.id))) }} />
          ))}
        </div>
        {items.length < total && (
          <button className="pill-btn pill-btn--outline mem-more" disabled={loading} onClick={() => load(items.length)}>
            <span className="pill-inner">{loading ? t('common.loading') : t('mem.more')}</span>
          </button>
        )}
      </section>
      {viewer && (
        <SourceViewer personaId={id} index={0} onClose={() => setViewer(null)}
          source={{ memory_id: viewer.id, citation: viewer.citation, voice: viewer.voice, quote: viewer.text, distance: viewer.distance }} />
      )}
    </div>
  )
}
