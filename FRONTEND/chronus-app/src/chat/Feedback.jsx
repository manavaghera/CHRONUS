import { useState } from 'react'
import { api } from '../api'
import { tx, useT } from '../i18n'
import Icon from '../lib/Icon'

const REASONS = [['not_their_words', tx('Not their words')], ['wrong_attribution', tx('Wrong source')], ['incorrect', tx('Factually wrong')], ['unhelpful', tx('Didn’t answer')], ['other', tx('Something else')]]

// Thumbs up / down on an answer. Goes to the review queue on the Insights
// page, where a person decides what happens; nothing changes the model directly.
export default function Feedback({ entryId, personaId }) {
  const t = useT()
  const [sent, setSent] = useState(null)
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('not_their_words')
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  if (!/^[0-9a-f]{12}$/.test(entryId || '')) return null
  const send = async (rating) => {
    setError('')
    try { await api.feedback({ entry_id: entryId, persona: personaId, rating, ...(rating === 'down' ? { reason, note } : {}) }); setSent(rating); setOpen(false) }
    catch (e) { setError(e.message) }
  }
  return (
    <>
      <button type="button" className={`mact icon${sent === 'up' ? ' is-on' : ''}`} aria-label={t('Good answer')} title={t('Good answer')} disabled={!!sent} onClick={() => send('up')}><Icon name="thumbUp" size={14} /></button>
      <button type="button" className={`mact icon${sent === 'down' || open ? ' is-on' : ''}`} aria-label={t('Report a problem')} title={t('Report a problem')} aria-expanded={open} disabled={!!sent} onClick={() => setOpen(o => !o)}><Icon name="thumbDown" size={14} /></button>
      {sent && <span className="note">{t('Thanks, sent for review')}</span>}
      {error && <span className="note">{error}</span>}
      {open && (
        <div className="fb-form">
          <div className="chips" role="group" aria-label={t('What’s wrong')}>
            {REASONS.map(([v, l]) => <button key={v} type="button" className="chip sm" aria-pressed={reason === v} onClick={() => setReason(v)}>{t(l)}</button>)}
          </div>
          <div className="row gap8">
            <input className="field sm" maxLength={1000} placeholder={t('Optional note for the reviewer')} aria-label={t('Note for the reviewer')} value={note} onChange={e => setNote(e.target.value)} />
            <button type="button" className="btn btn-p btn-sm" onClick={() => send('down')}>{t('Send')}</button>
          </div>
        </div>
      )}
    </>
  )
}
