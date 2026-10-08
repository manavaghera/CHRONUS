import { useState } from 'react'
import { api } from '../api'
import { navigate } from '../router'
import { useT } from '../i18n'
import { useToast } from '../lib/toast'
import Icon from '../lib/Icon'

// Consent that can change (services/consent.py): pause or resume, renew by the
// review date, revoke (deletes everything), and topics that are off limits.
export default function ConsentPanel({ persona, onChange }) {
  const t = useT()
  const toast = useToast()
  const consent = persona.consent || {}
  const [topics, setTopics] = useState((consent.off_limits || []).join(', '))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const paused = consent.status === 'paused'
  const name = persona.name

  const act = async (action) => {
    if (action === 'revoke' && !window.confirm(t('Revoke consent for {name}? This deletes the model and everything in it: memories, documents, interview answers and voice. It cannot be undone.', { name }))) return
    setBusy(true); setError('')
    try {
      const r = await api.changeConsent(persona.id, action)
      if (r.deleted) { toast(t('Consent revoked. {name} was deleted.', { name })); navigate('/models'); return }
      onChange({ ...persona, consent: r })
      toast(action === 'pause' ? t('{name} is paused', { name }) : action === 'resume' ? t('{name} is active again', { name }) : t('Consent renewed for a year'))
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  const save = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      const r = await api.setOffLimits(persona.id, topics.split(',').map(x => x.trim()).filter(Boolean))
      onChange({ ...persona, consent: r }); setTopics(r.off_limits.join(', ')); toast(t('Off-limits topics saved'))
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const state = consent.review_due ? 'due' : paused ? 'paused' : 'active'
  return (
    <section className="card consent-panel" aria-labelledby="cp-h">
      <div className="cp-head">
        <div className="col gap8">
          <span className="over">{t('Consent and privacy')}</span>
          <h2 id="cp-h" className="h3">{t('Consent can change. So can this model.')}</h2>
          <p className="small">{t('The person who gave consent, or their family, can pause {name}, renew consent each year, keep topics private, or revoke it, which deletes everything.', { name })}</p>
        </div>
        <span className={`cp-state is-${state}`} role="status">
          <i />{state === 'due' ? t('Review was due {date}', { date: consent.review_by }) : state === 'paused' ? t('Paused') : t('Active · review by {date}', { date: consent.review_by || t('a year after consent') })}
        </span>
      </div>
      {state !== 'active' && <p className="small">{state === 'due' ? t('Nobody can chat with {name} until consent is renewed.', { name }) : t('Nobody can chat with {name} until it is resumed.', { name })}</p>}
      <div className="row wrap-row gap8">
        {!paused && !consent.review_due && <button type="button" className="btn btn-s btn-sm" disabled={busy} onClick={() => act('pause')}><Icon name="stop" size={14} />{t('Pause')}</button>}
        {paused && !consent.review_due && <button type="button" className="btn btn-s btn-sm" disabled={busy} onClick={() => act('resume')}><Icon name="play" size={14} />{t('Resume')}</button>}
        <button type="button" className="btn btn-s btn-sm" disabled={busy} onClick={() => act('renew')}><Icon name="check" size={14} />{t('Renew for a year')}</button>
        <button type="button" className="btn btn-d btn-sm" disabled={busy} onClick={() => act('revoke')}><Icon name="trash" size={14} />{t('Revoke consent')}</button>
      </div>
      <form className="col gap8" onSubmit={save}>
        <label className="fld" htmlFor="off-limits">{t('Off-limits topics, comma-separated. Questions about them are refused, and memories that mention them are never quoted.')}
          <span className="row wrap-row gap8">
            <input id="off-limits" className="field sm" maxLength={1200} placeholder={t('e.g. divorce, the hospital')} value={topics} onChange={e => setTopics(e.target.value)} />
            <button className="btn btn-p btn-sm" disabled={busy}>{t('Save topics')}</button>
          </span>
        </label>
        {(consent.off_limits || []).length > 0 && <div className="row wrap-row gap8">{consent.off_limits.map(x => <span key={x} className="badge">{x}</span>)}</div>}
      </form>
      <p className="note">{t('To keep one memory but never quote it, use “Never quote” in')} <a href={`#/memories/${persona.id}`}>{t('{name}’s memories', { name })}</a>.</p>
      {error && <div className="alert" role="alert">{error}</div>}
    </section>
  )
}
