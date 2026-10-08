import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { navigate } from '../router'
import { halves, tx, useLanguage } from '../i18n'
import { coverage, initials, relLabel } from '../lib/data'
import Icon from '../lib/Icon'
import Radar from '../components/Radar'
import { StepConsent, StepWho } from '../create/StepWho'
import StepWords from '../create/StepWords'
import StepInterview from '../create/StepInterview'
import StepVoice from '../create/StepVoice'
import StepBuild from '../create/StepBuild'
import ConsentPanel from '../create/ConsentPanel'

const STEPS = [tx('Who'), tx('Consent'), tx('Their words'), tx('Interview'), tx('Voice'), tx('Build')]
const BLANK = { name: '', description: '', relationship: '', memorial: false, allow_cloud_llm: true }

// Where an existing model should open: the first thing still missing
function firstStep(p) {
  if (p.status === 'ready') return 5
  if (!p.uploads.length && !p.interview_answered.length) return 2
  if (p.interview_answered.length < 10) return 3
  return 5
}

export default function CreatePage({ id }) {
  const { t, lang } = useLanguage()
  const [persona, setPersona] = useState(null)
  const [draft, setDraft] = useState(BLANK)
  const [step, setStep] = useState(0)
  const [error, setError] = useState('')
  const [consentText, setConsentText] = useState(null)

  // The consent statements in the site's language, exactly as the record keeps them
  useEffect(() => { api.consentText(lang).then(setConsentText).catch(() => setConsentText(null)) }, [lang])
  useEffect(() => {
    if (!id) return
    api.persona(id).then(p => {
      if (p.kind !== 'custom') { setError(t('{name} is a pretrained model; it can’t be edited here.', { name: p.name })); return }
      setPersona(p); setStep(firstStep(p))
    }).catch(e => setError(e.message))
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  const go = useCallback((n) => { setStep(n); window.scrollTo({ top: 0, behavior: 'smooth' }) }, [])
  const valid0 = draft.name.trim().length >= 2 && !!draft.relationship
  const reach = persona ? [false, false, true, true, true, true] : [true, valid0, false, false, false, false]
  const shown = persona || draft
  const answered = persona?.interview_answered || []
  const own = persona ? persona.uploads.filter(u => u.authored_by === 'self').length : 0

  return (
    <div className="page wiz">
      <div className="wrap">
        <div className="wtop">
          <div className="col gap8">
            <nav className="crumbs" aria-label={t('Breadcrumb')}><a href="#/">{t('Home')}</a><span aria-hidden="true">/</span><a href="#/models">{t('Your models')}</a><span aria-hidden="true">/</span><span>{persona ? persona.name : t('Preserve someone')}</span></nav>
            <h1 className="wiz-title">{persona ? <>{t('Preserving')} <em>{persona.name}</em></> : halves(t('Preserve|someone'))}</h1>
          </div>
          <button className="btn btn-s btn-sm" type="button" onClick={() => navigate('/models')}>{t('Exit')}</button>
        </div>
        {error && <div className="alert" role="alert">{error}</div>}
        <ol className="rail" aria-label={t('Steps')}>
          {STEPS.map((s, i) => {
            const done = persona ? i < 2 || (i === 2 && persona.uploads.length > 0) || (i === 3 && answered.length > 0) || (i === 4 && !!persona.voice) || (i === 5 && persona.status === 'ready') : i < step
            return (
              <li key={s}>
                <button type="button" className="rstep" data-st={i === step ? 'cur' : done ? 'done' : 'todo'} disabled={!reach[i] && i !== step}
                  aria-current={i === step ? 'step' : undefined} onClick={() => reach[i] && go(i)}>
                  <span className="n">{done && i !== step ? <Icon name="check" size={12} /> : `0${i + 1}`}</span><span className="t">{t(s)}</span>
                </button>
              </li>
            )
          })}
        </ol>
        <div className="wgrid">
          <div className="card wmain">
            <div className="wbody" key={step}>
              {step === 0 && <StepWho draft={draft} setDraft={setDraft} onNext={() => go(1)} valid={valid0} />}
              {step === 1 && <StepConsent draft={draft} consentText={consentText} onBack={() => go(0)} onCreated={(p) => navigate(`/create/${p.id}`)} />}
              {persona && step === 2 && <StepWords persona={persona} onChange={setPersona} onNext={() => go(3)} />}
              {persona && step === 3 && <StepInterview persona={persona} onChange={setPersona} onNext={() => go(4)} />}
              {persona && step === 4 && <StepVoice persona={persona} onChange={setPersona} consentText={consentText} onNext={() => go(5)} />}
              {persona && step === 5 && <StepBuild persona={persona} onChange={setPersona} onAddMore={() => go(2)} />}
              {!persona && id && !error && <div className="row gap12"><span className="spinner" />{t('Loading…')}</div>}
            </div>
          </div>
          <aside className="wprev" aria-label={t('Live preview')}>
            <div className="card pcard">
              <div className="row-sb"><span className="lab">{t('Live preview')}</span>
                <span className="row gap8">{shown.memorial && <span className="badge acc">{t('Memorial')}</span>}<span className="badge">{t('Private')}</span></span></div>
              <div className="row gap14">
                <span className="av">{initials(shown.name)}</span>
                <span className="col gap8" style={{ minWidth: 0 }}>
                  <span className="serif pv-name">{shown.name?.trim() || t('Their name')}</span>
                  <span className="lab">{shown.relationship ? t(relLabel(shown.relationship)) : t('Relationship')}</span>
                </span>
              </div>
              <Radar values={coverage(answered)} />
              <div>
                <div className="prow"><span>{t('Consent')}</span><b>{persona ? t('Recorded') : t('Not yet')}</b></div>
                <div className="prow"><span>{t('Memories')}</span><b>{persona ? persona.memories.toLocaleString() : 0}</b></div>
                <div className="prow"><span>{t('Files (theirs / others’)')}</span><b>{persona ? `${own} / ${persona.uploads.length - own}` : '0 / 0'}</b></div>
                <div className="prow"><span>{t('Interview')}</span><b>{t('{n} of 25', { n: answered.length })}</b></div>
                <div className="prow"><span>{t('Cloned voice')}</span><b>{persona?.voice ? `${persona.voice.seconds} s` : t('None yet')}</b></div>
                <div className="prow"><span>{t('Status')}</span><b>{persona?.status === 'ready' ? t('Ready to talk') : t('Draft')}</b></div>
              </div>
            </div>
            <p className="note" style={{ padding: '0 6px' }}>{t('The shape fills in as you answer. Each point is one part of who they are.')}</p>
            {persona && (
              <div className="card pcard quick-links">
                <span className="lab">{t('Manage')}</span>
                <a className="qlink" href={`#/memories/${persona.id}`}><Icon name="search" size={16} />{t('Browse and correct memories')}<Icon name="arrow" size={14} /></a>
                <a className="qlink" href={`#/insights/${persona.id}`}><Icon name="chart" size={16} />{t('Insights and knowledge gaps')}<Icon name="arrow" size={14} /></a>
                {persona.status === 'ready' && <a className="qlink" href={`#/chat/${persona.id}`}><Icon name="sparkle" size={16} />{t('Talk to {name}', { name: persona.name.split(' ')[0] })}<Icon name="arrow" size={14} /></a>}
              </div>
            )}
          </aside>
        </div>
        {persona && <ConsentPanel persona={persona} onChange={setPersona} />}
      </div>
    </div>
  )
}
