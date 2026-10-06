import { useState } from 'react'
import { api } from '../../api'

const REASONS = [
  ['not_their_words', "Not their words"],
  ['wrong_attribution', 'Wrong source'],
  ['incorrect', 'Factually wrong'],
  ['unhelpful', "Didn't answer"],
  ['other', 'Something else'],
]

// Thumbs up / down on an answer. Goes to the review queue (Insights page),
// where a person decides what happens; nothing changes the model directly.
export default function Feedback({ entryId, personaId }) {
  const [sent, setSent] = useState(null)
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('not_their_words')
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  if (!entryId) return null

  const send = async (rating) => {
    setError('')
    try {
      await api.feedback({ entry_id: entryId, persona: personaId, rating, ...(rating === 'down' ? { reason, note } : {}) })
      setSent(rating); setOpen(false)
    } catch (e) { setError(e.message) }
  }

  return (
    <div className="feedback">
      <button className={`fb-btn${sent === 'up' ? ' is-on' : ''}`} onClick={() => send('up')} aria-label="Good answer" title="Good answer">👍</button>
      <button className={`fb-btn${sent === 'down' || open ? ' is-on' : ''}`} onClick={() => setOpen(o => !o)} aria-label="Report a problem" title="Report a problem">👎</button>
      {sent && <span className="fb-thanks">Thanks, sent for review</span>}
      {open && (
        <div className="fb-form">
          <select className="create-select" value={reason} onChange={e => setReason(e.target.value)} aria-label="What's wrong">
            {REASONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <input className="create-select" maxLength={1000} value={note} onChange={e => setNote(e.target.value)} placeholder="Optional note for the reviewer" />
          <button className="demo-quick-btn" onClick={() => send('down')}>Send</button>
        </div>
      )}
      {error && <span className="fb-error">{error}</span>}
    </div>
  )
}
