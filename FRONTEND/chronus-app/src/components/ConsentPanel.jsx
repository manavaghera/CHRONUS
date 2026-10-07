import { useState } from 'react'
import { api } from '../api'
import { useT } from '../i18n'
import { navigate } from '../router'

// Consent that can change (services/consent.py): pause or resume, renew by the
// review date, revoke (deletes everything), and topics that are off limits.
export default function ConsentPanel({ persona, onChange }) {
  const t = useT()
  const consent = persona.consent || {}
  const [topics, setTopics] = useState((consent.off_limits || []).join(', '))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)
  const paused = consent.status === 'paused'
  const name = persona.name

  const act = async (action) => {
    if (action === 'revoke' && !window.confirm(t('consent.revokeConfirm', { name }))) return
    setBusy(true); setError('')
    try {
      const result = await api.changeConsent(persona.id, action)
      if (result.deleted) { navigate('/models'); return }
      onChange({ ...persona, consent: result })
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const saveTopics = async (e) => {
    e.preventDefault()
    setBusy(true); setError(''); setSaved(false)
    try {
      const result = await api.setOffLimits(persona.id, topics.split(',').map(x => x.trim()).filter(Boolean))
      onChange({ ...persona, consent: result })
      setTopics(result.off_limits.join(', '))
      setSaved(true)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  let status = t('consent.active', { date: consent.review_by || t('consent.aYear') })
  if (consent.review_due) status = t('consent.due', { date: consent.review_by, name })
  else if (paused) status = t('consent.paused', { name })

  return (
    <section className="create-card">
      <h2 className="page-h2">{t('consent.title')}</h2>
      <p className="page-note">{t('consent.intro')}</p>
      <p className={`model-status ${paused || consent.review_due ? '' : 'model-status--ready'}`} role="status">{status}</p>
      <div className="create-upload-row">
        {!paused && !consent.review_due && <button className="demo-quick-btn" disabled={busy} onClick={() => act('pause')}>{t('consent.pause')}</button>}
        {paused && !consent.review_due && <button className="demo-quick-btn" disabled={busy} onClick={() => act('resume')}>{t('consent.resume')}</button>}
        <button className="demo-quick-btn" disabled={busy} onClick={() => act('renew')}>{t('consent.renew')}</button>
        <button className="model-delete" disabled={busy} onClick={() => act('revoke')}>{t('consent.revoke')}</button>
      </div>
      <form onSubmit={saveTopics}>
        <label className="page-note" htmlFor="off-limits">{t('consent.topicsLabel')}</label>
        <div className="create-upload-row">
          <input id="off-limits" className="create-select" maxLength={1200} value={topics} onChange={e => { setTopics(e.target.value); setSaved(false) }} placeholder={t('consent.topicsPlaceholder')} />
          <button className="demo-quick-btn" disabled={busy}>{t('consent.saveTopics')}</button>
        </div>
      </form>
      {saved && <p className="create-saved">{t('consent.saved')}</p>}
      <p className="page-note">{t('consent.neverQuoteHint')}</p>
      {error && <div className="page-alert">{error}</div>}
    </section>
  )
}
