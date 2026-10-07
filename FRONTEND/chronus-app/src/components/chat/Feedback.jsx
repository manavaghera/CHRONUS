import { useState } from 'react'
import { api } from '../../api'
import { useT } from '../../i18n'

// Their names are in strings/chat.js (reason.*)
const REASONS = ['not_their_words', 'wrong_attribution', 'incorrect', 'unhelpful', 'other']

// Thumbs up / down on an answer. Goes to the review queue (Insights page),
// where a person decides what happens; nothing changes the model directly.
export default function Feedback({ entryId, personaId }) {
  const t = useT()
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
      <button className={`fb-btn${sent === 'up' ? ' is-on' : ''}`} onClick={() => send('up')} aria-label={t('fb.good')} title={t('fb.good')}>👍</button>
      <button className={`fb-btn${sent === 'down' || open ? ' is-on' : ''}`} onClick={() => setOpen(o => !o)} aria-label={t('fb.report')} title={t('fb.report')}>👎</button>
      {sent && <span className="fb-thanks">{t('fb.thanks')}</span>}
      {open && (
        <div className="fb-form">
          <select className="create-select" value={reason} onChange={e => setReason(e.target.value)} aria-label={t('fb.whatsWrong')}>
            {REASONS.map(v => <option key={v} value={v}>{t.label('reason', v)}</option>)}
          </select>
          <input className="create-select" maxLength={1000} value={note} onChange={e => setNote(e.target.value)} placeholder={t('fb.note')} />
          <button className="demo-quick-btn" onClick={() => send('down')}>{t('chat.send')}</button>
        </div>
      )}
      {error && <span className="fb-error">{error}</span>}
    </div>
  )
}
