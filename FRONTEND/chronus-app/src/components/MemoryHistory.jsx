import { useEffect, useState } from 'react'
import { api } from '../api'
import { useT } from '../i18n'

// Memory history with undo (services/memory_history.py): every version of a
// memory, the original first, and memories deleted from the model.

function when(iso) {
  return iso ? new Date(iso).toLocaleString() : ''
}

export function VersionList({ personaId, memoryId, onRestored }) {
  const t = useT()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.memoryHistory(personaId, memoryId).then(setData).catch(e => setError(e.message))
  }, [personaId, memoryId])

  const restore = async (seq) => {
    setBusy(true); setError('')
    try { onRestored(await api.restoreMemory(personaId, memoryId, seq)) } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  if (error) return <div className="page-alert">{error}</div>
  if (!data) return <p className="page-note">{t('mem.loadingHistory')}</p>
  return (
    <div className="mem-history">
      {data.log && !data.log.ok && <div className="page-alert">{t('mem.tampered', { entry: data.log.broken_at })}</div>}
      <ol>
        {data.versions.map(v => (
          <li key={v.version}>
            <div className="mem-history-head">
              {t('mem.version', { n: v.version })}{v.version === 1 && ` ${t('mem.original')}`}{v.current ? ` · ${t('mem.current')}` : ` · ${t.label('replaced', v.replaced_by)} ${when(v.replaced_at)}`}
            </div>
            <p className="mem-text">{v.text}</p>
            {!v.current && <button className="page-link" disabled={busy} onClick={() => restore(v.seq)}>{t('mem.restoreVersion')}</button>}
          </li>
        ))}
      </ol>
    </div>
  )
}

export function DeletedMemories({ personaId, refreshKey, onRestored }) {
  const t = useT()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.history(personaId).then(setData).catch(e => setError(e.message))
  }, [personaId, refreshKey])

  const restore = async (item) => {
    setError('')
    try { await api.restoreMemory(personaId, item.memory_id, item.seq); onRestored() } catch (e) { setError(e.message) }
  }

  if (error) return <div className="page-alert">{error}</div>
  if (!data || (!data.deleted.length && data.log.ok)) return null
  return (
    <details className="create-card mem-docs">
      <summary>{t('mem.recentlyDeleted', { count: data.deleted.length })}</summary>
      {!data.log.ok && <div className="page-alert">{t('mem.tampered', { entry: data.log.broken_at })}</div>}
      <ul className="create-list">
        {data.deleted.map(item => (
          <li key={item.memory_id}>
            <span>{item.text.slice(0, 140)}{item.text.length > 140 ? '…' : ''}</span>
            <span>{when(item.deleted_at)} <button className="page-link" onClick={() => restore(item)}>{t('mem.restore')}</button></span>
          </li>
        ))}
      </ul>
    </details>
  )
}
