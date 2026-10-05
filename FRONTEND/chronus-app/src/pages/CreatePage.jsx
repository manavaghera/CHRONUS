import { useCallback, useEffect, useState } from 'react'
import { api, MAX_UPLOAD_MB, UPLOAD_ACCEPT } from '../api'
import { navigate } from '../router'

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
  const [form, setForm] = useState({ name: '', description: '', relationship: 'family', allow_cloud_llm: false, consent: false })
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
      <p className="page-note">Letters, journals, emails, speeches, transcripts ({UPLOAD_ACCEPT.replaceAll(',', ', ')}; up to {MAX_UPLOAD_MB} MB each). Word files: save as PDF or .txt first.</p>
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

function Question({ q, personaId, answered, origin, onSaved }) {
  const [text, setText] = useState('')
  const [state, setState] = useState(answered ? 'saved' : 'idle')
  const [error, setError] = useState('')

  const save = async () => {
    setState('saving'); setError('')
    try {
      onSaved((await api.answerInterview(personaId, { question_id: q.id, answer: text, origin })).persona)
      setState('saved'); setText('')
    } catch (err) { setState('idle'); setError(err.message) }
  }

  return (
    <div className="create-question">
      <label htmlFor={`q-${q.id}`}><span className="create-qid">{q.id}</span>{q.question}{state === 'saved' && <span className="create-saved">✓ saved</span>}</label>
      <textarea id={`q-${q.id}`} rows={3} maxLength={4000} value={text} onChange={e => setText(e.target.value)}
        placeholder={state === 'saved' ? 'Answered. Write here to replace the saved answer.' : 'Answer in their words, as they would.'} />
      {error && <div className="page-alert">{error}</div>}
      <button className="demo-quick-btn" disabled={!text.trim() || state === 'saving'} onClick={save}>{state === 'saving' ? 'Saving…' : 'Save answer'}</button>
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
      <h2 className="page-h2">3. Interview <span className="create-count">{persona.interview_answered.length}/25</span></h2>
      <p className="page-note">25 questions across six parts of a personality. Answer as many as you can; even a few fill gaps the documents leave.</p>
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
              answered={persona.interview_answered.includes(id)} onSaved={onChange} />
          ))}
        </details>
      ))}
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
          </>
        )}
      </section>
    </div>
  )
}
