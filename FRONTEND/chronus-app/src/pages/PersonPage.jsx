import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { halves, tx, useLanguage } from '../i18n'
import { initials } from '../lib/data'
import { useToast } from '../lib/toast'

// The person model (services/person_routes.py): who they are (identity
// profile), how they talk (style adapter), and the switches that are consent
// decisions (learn their style, "in their spirit" answers, freeze).
const VOICES = { own: tx('Their words'), about: tx('Said about them'), public: tx('Public record') }
// Section headings by key (services/identity.py SECTIONS), so they translate
const HEADINGS = { about: tx('About'), values: tx('What I believe'), temperament: tx('How I am'), shaped: tx('What shaped me'),
  people: tx('People who matter'), loves: tx('What I love'), voice: tx('How I talk') }
const STAGES = { starting: tx('Starting'), dataset: tx('Building the training set'), training: tx('Training'), exam: tx('Taking the exam') }
const SWITCHES = [
  ['allow_spirit', tx('Allow “in their spirit” answers.'), tx('When they never talked about something, the AI voice may answer the way they likely would, always labelled as inferred.')],
  ['learn_style', tx('Learn their style.'), tx('Train a small style model on their own answers, on this computer, and retrain it as they add more.')],
  ['frozen', tx('Freeze this model.'), tx('No more training, for example after they have died. Their memories and profile stay as they are.')],
]

function Identity({ persona, data, custom, onChange }) {
  const { t } = useLanguage()
  const toast = useToast()
  const [busy, setBusy] = useState('')
  const hide = async (line) => {
    setBusy(line.id)
    try { onChange(await api.hideIdentityLine(persona.id, line.id, !line.hidden)); toast(line.hidden ? t('Line shown again') : t('Line hidden from the profile')) }
    catch (e) { toast(e.message) } finally { setBusy('') }
  }
  const rebuild = async () => {
    setBusy('all')
    try { onChange(await api.rebuildIdentity(persona.id)); toast(t('Profile rebuilt from their words')) } catch (e) { toast(e.message) } finally { setBusy('') }
  }
  const groups = data.sections.map(([key, heading]) => [key, HEADINGS[key] || heading, data.lines.filter(l => l.section === key)]).filter(g => g[2].length)
  return (
    <div className="card pm-card">
      <div className="row-sb"><h2 className="h3">{t('Who they are')}</h2>
        {custom && <button type="button" className="btn btn-s btn-sm" disabled={!!busy} onClick={rebuild}>{t('Rebuild')}</button>}</div>
      <p className="note">{t('Every line is one of their own sentences, linked to where it came from. The AI voice reads this before it answers.')}</p>
      {!groups.length && <p className="small">{t('Nothing yet: answer interview questions or add their words, and the profile fills in.')}</p>}
      {groups.map(([key, heading, lines]) => (
        <section key={key} className="id-sec" aria-label={t(heading)}>
          <span className="lab">{t(heading)}</span>
          <ul>
            {lines.map(line => (
              <li key={line.id} className={`id-line${line.hidden ? ' is-hidden' : ''}`}>
                <p lang={line.voice === 'public' ? undefined : 'en'}>{line.voice === 'public' ? line.text : `“${line.text}”`}</p>
                <div className="row wrap-row gap8">
                  <span className={`badge${line.voice === 'own' ? ' ok' : ''}`}>{t(VOICES[line.voice] || line.voice)}</span>
                  {line.question && <span className="note ell" title={line.question}>{line.question}</span>}
                  {!line.question && line.source && <span className="note ell">{line.source}</span>}
                  {line.hidden && <span className="badge">{t('Hidden')}</span>}
                  {custom && <button type="button" className="linkbtn" disabled={busy === line.id} onClick={() => hide(line)}>{line.hidden ? t('Show') : t('Hide')}</button>}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

function Style({ persona, state, custom, onTrain }) {
  const { t, lang } = useLanguage()
  const exam = state.current?.exam
  const run = state.run
  const date = (s) => (s ? new Date(s).toLocaleDateString(lang, { day: 'numeric', month: 'short', year: 'numeric' }) : '')
  return (
    <div className="card pm-card">
      <div className="row-sb"><h2 className="h3">{t('How they talk')}</h2>
        <span className={`badge${state.in_use ? ' ok' : ''}`}>{state.in_use ? t('In use') : t('Not in use')}</span></div>
      <p className="note">{t('A small style model trained only on their own answers. A new version is used only if it passes an exam: closer to their real answers than the plain model, and just as faithful to their words.')}</p>
      {state.current ? (
        <div className="exam">
          <b>{t('Version {n}', { n: state.current.version })}</b>
          <span className="small">{t('Closer to their real answers: {a} vs {b} for the plain model', { a: exam.candidate.cosine, b: exam.base.cosine })}</span>
          <span className="small">{t('Answers kept by the grounding check: {a}% vs {b}%', { a: Math.round(exam.candidate.kept * 100), b: Math.round(exam.base.kept * 100) })}</span>
        </div>
      ) : <p className="small">{t('No version has passed its exam yet.')}</p>}
      {run?.state === 'running' && <p className="row gap8 small"><span className="spinner" />{t(STAGES[run.stage] || 'Training')}{run.version ? ` · ${t('Version {n}', { n: run.version })}` : ''}</p>}
      {run?.state === 'failed' && <div className="alert">{run.message}</div>}
      {state.history.length > 0 && (
        <ul className="runs">
          {[...state.history].reverse().map(h => (
            <li key={h.version}><span className={`badge${h.passed ? ' ok' : ''}`}>{h.passed ? t('Passed') : t('Not used')}</span>
              <span className="small"><b>{t('Version {n}', { n: h.version })}</b> · {date(h.trained_at)} · {t('{n} examples', { n: h.examples })}</span>
              <span className="note">{h.reason}</span></li>
          ))}
        </ul>
      )}
      {custom && state.reason && <p className="note">{state.reason}</p>}
      {custom && state.ready && run?.state !== 'running' && <button type="button" className="btn btn-a btn-sm" onClick={onTrain}>{t('Train now')}</button>}
      {!custom && <p className="note">{t('Used by the on-device AI voice. {name}’s style is trained from the command line.', { name: persona.name })}</p>}
    </div>
  )
}

export default function PersonPage({ id }) {
  const { t } = useLanguage()
  const toast = useToast()
  const [persona, setPersona] = useState(null)
  const [profile, setProfile] = useState(null)
  const [style, setStyle] = useState(null)
  const [error, setError] = useState('')
  const load = useCallback(() => Promise.all([api.persona(id), api.identity(id), api.styleStatus(id)])
    .then(([p, i, s]) => { setPersona(p); setProfile(i); setStyle(s) }).catch(e => setError(e.message)), [id])
  useEffect(() => { load() }, [load])
  // While a training run is going, check on it now and then
  useEffect(() => {
    if (style?.run?.state !== 'running') return undefined
    const timer = setInterval(() => api.styleStatus(id).then(setStyle).catch(() => {}), 10000)
    return () => clearInterval(timer)
  }, [id, style?.run?.state])

  const custom = persona?.kind === 'custom'
  const flip = async (key) => {
    try {
      const flags = await api.personSettings(id, { [key]: !persona.person_settings[key] })
      setPersona(p => ({ ...p, person_settings: flags }))
      setStyle(await api.styleStatus(id))
      toast(t('Saved'))
    } catch (e) { toast(e.message) }
  }
  const train = async () => { try { setStyle(await api.trainStyle(id)); toast(t('Training started')) } catch (e) { toast(e.message) } }

  return (
    <div className="page">
      <section className="page-hero">
        <div className="page-hero-bg" aria-hidden="true" />
        <div className="wrap">
          <nav className="crumbs" aria-label={t('Breadcrumb')}><a href="#/">{t('Home')}</a><span aria-hidden="true">/</span><a href="#/models">{t('Your models')}</a><span aria-hidden="true">/</span><span>{persona?.name || '…'}</span></nav>
          <div className="row gap16 wrap-row">
            {persona && <span className="av">{initials(persona.name)}</span>}
            <h1 className="h1 h1-sm">{halves(t('Who they are,|in their own words.'))}</h1>
          </div>
          <p className="lede">{t('A model of a person has four layers: what they said (memories), who they are (this profile), how they talk (a style model) and how they sound (their voice).')}</p>
          {persona && <div className="row wrap-row gap8">
            {persona.status === 'ready' && <a className="btn btn-a btn-sm" href={`#/chat/${id}`}>{t('Talk to {name}', { name: persona.name.split(' ')[0] })}</a>}
            <a className="btn btn-s btn-sm" href={`#/memories/${id}`}>{t('Memories')}</a>
          </div>}
        </div>
      </section>
      <section className="sec" style={{ paddingTop: 16 }}>
        <div className="wrap pm-grid">
          {error && <div className="alert" role="alert">{error}</div>}
          {!persona && !error && <p className="lab">{t('Loading…')}</p>}
          {persona && profile && <Identity persona={persona} data={profile} custom={custom} onChange={setProfile} />}
          <div className="col gap16">
            {persona && style && <Style persona={persona} state={style} custom={custom} onTrain={train} />}
            {custom && (
              <div className="card pm-card">
                <h2 className="h3">{t('Consent switches')}</h2>
                <p className="note">{t('Each change is kept in the model’s consent history.')}</p>
                {SWITCHES.map(([key, title, text]) => (
                  <label key={key} className="check"><input type="checkbox" checked={!!persona.person_settings?.[key]} onChange={() => flip(key)} />
                    <span><b>{t(title)}</b> {t(text)}</span></label>
                ))}
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
