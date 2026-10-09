import { useEffect, useRef, useState } from 'react'
import { api, download } from '../api'
import { halves, tx, useT } from '../i18n'
import { useToast } from '../lib/toast'
import Icon from '../lib/Icon'

const STAGES = [tx('Checking the consent record'), tx('Gathering their memories'), tx('Labelling every memory by voice'), tx('Embedding with Sentence-BERT'), tx('Calibrating the “I don’t know” threshold')]

export function Backup({ persona }) {
  const t = useT()
  const toast = useToast()
  const [pw, setPw] = useState('')
  const [again, setAgain] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const ok = pw.length >= 8 && pw === again
  const go = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      download(await api.exportModel(persona.id, pw), `${persona.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'model'}.chronus`)
      setPw(''); setAgain(''); toast(t('Encrypted backup downloaded'))
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return (
    <form className="backup" onSubmit={go}>
      <div className="col gap8"><span className="lab">{t('Encrypted backup · optional')}</span><p className="small">{t('Download {name} as a password-protected .chronus file you can import on any install.', { name: persona.name })}</p></div>
      <div className="row wrap-row gap8">
        <input className="field sm" type="password" autoComplete="new-password" placeholder={t('Password (8+ characters)')} aria-label={t('Backup password')} value={pw} onChange={e => setPw(e.target.value)} />
        <input className="field sm" type="password" autoComplete="new-password" placeholder={t('Repeat it')} aria-label={t('Repeat the password')} value={again} onChange={e => setAgain(e.target.value)} />
        <button className="btn btn-s btn-sm" disabled={!ok || busy}>{busy ? t('Encrypting…') : t('Download backup')}</button>
      </div>
      {pw && again && pw !== again && <p className="note">{t('The passwords don’t match.')}</p>}
      {error && <div className="alert" role="alert">{error}</div>}
    </form>
  )
}

export default function StepBuild({ persona, onChange, onAddMore }) {
  const t = useT()
  const [busy, setBusy] = useState(false)
  const [stage, setStage] = useState(-1)
  const [error, setError] = useState('')
  const timer = useRef(0)
  useEffect(() => () => clearInterval(timer.current), [])
  const ready = persona.status === 'ready'
  const enough = persona.memories >= persona.min_memories
  const pct = Math.min(100, Math.round((persona.memories / Math.max(1, persona.min_memories)) * 100))
  const first = persona.name.split(' ')[0]

  const build = async () => {
    setBusy(true); setError(''); setStage(0)
    let s = 0
    timer.current = setInterval(() => { s = Math.min(STAGES.length - 1, s + 1); setStage(s) }, 650)
    try { onChange(await api.buildPersona(persona.id)) } catch (e) { setError(e.message) } finally { clearInterval(timer.current); setBusy(false); setStage(-1) }
  }

  return (
    <>
      <span className="lab">{t('Step {n} of 6', { n: 6 })}</span>
      {ready ? (
        <div className="done">
          <span className="badge ok">{t('Ready to talk')}</span>
          <p className="done-big">{halves(t('{name} is|preserved.', { name: persona.name }))}</p>
          <p className="lede">{t('Every answer will come from something {name} really said or wrote, with the source attached. Keep adding their words whenever you find more.', { name: first })}</p>
          <div className="row wrap-row gap12">
            <a className="btn btn-a" href={`#/chat/${persona.id}`}>{t('Talk to {name}', { name: first })}<Icon name="arrow" /></a>
            <a className="btn btn-s" href="#/models">{t('Your models')}</a>
            <button className="btn btn-s" type="button" disabled={busy} onClick={build}>{busy ? t('Rebuilding…') : t('Rebuild with new memories')}</button>
          </div>
        </div>
      ) : (
        <>
          <h2 className="wh">{t('Ready to preserve')} <em>{persona.name}?</em></h2>
          <div className="meter-ring" style={{ '--pct': pct }}>
            <div><b>{persona.memories.toLocaleString()}</b><span className="lab">{t('of {n} memories needed', { n: persona.min_memories })}</span></div>
          </div>
          {!enough && <p className="small">{t('Add a few more of their words or interview answers before building: a model needs at least {n} memories to answer well.', { n: persona.min_memories })}</p>}
          {busy && (
            <ol className="stages">
              {STAGES.map((s, i) => <li key={s} className="stage" data-st={i < stage ? 'done' : i === stage ? 'cur' : 'todo'}><span className="sdot">{i < stage && <Icon name="check" size={11} />}</span>{t(s)}</li>)}
            </ol>
          )}
          <div className="row wrap-row gap12">
            <button className="btn btn-a" type="button" disabled={!enough || busy} onClick={build}>{busy ? t('Preserving…') : t('Preserve {name}', { name: persona.name })}<Icon name="arrow" /></button>
            {!enough && <button className="btn btn-s" type="button" onClick={onAddMore}>{t('Add more memories')}</button>}
          </div>
        </>
      )}
      {error && <div className="alert" role="alert">{error}</div>}
      <Backup persona={persona} />
    </>
  )
}
