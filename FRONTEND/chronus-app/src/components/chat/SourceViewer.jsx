import { useEffect, useState } from 'react'
import { api } from '../../api'
import { navigate } from '../../router'
import useDialog from '../../useDialog'

// A cited memory in full, with the text around it ("view in transcript").
export default function SourceViewer({ personaId, source, index, onClose }) {
  const [memory, setMemory] = useState(null)
  const [error, setError] = useState('')
  const memoryId = source?.memory_id

  useEffect(() => {
    if (!memoryId) return
    let cancelled = false
    api.memory(personaId, memoryId).then(m => !cancelled && setMemory(m)).catch(e => !cancelled && setError(e.message))
    return () => { cancelled = true }
  }, [personaId, memoryId])

  const dialogRef = useDialog(!!source, onClose)

  if (!source) return null
  const text = memory?.text || source.quote
  const context = memory?.context
  return (
    <div className="viewer-overlay" role="dialog" aria-modal="true" aria-labelledby="viewer-title" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="viewer-panel" ref={dialogRef} tabIndex={-1}>
        <button className="modal-close" onClick={onClose} aria-label="Close"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 4l16 16M20 4 4 20" /></svg></button>
        <div className="eyebrow eyebrow--accent">Source {index + 1}</div>
        <h2 id="viewer-title" className="viewer-title">{source.citation || source.source_file}</h2>
        <div className="viewer-meta">
          {source.voice && <span className={`demo-voice demo-voice--${source.voice}`}>{source.voice.replace('_', ' ')}</span>}
          {source.distance != null && <span>match {Math.max(0, Math.round((1 - source.distance) * 100))}%</span>}
          {memory?.date && !['unknown', 'protocol'].includes(memory.date) && <span>{memory.date}</span>}
          {memory?.page && <span>page {memory.page}</span>}
        </div>
        {error && <div className="page-alert">{error}</div>}
        <blockquote className="viewer-quote">{text}</blockquote>
        {context?.kind === 'paragraph' && (
          <div className="viewer-context">
            <h3>In context</h3>
            <p>{context.text}</p>
          </div>
        )}
        {context?.kind === 'pages' && (
          <div className="viewer-context">
            <h3>Neighbouring pages</h3>
            {context.pages.map(p => <p key={p.page}><strong>p. {p.page}</strong> {p.text}</p>)}
          </div>
        )}
        {memoryId && (
          <button className="page-link" onClick={() => { onClose(); navigate(`/memories/${personaId}`) }}>Browse all memories of this model →</button>
        )}
      </div>
    </div>
  )
}
