import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { navigate } from '../router'
import SourceViewer from '../components/chat/SourceViewer'
import { Emblem } from '../components/Emblems'

const PAGE = 20
const VOICE = { first_person: 'own words', third_party: 'written by others', synthesized: 'synthesized' }

function MemoryCard({ item, personaId, onChanged, onOpen }) {
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(item.text)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const save = async () => {
    setBusy(true); setError('')
    try { onChanged(await api.editMemory(personaId, item.id, text)); setEditing(false) } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  const remove = async () => {
    if (!window.confirm('Delete this memory? The model will no longer use it. This cannot be undone.')) return
    setBusy(true); setError('')
    try { await api.deleteMemory(personaId, item.id); onChanged(null) } catch (e) { setError(e.message); setBusy(false) }
  }

  return (
    <article className="mem-card">
      <div className="mem-top">
        <span className={`demo-voice demo-voice--${item.voice}`}>{VOICE[item.voice] || item.voice}</span>
        <span className="mem-cite">{item.citation}</span>
        {item.distance != null && <span className="mem-match">match {Math.max(0, Math.round((1 - item.distance) * 100))}%</span>}
        {item.edited_at && <span className="mem-edited">edited</span>}
      </div>
      {editing ? (
        <textarea className="create-select" rows={5} maxLength={4000} value={text} onChange={e => setText(e.target.value)} />
      ) : (
        <p className="mem-text">{item.text}</p>
      )}
      {error && <div className="page-alert">{error}</div>}
      <div className="mem-actions">
        <button className="page-link" onClick={() => onOpen(item)}>View in context</button>
        {item.editable && !editing && <button className="page-link" onClick={() => setEditing(true)}>Edit</button>}
        {editing && <button className="demo-quick-btn" disabled={busy || text.trim().length < 3} onClick={save}>{busy ? 'Saving…' : 'Save'}</button>}
        {editing && <button className="demo-quick-btn" onClick={() => { setEditing(false); setText(item.text) }}>Cancel</button>}
        {item.editable && !editing && <button className="model-delete" disabled={busy} onClick={remove}>Delete</button>}
      </div>
    </article>
  )
}

export default function MemoriesPage({ id }) {
  const [persona, setPersona] = useState(null)
  const [query, setQuery] = useState('')
  const [applied, setApplied] = useState('')
  const [source, setSource] = useState('')
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [viewer, setViewer] = useState(null)

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
    if (!window.confirm(`Remove ${filename} and every memory made from it?`)) return
    try { await api.deleteDocument(id, filename); loadPersona(); load(0) } catch (e) { setError(e.message) }
  }

  const custom = persona?.kind === 'custom'
  const sources = custom ? [...persona.uploads.map(u => u.filename), 'interview_protocol', 'reviewed_answers'] : []

  return (
    <div className="page">
      <section className="page-hero page-hero--compact shell">
        <button className="page-back" onClick={() => navigate(persona ? `/chat/${persona.id}` : '/models')}>&larr; Back to chat</button>
        <div className="eyebrow eyebrow--accent">Memory browser</div>
        <h1 className="page-h1 mem-h1">
          {persona && <span className="model-emblem"><Emblem id={persona.id} name={persona.name} /></span>}
          {persona ? `What ${persona.name} knows` : 'Memories'}
        </h1>
        <p className="page-sub">
          Every answer is built from these memories and nothing else.
          {custom ? ' Correct a memory, or remove one or a whole document, and the model changes right away.' : ' This model is built from published sources, so its memories are read-only.'}
        </p>
      </section>

      <section className="shell page-section mem-layout">
        <form className="mem-filters" onSubmit={e => { e.preventDefault(); setApplied(query.trim()) }}>
          <input className="create-select" type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search by meaning, e.g. “childhood” or “first factory”" />
          {sources.length > 0 && (
            <select className="create-select" value={source} onChange={e => setSource(e.target.value)} aria-label="Source">
              <option value="">All sources</option>
              {sources.map(s => <option key={s} value={s}>{s === 'interview_protocol' ? 'Interview answers' : s === 'reviewed_answers' ? 'Reviewed answers' : s}</option>)}
            </select>
          )}
          <button className="pill-btn pill-btn--dark"><span className="pill-inner">Search</span></button>
          {applied && <button type="button" className="demo-quick-btn" onClick={() => { setQuery(''); setApplied('') }}>Clear</button>}
        </form>
        <p className="page-note">{loading ? 'Loading…' : applied ? `${total.toLocaleString()} memories, closest to “${applied}” first` : `${total.toLocaleString()} memories`}</p>
        {error && <div className="page-alert">{error}</div>}

        {custom && persona.uploads.length > 0 && (
          <details className="create-card mem-docs">
            <summary>Uploaded documents ({persona.uploads.length})</summary>
            <ul className="create-list">
              {persona.uploads.map(u => (
                <li key={u.filename}>
                  <span>{u.filename}</span>
                  <span>{u.memories} memories <button className="model-delete" onClick={() => removeDoc(u.filename)}>Remove</button></span>
                </li>
              ))}
            </ul>
          </details>
        )}

        <div className="mem-list">
          {items.map(item => (
            <MemoryCard key={item.id} item={item} personaId={id} onOpen={setViewer}
              onChanged={(updated) => setItems(list => (updated ? list.map(x => (x.id === updated.id ? { ...x, ...updated } : x)) : list.filter(x => x.id !== item.id)))} />
          ))}
        </div>
        {items.length < total && (
          <button className="pill-btn pill-btn--outline mem-more" disabled={loading} onClick={() => load(items.length)}>
            <span className="pill-inner">{loading ? 'Loading…' : 'Show more'}</span>
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
