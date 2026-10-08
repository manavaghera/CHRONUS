import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { tx, useLanguage, useT } from '../i18n'
import { initials } from '../lib/data'
import { SplitWords } from '../lib/motion'
import { useToast } from '../lib/toast'
import Icon from '../lib/Icon'
import SourceViewer, { matchPct, VOICES } from '../chat/SourceViewer'

const PAGE = 20
const REPLACED = { edit: tx('edited'), delete: tx('deleted'), restore: tx('replaced by a restore'), never_quote: tx('quoting changed') }
const mark = (v) => `pm${v === 'first_person' ? '' : v === 'synthesized' ? ' dot' : ' dash'}`

// Every version of a memory, the original first, with undo (services/memory_history.py)
function Versions({ personaId, memoryId, onRestored }) {
  const { t, lang } = useLanguage()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { api.memoryHistory(personaId, memoryId).then(setData).catch(e => setError(e.message)) }, [personaId, memoryId])
  if (error) return <div className="alert" role="alert">{error}</div>
  if (!data) return <p className="note row gap8"><span className="spinner" />{t('Loading its history…')}</p>
  return (
    <ol className="versions">
      {data.log && !data.log.ok && <li className="alert">{t('This model’s change log was altered after it was written (entry {n}).', { n: data.log.broken_at })}</li>}
      {data.versions.map(v => (
        <li key={v.version}>
          <span className="lab">{t('Version {n}', { n: v.version })}{v.version === 1 ? ` · ${t('original')}` : ''}{v.current ? ` · ${t('current')}` : ` · ${t(REPLACED[v.replaced_by] || v.replaced_by)} ${v.replaced_at ? new Date(v.replaced_at).toLocaleString(lang) : ''}`}</span>
          <p lang="en">{v.text}</p>
          {!v.current && (
            <button type="button" className="linkbtn" disabled={busy} onClick={async () => {
              setBusy(true)
              try { onRestored(await api.restoreMemory(personaId, memoryId, v.seq)) } catch (e) { setError(e.message) } finally { setBusy(false) }
            }}>{t('Restore this version')}</button>
          )}
        </li>
      ))}
    </ol>
  )
}

function MemoryCard({ item, personaId, onChanged, onOpen }) {
  const t = useT()
  const toast = useToast()
  const [editing, setEditing] = useState(false)
  const [history, setHistory] = useState(false)
  const [text, setText] = useState(item.text)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const run = async (fn, done) => {
    setBusy(true); setError('')
    try { const r = await fn(); onChanged(r); done?.() } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  return (
    <article className={`card mem${item.never_quote ? ' is-muted' : ''}`}>
      <div className="row wrap-row gap8">
        <span className="prov"><i className={mark(item.voice)} />{t(VOICES[item.voice] || item.voice)}</span>
        <span className="lab ell" style={{ flex: 1 }} lang="en">{item.citation}</span>
        {item.distance != null && <span className="badge">{t('Match {pct}%', { pct: matchPct(item.distance) })}</span>}
        {item.edited_at && <span className="badge">{t('Edited')}</span>}
        {item.never_quote && <span className="badge acc">{t('Never quoted')}</span>}
      </div>
      {editing
        ? <textarea className="field" rows={5} maxLength={4000} value={text} onChange={e => setText(e.target.value)} aria-label={t('Memory text')} />
        : <p className="mem-text" lang="en">{item.text}</p>}
      {error && <div className="alert" role="alert">{error}</div>}
      <div className="mem-actions">
        <button type="button" className="mact" onClick={() => onOpen(item)}><Icon name="doc" size={14} />{t('View in context')}</button>
        {item.editable && !editing && <>
          <button type="button" className="mact" onClick={() => setEditing(true)}><Icon name="file" size={14} />{t('Edit')}</button>
          <button type="button" className={`mact${history ? ' is-on' : ''}`} onClick={() => setHistory(h => !h)}><Icon name="clock" size={14} />{t('History')}</button>
          <button type="button" className="mact" disabled={busy} onClick={() => run(() => api.neverQuote(personaId, item.id, !item.never_quote))}
            title={t('Kept in the archive, but never quoted in an answer')}><Icon name={item.never_quote ? 'check' : 'slash'} size={14} />{item.never_quote ? t('Allow quoting') : t('Never quote')}</button>
          <button type="button" className="mact danger" disabled={busy} onClick={() => {
            if (!window.confirm(t('Delete this memory? The model will no longer use it. You can restore it from “Recently deleted”.'))) return
            run(async () => { await api.deleteMemory(personaId, item.id); toast(t('Memory deleted')); return null })
          }}><Icon name="trash" size={14} />{t('Delete')}</button>
        </>}
        {editing && <>
          <button type="button" className="btn btn-p btn-sm" disabled={busy || text.trim().length < 3} onClick={() => run(() => api.editMemory(personaId, item.id, text), () => { setEditing(false); toast(t('Memory updated')) })}>{busy ? t('Saving…') : t('Save')}</button>
          <button type="button" className="btn btn-s btn-sm" onClick={() => { setEditing(false); setText(item.text) }}>{t('Cancel')}</button>
        </>}
      </div>
      {history && <Versions personaId={personaId} memoryId={item.id} onRestored={(r) => { onChanged(r); setHistory(false); toast(t('Version restored')) }} />}
    </article>
  )
}

function Deleted({ personaId, refresh, onRestored }) {
  const { t, lang } = useLanguage()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api.history(personaId).then(setData).catch(e => setError(e.message)) }, [personaId, refresh])
  if (error) return <div className="alert" role="alert">{error}</div>
  if (!data || (!data.deleted.length && data.log.ok)) return null
  return (
    <details className="card mem-box">
      <summary><Icon name="trash" size={15} />{t('Recently deleted')} <span className="badge">{data.deleted.length}</span></summary>
      {!data.log.ok && <div className="alert">{t('This model’s change log was altered after it was written (entry {n}).', { n: data.log.broken_at })}</div>}
      <ul>{data.deleted.map(item => (
        <li key={item.memory_id} className="mem-row">
          <span className="small" lang="en">{item.text.slice(0, 160)}{item.text.length > 160 ? '…' : ''}</span>
          <span className="row gap8"><span className="lab">{item.deleted_at ? new Date(item.deleted_at).toLocaleString(lang) : ''}</span>
            <button type="button" className="linkbtn" onClick={async () => { try { await api.restoreMemory(personaId, item.memory_id, item.seq); onRestored() } catch (e) { setError(e.message) } }}>{t('Restore')}</button></span>
        </li>
      ))}</ul>
    </details>
  )
}

export default function MemoriesPage({ id }) {
  const t = useT()
  const toast = useToast()
  const [persona, setPersona] = useState(null)
  const [query, setQuery] = useState('')
  const [applied, setApplied] = useState('')
  const [source, setSource] = useState('')
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [viewer, setViewer] = useState(null)
  const [changes, setChanges] = useState(0)

  const loadPersona = useCallback(() => api.persona(id).then(setPersona).catch(e => setError(e.message)), [id])
  useEffect(() => { loadPersona() }, [loadPersona])
  const load = useCallback(async (offset = 0) => {
    setLoading(true); setError('')
    try {
      const page = await api.memories(id, { limit: PAGE, offset, ...(applied ? { q: applied } : {}), ...(source ? { source } : {}) })
      setItems(prev => (offset ? [...prev, ...page.items] : page.items)); setTotal(page.total)
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }, [id, applied, source])
  useEffect(() => { load(0) }, [load])

  const custom = persona?.kind === 'custom'
  const sources = custom ? [...persona.uploads.map(u => [u.filename, u.filename]), ['interview_protocol', t('Interview answers')], ['reviewed_answers', t('Reviewed answers')]] : []
  const removeDoc = async (filename) => {
    if (!window.confirm(t('Remove {file} and every memory made from it?', { file: filename }))) return
    try { await api.deleteDocument(id, filename); toast(t('{file} removed', { file: filename })); loadPersona(); load(0) } catch (e) { setError(e.message) }
  }

  return (
    <div className="page">
      <section className="page-hero">
        <div className="page-hero-bg" aria-hidden="true" />
        <div className="wrap">
          <nav className="crumbs" aria-label={t('Breadcrumb')}><a href="#/">{t('Home')}</a><span aria-hidden="true">/</span><a href="#/models">{t('Your models')}</a><span aria-hidden="true">/</span><span>{t('Memories')}</span></nav>
          <div className="row gap16 wrap-row">
            {persona && <span className="av">{initials(persona.name)}</span>}
            <SplitWords as="h1" className="h1 h1-sm" text={persona ? t('What {name}', { name: persona.name }) : t('What this model')} em={t('remembers.')} />
          </div>
          <p className="lede">{t('Every answer is built from these memories and nothing else.')} {custom ? t('Correct one, keep one but never quote it, or remove a whole document, and the model changes right away.') : t('This model is built from published sources, so its memories are read-only.')}</p>
          {persona && <div className="row wrap-row gap8">
            {persona.status === 'ready' && <a className="btn btn-a btn-sm" href={`#/chat/${id}`}>{t('Talk to {name}', { name: persona.name.split(' ')[0] })}</a>}
            <a className="btn btn-s btn-sm" href={`#/insights/${id}`}>{t('Insights')}</a>
            {custom && <a className="btn btn-s btn-sm" href={`#/create/${id}`}>{t('Add memories')}</a>}
          </div>}
        </div>
      </section>
      <section className="sec" style={{ paddingTop: 16 }}>
        <div className="wrap mem-layout">
          <form className="tbar" onSubmit={e => { e.preventDefault(); setApplied(query.trim()) }}>
            <label className="search" htmlFor="mq"><Icon name="search" size={17} /><span className="sr-only">{t('Search memories by meaning')}</span>
              <input id="mq" type="search" autoComplete="off" placeholder={t('Search by meaning, e.g. “childhood” or “first job”')} value={query} onChange={e => setQuery(e.target.value.slice(0, 200))} /></label>
            {sources.length > 0 && (
              <label className="tchip sel"><span className="sr-only">{t('Source')}</span>
                <select value={source} onChange={e => setSource(e.target.value)}><option value="">{t('All sources')}</option>{sources.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            )}
            <button className="btn btn-p btn-sm">{t('Search')}</button>
            {applied && <button type="button" className="btn btn-s btn-sm" onClick={() => { setQuery(''); setApplied('') }}>{t('Clear')}</button>}
          </form>
          <p className="lab" aria-live="polite">{loading ? t('Loading…') : applied ? t('{n} memories, closest to “{q}” first', { n: total.toLocaleString(), q: applied }) : t('{n} memories', { n: total.toLocaleString() })}</p>
          {error && <div className="alert" role="alert">{error}</div>}
          {custom && persona.uploads.length > 0 && (
            <details className="card mem-box">
              <summary><Icon name="file" size={15} />{t('Uploaded documents')} <span className="badge">{persona.uploads.length}</span></summary>
              <ul>{persona.uploads.map(u => (
                <li key={u.filename} className="mem-row"><span className="small ell">{u.filename}</span>
                  <span className="row gap8"><span className="lab">{t('{n} memories', { n: u.memories })}</span><button type="button" className="linkbtn" onClick={() => removeDoc(u.filename)}>{t('Remove')}</button></span></li>
              ))}</ul>
            </details>
          )}
          {custom && <Deleted personaId={id} refresh={changes} onRestored={() => { setChanges(n => n + 1); load(0); toast(t('Memory restored')) }} />}
          <div className="mem-list">
            {items.map(item => (
              <MemoryCard key={item.id} item={item} personaId={id} onOpen={setViewer}
                onChanged={(u) => { setChanges(n => n + 1); setItems(list => (u ? list.map(x => (x.id === u.id ? { ...x, ...u } : x)) : list.filter(x => x.id !== item.id))) }} />
            ))}
          </div>
          {items.length < total && <button type="button" className="btn btn-s" style={{ alignSelf: 'center' }} disabled={loading} onClick={() => load(items.length)}>{loading ? t('Loading…') : t('Show more')}</button>}
        </div>
      </section>
      {viewer && <SourceViewer personaId={id} index={0} onClose={() => setViewer(null)}
        source={{ memory_id: viewer.id, citation: viewer.citation, voice: viewer.voice, quote: viewer.text, distance: viewer.distance }} />}
    </div>
  )
}
