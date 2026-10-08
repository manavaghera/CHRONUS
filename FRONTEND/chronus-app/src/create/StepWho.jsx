import { useState } from 'react'
import { api } from '../api'
import { useLanguage } from '../i18n'
import { RELATIONSHIPS } from '../lib/data'
import Icon from '../lib/Icon'

export function StepWho({ draft, setDraft, onNext, valid }) {
  const { t } = useLanguage()
  const set = (k, v) => setDraft(d => ({ ...d, [k]: v }))
  return (
    <>
      <span className="lab">{t('Step {n} of 6', { n: 1 })}</span>
      <h2 className="wh">{t('Who are you')} <em>{t('preserving?')}</em></h2>
      <label className="fld" htmlFor="w-name">{t('Their name, or what you call them')}
        <input id="w-name" className="field" maxLength={60} autoComplete="off" autoFocus placeholder={t('Name')} value={draft.name} onChange={e => set('name', e.target.value)} />
      </label>
      <div className="fld"><span id="rel-l">{t('Who they are to you')}</span>
        <div className="chips" role="group" aria-labelledby="rel-l">
          {RELATIONSHIPS.map(([v, label]) => (
            <button key={v} type="button" className="chip" aria-pressed={draft.relationship === v}
              onClick={() => setDraft(d => ({ ...d, relationship: v, memorial: v === 'self' ? false : d.memorial }))}>{t(label)}</button>
          ))}
        </div>
      </div>
      <label className="fld" htmlFor="w-desc">{t('A line about them (optional)')}
        <input id="w-desc" className="field" maxLength={300} placeholder={t('e.g. My grandmother, a teacher for thirty years')} value={draft.description} onChange={e => set('description', e.target.value)} />
      </label>
      <button className="switch" type="button" role="switch" aria-checked={draft.memorial} disabled={draft.relationship === 'self'} onClick={() => set('memorial', !draft.memorial)}>
        <span className="tr" /><span><span className="t1">{t('Memorial mode')}</span><span className="t2">{t('For someone who has died. Built with the family’s agreement, with gentler framing.')}</span></span>
      </button>
      <button className="switch" type="button" role="switch" aria-checked={draft.allow_cloud_llm} onClick={() => set('allow_cloud_llm', !draft.allow_cloud_llm)}>
        <span className="tr" /><span><span className="t1">{t('Allow the AI voice')}</span><span className="t2">{t('A language model may rephrase their words conversationally, always citing them. Off: answers are their exact words only.')}</span></span>
      </button>
      <div className="wfoot">
        <span className="lab">{t('Step {n} of 6', { n: 1 })}</span>
        <button className="btn btn-p btn-sm" type="button" disabled={!valid} onClick={onNext}>{t('Continue to consent')}<Icon name="arrow" size={16} /></button>
      </div>
    </>
  )
}

export function StepConsent({ draft, consentText, onBack, onCreated }) {
  const { t, lang } = useLanguage()
  const [agree, setAgree] = useState(false)
  const [understand, setUnderstand] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const name = draft.name.trim() || t('them')
  const create = async () => {
    setBusy(true); setError('')
    try {
      const p = await api.createPersona({ ...draft, name: draft.name.trim(), description: draft.description.trim(), consent: true, language: consentText?.language || 'en' })
      onCreated(p)
    } catch (e) { setError(e.message); setBusy(false) }
  }
  const today = new Date().toLocaleDateString(lang, { day: 'numeric', month: 'short', year: 'numeric' })
  const intro = draft.memorial ? t('{name} has died. Build this only as their next of kin or with the family’s agreement.', { name })
    : draft.relationship === 'self' ? t('You are preserving yourself. You choose what goes in, and you can delete it at any time.')
      : t('{name} should know what CHRONUS does, what it will be built from, and that they can ask for it to be deleted at any time.', { name })
  return (
    <>
      <span className="lab">{t('Step {n} of 6', { n: 2 })}</span>
      <h2 className="wh">{t('Consent')} <em>{t('comes first.')}</em></h2>
      <p className="lede">{intro}</p>
      <label className="check"><input type="checkbox" checked={agree} disabled={!consentText} onChange={e => setAgree(e.target.checked)} />
        <span><b>{t('Consent.')}</b> {consentText?.model || t('Loading the consent statement…')}</span></label>
      <label className="check"><input type="checkbox" checked={understand} onChange={e => setUnderstand(e.target.checked)} />
        <span>{t('I understand it answers only from what they really said, and says “I don’t know” otherwise.')}</span></label>
      <div className="record" aria-label={t('Consent record preview')}>
        <span className="lab">{t('Consent record')}</span>
        <span>{t('Model')} ········ <b>{name}</b></span>
        <span>{t('Mode')} ········· <b>{draft.memorial ? t('Memorial') : draft.relationship === 'self' ? t('Self') : t('Living, with consent')}</b></span>
        <span>{t('AI voice')} ····· <b>{draft.allow_cloud_llm ? t('Allowed') : t('Quotes only')}</b></span>
        <span>{t('Language')} ····· <b>{consentText?.language?.toUpperCase() || 'EN'}</b></span>
        <span>{t('Date')} ········· <b>{today}</b></span>
      </div>
      {!consentText && <div className="alert">{t('Can’t load the consent statement. Is the CHRONUS server running on port 8001?')}</div>}
      {error && <div className="alert" role="alert">{error}</div>}
      <div className="wfoot">
        <button className="btn btn-s btn-sm" type="button" onClick={onBack}>{t('Back')}</button>
        <button className="btn btn-a btn-sm" type="button" disabled={!agree || !understand || busy || !consentText} onClick={create}>
          {busy ? t('Recording consent…') : t('Create {name}’s model', { name })}<Icon name="arrow" size={16} />
        </button>
      </div>
    </>
  )
}
