import { useCallback, useEffect, useState } from 'react'
import { api, download, MAX_UPLOAD_MB, UPLOAD_ACCEPT } from '../api'
import { navigate } from '../router'
import { toWav } from '../audio'
import useVoiceInput from '../components/chat/useVoiceInput'

const RELATIONSHIPS = [['self', 'This is me'], ['family', 'Family member'], ['friend', 'Friend'], ['colleague', 'Colleague'], ['other', 'Other']]
const ANSWERERS = [['self', 'The person themselves'], ['family', 'Family'], ['friend', 'A friend'], ['colleague', 'A colleague']]
const CONSENT = "I am this person, or I have their permission (or their estate's) to build this model from their words."

function StepBar({ persona }) {
  const steps = [
    ['Details & consent', !!persona],
    ['Upload documents', persona?.uploads.length > 0],
    ['Interview', persona?.interview_answered.length > 0],
    ['Build', persona?.status === 'ready'],
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
  const [form, setForm] = useState({ name: '', description: '', relationship: 'family', allow_cloud_llm: false, memorial: false, consent: false })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = (key) => (e) => setForm(f => ({ ...f, [key]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      const persona = await api.createPersona(form)
      navigate(`/create/${persona.id}`)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <form className="create-card modal-form" onSubmit={submit}>
      <h2 className="page-h2">1. Who is this model of?</h2>
      <div className="form-field"><label htmlFor="c-name">Name</label><input id="c-name" required minLength={2} maxLength={60} value={form.name} onChange={set('name')} placeholder="e.g. Amma, or Dr. Rao" /></div>
      <div className="form-field"><label htmlFor="c-desc">Short description (optional)</label><input id="c-desc" maxLength={300} value={form.description} onChange={set('description')} placeholder="e.g. Retired schoolteacher from Vadodara" /></div>
      <div className="form-field"><label htmlFor="c-rel">Your relationship to them</label>
        <select id="c-rel" className="create-select" value={form.relationship} onChange={set('relationship')}>
          {RELATIONSHIPS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>
      <label className="create-check">
        <input type="checkbox" checked={form.memorial} onChange={set('memorial')} />
        <span><strong>They have passed away.</strong> Memorial mode: answers are framed as remembered words, the model never speaks as if they were alive or present, and long sessions get a gentle reminder to take a break.</span>
      </label>
      <label className="create-check">
        <input type="checkbox" checked={form.allow_cloud_llm} onChange={set('allow_cloud_llm')} />
        <span><strong>Allow AI voice.</strong> Phrasing answers in their voice sends short excerpts of these memories to a cloud AI service (OpenRouter). Leave this off to keep everything on this computer; the model then answers with verbatim quotes.</span>
      </label>
      <label className="create-check">
        <input type="checkbox" required checked={form.consent} onChange={set('consent')} />
        <span><strong>Consent.</strong> {CONSENT}</span>
      </label>
      {error && <div className="page-alert">{error}</div>}
      <div className="form-bottom">
        <span className="form-note">Everything stays in this CHRONUS install. You can delete it all later.</span>
        <button type="submit" className="pill-btn pill-btn--dark" disabled={busy}><span className="pill-inner">{busy ? 'Creating…' : 'Create model'}</span></button>
      </div>
    </form>
  )
}

function UploadStep({ persona, onChange }) {
  const [authoredBy, setAuthoredBy] = useState('self')
  const [status, setStatus] = useState('')
  const [errors, setErrors] = useState([])

  const upload = async (e) => {
    const files = [...e.target.files]
    e.target.value = ''
    const failed = []
    for (const file of files) {
      if (file.size > MAX_UPLOAD_MB * 1024 * 1024) { failed.push(`${file.name}: larger than ${MAX_UPLOAD_MB} MB`); continue }
      setStatus(`Reading and embedding ${file.name}…`)
      try { onChange((await api.uploadDocument(persona.id, file, authoredBy)).persona) }
      catch (err) { failed.push(`${file.name}: ${err.message}`) }
    }
    setStatus(''); setErrors(failed)
  }

  return (
    <section className="create-card">
      <h2 className="page-h2">2. Upload documents</h2>
      <p className="page-note">Letters, journals, emails, speeches, transcripts ({UPLOAD_ACCEPT.replaceAll(',', ', ')}; up to {MAX_UPLOAD_MB} MB each).</p>
      <div className="create-upload-row">
        <select className="create-select" value={authoredBy} onChange={e => setAuthoredBy(e.target.value)} aria-label="Who wrote these documents">
          <option value="self">Written by {persona.name}</option>
          <option value="other">Written about {persona.name}</option>
        </select>
        <label className="pill-btn pill-btn--dark create-file">
          <span className="pill-inner">{status ? 'Uploading…' : 'Choose files'}</span>
          <input type="file" multiple accept={UPLOAD_ACCEPT} disabled={!!status} onChange={upload} />
        </label>
      </div>
      {status && <p className="page-note">{status}</p>}
      {errors.map(err => <div key={err} className="page-alert">{err}</div>)}
      {persona.uploads.length > 0 && (
        <ul className="create-list">
          {persona.uploads.map(u => (
            <li key={u.filename}><span>{u.filename}</span><span>{u.authored_by === 'self' ? 'their words' : 'about them'} · {u.memories} memories</span></li>
          ))}
        </ul>
      )}
    </section>
  )
}

function Dictate({ onText }) {
  const voice = useVoiceInput('auto')
  if (!voice.engine) return null
  const click = async () => {
    if (voice.state === 'listening') { voice.stop(); return }
    try { const t = await voice.listen(); if (t) onText(t) } catch { /* shown below */ }
  }
  return (
    <>
      <button type="button" className={`demo-quick-btn${voice.state !== 'idle' ? ' demo-quick-btn--active' : ''}`} onClick={click} disabled={voice.state === 'transcribing'}
        title={voice.engine === 'local' ? 'Transcribed on this computer' : "Uses your browser's speech recognition, which may send audio to its provider"}>
        {voice.state === 'listening' ? '■ Stop' : voice.state === 'transcribing' ? 'Transcribing…' : '🎙 Speak the answer'}
      </button>
      {voice.error && <span className="fb-error">{voice.error}</span>}
    </>
  )
}

function FollowUp({ item, personaId, origin, onSaved }) {
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
    return <li><button className="page-link" onClick={jump}>Next: {item.id}</button> {item.question}</li>
  }
  const save = async () => {
    setState('saving'); setError('')
    try { await api.answerFollowup(personaId, { question: item.question, answer: text, origin }); setState('saved'); setOpen(false); onSaved() }
    catch (e) { setError(e.message); setState('idle') }
  }
  return (
    <li>
      <span>{item.question}</span>{state === 'saved' && <span className="create-saved">✓ saved</span>}
      {!open && state !== 'saved' && <button className="page-link followup-open" onClick={() => setOpen(true)}>Answer</button>}
      {open && (
        <div className="create-question">
          <textarea rows={2} maxLength={4000} value={text} onChange={e => setText(e.target.value)} placeholder="Their answer…" />
          <div className="followup-actions">
            <button className="demo-quick-btn" disabled={!text.trim() || state === 'saving'} onClick={save}>{state === 'saving' ? 'Saving…' : 'Save'}</button>
            <Dictate onText={t => setText(x => (x ? `${x} ${t}` : t))} />
          </div>
          {error && <div className="page-alert">{error}</div>}
        </div>
      )}
    </li>
  )
}

function Question({ q, personaId, answered, origin, onSaved, onRefresh }) {
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
      <label htmlFor={`q-${q.id}`}><span className="create-qid">{q.id}</span>{q.question}{state === 'saved' && <span className="create-saved">✓ saved</span>}</label>
      <textarea id={`q-${q.id}`} rows={3} maxLength={4000} value={text} onChange={e => setText(e.target.value)}
        placeholder={state === 'saved' ? 'Answered. Write here to replace the saved answer.' : 'Answer in their words, as they would.'} />
      {error && <div className="page-alert">{error}</div>}
      <div className="followup-actions">
        <button className="demo-quick-btn" disabled={!text.trim() || state === 'saving'} onClick={save}>{state === 'saving' ? 'Saving…' : 'Save answer'}</button>
        <Dictate onText={t => setText(x => (x ? `${x} ${t}` : t))} />
      </div>
      {followups.length > 0 && (
        <div className="followups">
          <span className="followups-title">Ask next</span>
          <ul>{followups.map(f => <FollowUp key={f.question} item={f} personaId={personaId} origin={origin} onSaved={onRefresh} />)}</ul>
        </div>
      )}
    </div>
  )
}

function InterviewStep({ persona, onChange }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [origin, setOrigin] = useState(persona.relationship === 'self' ? 'self' : ['family', 'friend', 'colleague'].includes(persona.relationship) ? persona.relationship : 'friend')
  useEffect(() => { api.interviewQuestions().then(setData).catch(e => setError(e.message)) }, [])

  const byId = Object.fromEntries((data?.questions || []).map(q => [q.id, q]))
  return (
    <section className="create-card">
      <h2 className="page-h2">3. Interview <span className="create-count">{persona.interview_answered.length}/25{persona.followups_answered ? ` + ${persona.followups_answered} follow-ups` : ''}</span></h2>
      <p className="page-note">25 questions across six parts of a personality. Answer as many as you can; even a few fill gaps the documents leave. After each answer, CHRONUS suggests what to ask next, from the names, places and years it mentions. You can speak answers instead of typing them.</p>
      <div className="form-field"><label htmlFor="c-origin">Who is answering?</label>
        <select id="c-origin" className="create-select" value={origin} onChange={e => setOrigin(e.target.value)}>
          {ANSWERERS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
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
    try { onChange(await api.addVoice(persona.id, await toWav(file))) } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  const remove = async () => {
    setBusy(true); setError('')
    try { onChange(await api.removeVoice(persona.id)) } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  return (
    <section className="create-card">
      <h2 className="page-h2">5. Voice <span className="create-count">optional</span></h2>
      <p className="page-note">A clear 6-60 second recording (any audio format) of {persona.name} speaking lets answers be read aloud in their voice. Fish Audio (a cloud service) turns it into a private voice; removing the voice, or the model, deletes it there and here.</p>
      {persona.voice ? (
        <div className="create-upload-row">
          <span className="model-status model-status--ready">Voice added · {persona.voice.seconds} s · {persona.voice.provider}</span>
          <button className="model-delete" disabled={busy} onClick={remove}>Remove voice</button>
        </div>
      ) : (
        <>
          {cloudReady === false && (
            <div className="page-alert">Cloud voice isn't set up yet: add <code>FISH_API_KEY=your_key</code> to <code>CHRONUS/.env</code> (get a key at fish.audio/app/api-keys), then restart the server.</div>
          )}
          <label className="create-check">
            <input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />
            <span><strong>Voice consent.</strong> {persona.name}, or their estate, agreed to their voice being used for this model.</span>
          </label>
          <label className="create-check">
            <input type="checkbox" checked={cloud} onChange={e => setCloud(e.target.checked)} />
            <span><strong>Cloud processing.</strong> I agree that the recording, and the text of each answer I play, is sent to Fish Audio to make and use the voice.</span>
          </label>
          <label className={`pill-btn pill-btn--dark create-file${canUpload ? '' : ' is-disabled'}`}>
            <span className="pill-inner">{busy ? 'Making voice…' : 'Choose a recording'}</span>
            <input type="file" accept="audio/*,.wav,.mp3,.m4a" disabled={!canUpload || busy} onChange={upload} />
          </label>
        </>
      )}
      {error && <div className="page-alert">{error}</div>}
    </section>
  )
}

function BuildStep({ persona, onChange }) {
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
      <h2 className="page-h2">4. Build</h2>
      <p className="page-note">
        {persona.memories} memories so far ({persona.min_memories} needed).{' '}
        {ready ? 'The model is ready. New documents and answers are added to it right away.' : 'Memories are embedded as you add them; building checks there is enough to answer from.'}
      </p>
      {error && <div className="page-alert">{error}</div>}
      <div className="model-actions">
        {!ready && <button className="pill-btn pill-btn--dark" disabled={!enough || busy} onClick={build}><span className="pill-inner">{busy ? 'Building…' : 'Build model'}</span></button>}
        {ready && <button className="pill-btn pill-btn--accent" onClick={() => navigate(`/chat/${persona.id}`)}><span className="pill-inner">Chat with {persona.name}</span></button>}
      </div>
    </section>
  )
}

function BackupStep({ persona }) {
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
      <h2 className="page-h2">6. Back up <span className="create-count">optional</span></h2>
      <p className="page-note">Download {persona.name} as one encrypted .chronus file: memories, documents, interview answers, consent record and voice recording. Only someone with the password can open it. Import it on the Models page of any CHRONUS install. Keep the password safe: it can't be recovered.</p>
      <div className="create-upload-row">
        <input className="create-select" type="password" autoComplete="new-password" minLength={8} value={password} onChange={e => setPassword(e.target.value)} placeholder="Password (8+ characters)" aria-label="Password" />
        <input className="create-select" type="password" autoComplete="new-password" value={again} onChange={e => setAgain(e.target.value)} placeholder="Repeat password" aria-label="Repeat password" />
        <button className="pill-btn pill-btn--dark" disabled={!ok || busy}><span className="pill-inner">{busy ? 'Encrypting…' : 'Download backup'}</span></button>
      </div>
      {password && again && password !== again && <p className="page-note">The passwords don't match.</p>}
      {done && <p className="create-saved">✓ Backup downloaded</p>}
      {error && <div className="page-alert">{error}</div>}
    </form>
  )
}

export default function CreatePage({ id }) {
  const [persona, setPersona] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    if (!id) { setPersona(null); return }
    api.persona(id).then(p => {
      if (p.kind !== 'custom') { setError(`${p.name} is a pretrained model and can't be edited.`); return }
      setPersona(p); setError('')
    }).catch(e => setError(e.message))
  }, [id])
  useEffect(load, [load])

  return (
    <div className="page">
      <section className="page-hero page-hero--compact shell">
        <button className="page-back" onClick={() => navigate('/models')}>&larr; All models</button>
        <div className="eyebrow eyebrow--accent">Create your model</div>
        <h1 className="page-h1">{persona ? `Building ${persona.name}` : 'Preserve someone’s memory'}</h1>
        <p className="page-sub">Their own words, collected with consent. CHRONUS answers only from what you add here, and shows the source of every answer.</p>
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
            <div className="page-links">
              <button className="page-link" onClick={() => navigate(`/memories/${persona.id}`)}>Review or correct its memories →</button>
              <button className="page-link" onClick={() => navigate(`/insights/${persona.id}`)}>See what people ask it →</button>
            </div>
          </>
        )}
      </section>
    </div>
  )
}
