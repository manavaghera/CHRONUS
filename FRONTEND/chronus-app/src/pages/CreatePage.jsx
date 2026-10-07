import { useCallback, useEffect, useState } from 'react'
import { api, AUDIO_ACCEPT, download, MAX_UPLOAD_MB, UPLOAD_ACCEPT } from '../api'
import { navigate } from '../router'
import { toWav } from '../audio'
import useVoiceInput from '../components/chat/useVoiceInput'
import ConsentPanel from '../components/ConsentPanel'
import { useLanguage, useT } from '../i18n'

const RELATIONSHIPS = ['self', 'family', 'friend', 'colleague', 'other']
const ANSWERERS = ['self', 'family', 'friend', 'colleague']  // named in strings/pages.js (ans.*)

// The consent statements in the chosen language, exactly as the record keeps them (GET /consent-text)
function useConsentText() {
  const { lang } = useLanguage()
  const [text, setText] = useState(null)
  useEffect(() => { api.consentText(lang).then(setText).catch(() => setText(null)) }, [lang])
  return text
}

function StepBar({ persona }) {
  const t = useT()
  const steps = [
    [t('create.step.details'), !!persona],
    [t('create.step.upload'), persona?.uploads.length > 0],
    [t('create.step.interview'), persona?.interview_answered.length > 0],
    [t('create.step.build'), persona?.status === 'ready'],
  ]
  return (
    <ol className="create-steps">
      {steps.map(([label, done], i) => (
        <li key={label} className={done ? 'is-done' : ''}><span>{done ? '✓' : i + 1}</span>{label}</li>
      ))}
    </ol>
  )
}

function DetailsForm() {
  const t = useT()
  const consentText = useConsentText()
  const [form, setForm] = useState({ name: '', description: '', relationship: 'family', allow_cloud_llm: false, memorial: false, consent: false })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = (key) => (e) => setForm(f => ({ ...f, [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      const persona = await api.createPersona({ ...form, language: consentText?.language || 'en' })
      navigate(`/create/${persona.id}`)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <form className="create-card modal-form" onSubmit={submit}>
      <h2 className="page-h2">{t('create.who')}</h2>
      <div className="form-field"><label htmlFor="c-name">{t('create.name')}</label><input id="c-name" required minLength={2} maxLength={60} value={form.name} onChange={set('name')} placeholder={t('create.namePlaceholder')} /></div>
      <div className="form-field"><label htmlFor="c-desc">{t('create.desc')}</label><input id="c-desc" maxLength={300} value={form.description} onChange={set('description')} placeholder={t('create.descPlaceholder')} /></div>
      <div className="form-field"><label htmlFor="c-rel">{t('create.relationship')}</label>
        <select id="c-rel" className="create-select" value={form.relationship} onChange={set('relationship')}>
          {RELATIONSHIPS.map(v => <option key={v} value={v}>{t(`rel.${v}`)}</option>)}
        </select>
      </div>
      <label className="create-check">
        <input type="checkbox" checked={form.memorial} onChange={set('memorial')} />
        <span><strong>{t('create.memorialTitle')}</strong> {t('create.memorialText')}</span>
      </label>
      <label className="create-check">
        <input type="checkbox" checked={form.allow_cloud_llm} onChange={set('allow_cloud_llm')} />
        <span><strong>{t('create.aiTitle')}</strong> {t('create.aiText')}</span>
      </label>
      <label className="create-check">
        <input type="checkbox" required checked={form.consent} onChange={set('consent')} disabled={!consentText} />
        <span><strong>{t('create.consentTitle')}</strong> {consentText?.model || '…'}</span>
      </label>
      {error && <div className="page-alert">{error}</div>}
      <div className="form-bottom">
        <span className="form-note">{t('create.staysHere')}</span>
        <button type="submit" className="pill-btn pill-btn--dark" disabled={busy || !consentText}><span className="pill-inner">{busy ? t('create.creating') : t('create.createModel')}</span></button>
      </div>
    </form>
  )
}

function UploadStep({ persona, onChange }) {
  const t = useT()
  const [authoredBy, setAuthoredBy] = useState('self')
  const [status, setStatus] = useState(null)  // { name, progress, message }
  const [errors, setErrors] = useState([])
  const [audio, setAudio] = useState(false)
  useEffect(() => { api.voiceStatus().then(s => setAudio(!!s.speech_to_text?.available)).catch(() => {}) }, [])

  const upload = async (e) => {
    const files = [...e.target.files]
    e.target.value = ''
    const failed = []
    for (const file of files) {
      if (file.size > MAX_UPLOAD_MB * 1024 * 1024) { failed.push(t('up.tooBig', { file: file.name, mb: MAX_UPLOAD_MB })); continue }
      setStatus({ name: file.name, progress: 0, message: t('up.uploading') })
      try {
        const r = await api.uploadDocumentWithProgress(persona.id, file, authoredBy,
          (progress, message) => setStatus({ name: file.name, progress, message }))
        onChange(r.persona)
      } catch (err) { failed.push(`${file.name}: ${err.message}`) }
    }
    setStatus(null); setErrors(failed)
  }

  const accept = audio ? `${UPLOAD_ACCEPT},${AUDIO_ACCEPT}` : UPLOAD_ACCEPT
  return (
    <section className="create-card">
      <h2 className="page-h2">{t('up.title')}</h2>
      <p className="page-note">
        {t('up.note', { types: UPLOAD_ACCEPT.replaceAll(',', ', '), mb: MAX_UPLOAD_MB })}
        {audio ? ` ${t('up.audio')}` : ''}
        {' '}{t('up.dupes')}
      </p>
      <div className="create-upload-row">
        <select className="create-select" value={authoredBy} onChange={e => setAuthoredBy(e.target.value)} aria-label={t('up.who')}>
          <option value="self">{t('up.bySelf', { name: persona.name })}</option>
          <option value="other">{t('up.byOther', { name: persona.name })}</option>
        </select>
        <label className={`pill-btn pill-btn--dark create-file${status ? ' is-disabled' : ''}`}>
          <span className="pill-inner">{status ? t('up.uploading') : t('up.choose')}</span>
          <input type="file" multiple accept={accept} disabled={!!status} onChange={upload} />
        </label>
      </div>
      {status && (
        <div className="upload-progress" role="status">
          <div className="upload-progress-label"><span>{status.name}</span><span>{status.message}</span></div>
          <div className="upload-progress-track"><span style={{ width: `${Math.round(status.progress * 100)}%` }} /></div>
        </div>
      )}
      {errors.map(err => <div key={err} className="page-alert">{err}</div>)}
      {persona.uploads.length > 0 && (
        <ul className="create-list">
          {persona.uploads.map(u => (
            <li key={u.filename}>
              <span>{u.kind === 'audio' ? '🎙 ' : ''}{u.filename}</span>
              <span>{u.authored_by === 'self' ? t('up.theirWords') : t('up.aboutThem')} · {t('common.memories', { count: u.memories })}{u.duplicates_skipped ? ` · ${t('up.known', { count: u.duplicates_skipped })}` : ''}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function Dictate({ onText }) {
  const t = useT()
  const voice = useVoiceInput('auto')
  if (!voice.engine) return null
  const click = async () => {
    if (voice.state === 'listening') { voice.stop(); return }
    try { const heard = await voice.listen(); if (heard) onText(heard) } catch { /* shown below */ }
  }
  return (
    <>
      <button type="button" className={`demo-quick-btn${voice.state !== 'idle' ? ' demo-quick-btn--active' : ''}`} onClick={click} disabled={voice.state === 'transcribing'}
        title={voice.engine === 'local' ? t('chat.voiceLocal') : t('chat.voiceBrowser')}>
        {voice.state === 'listening' ? t('chat.stop') : voice.state === 'transcribing' ? t('chat.transcribing') : t('iv.speak')}
      </button>
      {voice.error && <span className="fb-error">{voice.error}</span>}
    </>
  )
}

function FollowUp({ item, personaId, origin, onSaved }) {
  const t = useT()
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [state, setState] = useState('idle')
  const [error, setError] = useState('')
  if (item.kind === 'protocol') {
    const jump = () => {
      const el = document.getElementById(`q-${item.id}`)
      el?.closest('details')?.setAttribute('open', '')
      el?.focus()
    }
    return <li><button className="page-link" onClick={jump}>{t('iv.next', { id: item.id })}</button> {item.question}</li>
  }
  const save = async () => {
    setState('saving'); setError('')
    try { await api.answerFollowup(personaId, { question: item.question, answer: text, origin }); setState('saved'); setOpen(false); onSaved() }
    catch (e) { setError(e.message); setState('idle') }
  }
  return (
    <li>
      <span>{item.question}</span>{state === 'saved' && <span className="create-saved">{t('iv.saved')}</span>}
      {!open && state !== 'saved' && <button className="page-link followup-open" onClick={() => setOpen(true)}>{t('iv.answer')}</button>}
      {open && (
        <div className="create-question">
          <textarea rows={2} maxLength={4000} value={text} onChange={e => setText(e.target.value)} placeholder={t('iv.theirAnswer')} />
          <div className="followup-actions">
            <button className="demo-quick-btn" disabled={!text.trim() || state === 'saving'} onClick={save}>{state === 'saving' ? t('iv.saving') : t('iv.save')}</button>
            <Dictate onText={heard => setText(x => (x ? `${x} ${heard}` : heard))} />
          </div>
          {error && <div className="page-alert">{error}</div>}
        </div>
      )}
    </li>
  )
}

function Question({ q, personaId, answered, origin, onSaved, onRefresh }) {
  const t = useT()
  const [text, setText] = useState('')
  const [state, setState] = useState(answered ? 'saved' : 'idle')
  const [error, setError] = useState('')
  const [followups, setFollowups] = useState([])

  const save = async () => {
    setState('saving'); setError('')
    try {
      const r = await api.answerInterview(personaId, { question_id: q.id, answer: text, origin })
      onSaved(r.persona)
      setFollowups(r.followups || [])
      setState('saved'); setText('')
    } catch (err) { setState('idle'); setError(err.message) }
  }

  return (
    <div className="create-question">
      <label htmlFor={`q-${q.id}`}><span className="create-qid">{q.id}</span>{q.question}{state === 'saved' && <span className="create-saved">{t('iv.saved')}</span>}</label>
      <textarea id={`q-${q.id}`} rows={3} maxLength={4000} value={text} onChange={e => setText(e.target.value)}
        placeholder={state === 'saved' ? t('iv.replace') : t('iv.prompt')} />
      {error && <div className="page-alert">{error}</div>}
      <div className="followup-actions">
        <button className="demo-quick-btn" disabled={!text.trim() || state === 'saving'} onClick={save}>{state === 'saving' ? t('iv.saving') : t('iv.saveAnswer')}</button>
        <Dictate onText={heard => setText(x => (x ? `${x} ${heard}` : heard))} />
      </div>
      {followups.length > 0 && (
        <div className="followups">
          <span className="followups-title">{t('iv.askNext')}</span>
          <ul>{followups.map(f => <FollowUp key={f.question} item={f} personaId={personaId} origin={origin} onSaved={onRefresh} />)}</ul>
        </div>
      )}
    </div>
  )
}

function InterviewStep({ persona, onChange }) {
  const t = useT()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [origin, setOrigin] = useState(persona.relationship === 'self' ? 'self' : ['family', 'friend', 'colleague'].includes(persona.relationship) ? persona.relationship : 'friend')
  useEffect(() => { api.interviewQuestions().then(setData).catch(e => setError(e.message)) }, [])

  const byId = Object.fromEntries((data?.questions || []).map(q => [q.id, q]))
  return (
    <section className="create-card">
      <h2 className="page-h2">{t('iv.title')} <span className="create-count">{persona.interview_answered.length}/25{persona.followups_answered ? ` + ${t('iv.followups', { count: persona.followups_answered })}` : ''}</span></h2>
      <p className="page-note">{t('iv.intro')}</p>
      <div className="form-field"><label htmlFor="c-origin">{t('iv.who')}</label>
        <select id="c-origin" className="create-select" value={origin} onChange={e => setOrigin(e.target.value)}>
          {ANSWERERS.map(v => <option key={v} value={v}>{t(`ans.${v}`)}</option>)}
        </select>
      </div>
      {error && <div className="page-alert">{error}</div>}
      {data && Object.entries(data.dimensions).map(([dim, info]) => (
        <details key={dim} className="create-dimension">
          <summary>{info.label} <span>{info.question_ids.filter(id => persona.interview_answered.includes(id)).length}/{info.question_count}</span></summary>
          {info.question_ids.map(id => byId[id] && (
            <Question key={id} q={byId[id]} personaId={persona.id} origin={origin}
              answered={persona.interview_answered.includes(id)} onSaved={onChange}
              onRefresh={() => api.persona(persona.id).then(onChange).catch(() => {})} />
          ))}
        </details>
      ))}
    </section>
  )
}

function VoiceStep({ persona, onChange }) {
  const t = useT()
  const consentText = useConsentText()
  const [consent, setConsent] = useState(false)
  const [cloud, setCloud] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [cloudReady, setCloudReady] = useState(null)
  useEffect(() => {
    api.voiceStatus().then(s => setCloudReady(s.cloned.configured)).catch(() => setCloudReady(null))
  }, [])
  const canUpload = consent && cloud && cloudReady !== false

  const upload = async (e) => {
    const file = e.target.files[0]
    e.target.value = ''
    if (!file) return
    setBusy(true); setError('')
    try { onChange(await api.addVoice(persona.id, await toWav(file), consentText?.language || 'en')) } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  const remove = async () => {
    setBusy(true); setError('')
    try { onChange(await api.removeVoice(persona.id)) } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <section className="create-card">
      <h2 className="page-h2">{t('create.voiceTitle')} <span className="create-count">{t('create.optional')}</span></h2>
      <p className="page-note">{t('create.voiceIntro', { name: persona.name })}</p>
      {persona.voice ? (
        <div className="create-upload-row">
          <span className="model-status model-status--ready">{t('create.voiceAdded')} · {persona.voice.seconds} s · {persona.voice.provider}</span>
          <button className="model-delete" disabled={busy} onClick={remove}>{t('create.removeVoice')}</button>
        </div>
      ) : (
        <>
          {cloudReady === false && (
            <div className="page-alert">{t('create.voiceNotSetUp').split(/\{(key|file)\}/).map((part, i) => (i % 2 ? <code key={i}>{part === 'key' ? 'FISH_API_KEY=your_key' : 'CHRONUS/.env'}</code> : part))}</div>
          )}
          <label className="create-check">
            <input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />
            <span><strong>{t('create.voiceConsentTitle')}</strong> {consentText?.voice || '…'}</span>
          </label>
          <label className="create-check">
            <input type="checkbox" checked={cloud} onChange={e => setCloud(e.target.checked)} />
            <span><strong>{t('create.cloudTitle')}</strong> {t('create.cloudText')}</span>
          </label>
          <label className={`pill-btn pill-btn--dark create-file${canUpload ? '' : ' is-disabled'}`}>
            <span className="pill-inner">{busy ? t('create.makingVoice') : t('create.chooseRecording')}</span>
            <input type="file" accept="audio/*,.wav,.mp3,.m4a" disabled={!canUpload || busy} onChange={upload} />
          </label>
        </>
      )}
      {error && <div className="page-alert">{error}</div>}
    </section>
  )
}

function BuildStep({ persona, onChange }) {
  const t = useT()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const ready = persona.status === 'ready'
  const enough = persona.memories >= persona.min_memories

  const build = async () => {
    setBusy(true); setError('')
    try { onChange(await api.buildPersona(persona.id)) } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <section className="create-card">
      <h2 className="page-h2">{t('create.buildTitle')}</h2>
      <p className="page-note">
        {t('create.memoriesSoFar', { count: persona.memories, needed: persona.min_memories })}{' '}
        {ready ? t('create.ready') : t('create.notReady')}
      </p>
      {error && <div className="page-alert">{error}</div>}
      <div className="model-actions">
        {!ready && <button className="pill-btn pill-btn--dark" disabled={!enough || busy} onClick={build}><span className="pill-inner">{busy ? t('create.buildingNow') : t('create.buildModel')}</span></button>}
        {ready && <button className="pill-btn pill-btn--accent" onClick={() => navigate(`/chat/${persona.id}`)}><span className="pill-inner">{t('create.chatWith', { name: persona.name })}</span></button>}
      </div>
    </section>
  )
}

function BackupStep({ persona }) {
  const t = useT()
  const [password, setPassword] = useState('')
  const [again, setAgain] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const ok = password.length >= 8 && password === again

  const exportIt = async (e) => {
    e.preventDefault()
    setBusy(true); setError(''); setDone(false)
    try {
      const blob = await api.exportModel(persona.id, password)
      download(blob, `${persona.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'model'}.chronus`)
      setDone(true); setPassword(''); setAgain('')
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <form className="create-card" onSubmit={exportIt}>
      <h2 className="page-h2">{t('bk.title')} <span className="create-count">{t('create.optional')}</span></h2>
      <p className="page-note">{t('bk.intro', { name: persona.name })}</p>
      <div className="create-upload-row">
        <input className="create-select" type="password" autoComplete="new-password" minLength={8} value={password} onChange={e => setPassword(e.target.value)} placeholder={t('bk.password')} aria-label={t('bk.passwordLabel')} />
        <input className="create-select" type="password" autoComplete="new-password" value={again} onChange={e => setAgain(e.target.value)} placeholder={t('bk.repeat')} aria-label={t('bk.repeat')} />
        <button className="pill-btn pill-btn--dark" disabled={!ok || busy}><span className="pill-inner">{busy ? t('bk.encrypting') : t('bk.download')}</span></button>
      </div>
      {password && again && password !== again && <p className="page-note">{t('bk.mismatch')}</p>}
      {done && <p className="create-saved">{t('bk.done')}</p>}
      {error && <div className="page-alert">{error}</div>}
    </form>
  )
}

export default function CreatePage({ id }) {
  const t = useT()
  const [persona, setPersona] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    if (!id) { setPersona(null); return }
    api.persona(id).then(p => {
      if (p.kind !== 'custom') { setError(t('create.notCustom', { name: p.name })); return }
      setPersona(p); setError('')
    }).catch(e => setError(e.message))
  }, [id, t])
  useEffect(load, [load])

  return (
    <div className="page">
      <section className="page-hero page-hero--compact shell">
        <button className="page-back" onClick={() => navigate('/models')}>{t('chat.allModels')}</button>
        <div className="eyebrow eyebrow--accent">{t('create.eyebrow')}</div>
        <h1 className="page-h1">{persona ? t('create.building', { name: persona.name }) : t('create.preserve')}</h1>
        <p className="page-sub">{t('create.sub')}</p>
      </section>
      <section className="shell page-section create-layout">
        <StepBar persona={persona} />
        {error && <div className="page-alert">{error}</div>}
        {!id && <DetailsForm />}
        {persona && (
          <>
            <UploadStep persona={persona} onChange={setPersona} />
            <InterviewStep persona={persona} onChange={setPersona} />
            <BuildStep persona={persona} onChange={setPersona} />
            <VoiceStep persona={persona} onChange={setPersona} />
            <BackupStep persona={persona} />
            <ConsentPanel persona={persona} onChange={setPersona} />
            <div className="page-links">
              <button className="page-link" onClick={() => navigate(`/memories/${persona.id}`)}>{t('create.reviewMemories')}</button>
              <button className="page-link" onClick={() => navigate(`/insights/${persona.id}`)}>{t('create.seeQuestions')}</button>
            </div>
          </>
        )}
      </section>
    </div>
  )
}
