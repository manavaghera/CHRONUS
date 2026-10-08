import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { useT } from '../i18n'
import { DIMENSIONS, ORIGINS } from '../lib/data'
import useVoiceInput from '../chat/useVoiceInput'
import Icon from '../lib/Icon'

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
      <button type="button" className={`btn btn-s btn-sm${voice.state !== 'idle' ? ' is-rec' : ''}`} onClick={click} disabled={voice.state === 'transcribing'}
        title={voice.engine === 'local' ? t('Transcribed on this computer') : t('Uses your browser’s speech recognition')}>
        <Icon name={voice.state === 'listening' ? 'stop' : 'mic'} size={16} />
        {voice.state === 'listening' ? t('Stop') : voice.state === 'transcribing' ? t('Transcribing…') : t('Speak the answer')}
      </button>
      {voice.error && <span className="note">{voice.error}</span>}
    </>
  )
}

function FollowUp({ item, persona, origin, onJump, onSaved }) {
  const t = useT()
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [state, setState] = useState('idle')
  const [error, setError] = useState('')
  if (item.kind === 'protocol') {
    return <li className="fu"><span className="small">{t(item.question)}</span><button type="button" className="linkbtn" onClick={() => onJump(item.id)}>{t('Go to {id}', { id: item.id })}</button></li>
  }
  const save = async () => {
    setState('saving'); setError('')
    try { await api.answerFollowup(persona.id, { question: item.question, answer: text, origin }); setState('saved'); setOpen(false); onSaved() }
    catch (e) { setError(e.message); setState('idle') }
  }
  return (
    <li className="fu">
      <span className="small" lang="en">{item.question}</span>
      {state === 'saved' ? <span className="badge ok">{t('Saved')}</span> : !open && <button type="button" className="linkbtn" onClick={() => setOpen(true)}>{t('Answer')}</button>}
      {open && (
        <div className="fu-form">
          <textarea className="field" rows={2} maxLength={4000} value={text} onChange={e => setText(e.target.value)} placeholder={t('Their answer')} />
          <div className="row wrap-row gap8">
            <button type="button" className="btn btn-p btn-sm" disabled={!text.trim() || state === 'saving'} onClick={save}>{state === 'saving' ? t('Saving…') : t('Save')}</button>
            <Dictate onText={h => setText(x => (x ? `${x} ${h}` : h))} />
          </div>
          {error && <div className="alert" role="alert">{error}</div>}
        </div>
      )}
    </li>
  )
}

export default function StepInterview({ persona, onChange, onNext }) {
  const t = useT()
  const [questions, setQuestions] = useState(null)
  const [error, setError] = useState('')
  const answered = useMemo(() => new Set(persona.interview_answered), [persona.interview_answered])
  const [qi, setQi] = useState(() => Math.max(0, DIMENSIONS.flatMap(d => d.ids).findIndex(id => !persona.interview_answered.includes(id))))
  const [origin, setOrigin] = useState(persona.relationship === 'self' ? 'self' : persona.memorial ? (['family', 'friend', 'colleague'].includes(persona.relationship) ? persona.relationship : 'family') : 'self')
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)
  const [followups, setFollowups] = useState([])

  useEffect(() => { api.interviewQuestions().then(d => setQuestions(d.questions)).catch(e => setError(e.message)) }, [])
  const order = DIMENSIONS.flatMap(d => d.ids)
  const byId = Object.fromEntries((questions || []).map(q => [q.id, q]))
  const qid = order[Math.min(qi, order.length - 1)]
  const q = byId[qid]
  const dimIndex = DIMENSIONS.findIndex(d => d.ids.includes(qid))
  const isAnswered = answered.has(qid)
  const move = (n) => { setQi(Math.max(0, Math.min(order.length - 1, n))); setText(''); setFollowups([]) }

  const save = async () => {
    setSaving(true); setError('')
    try {
      const r = await api.answerInterview(persona.id, { question_id: qid, answer: text.trim(), origin })
      onChange(r.persona); setFollowups(r.followups || []); setText('')
    } catch (e) { setError(e.message) } finally { setSaving(false) }
  }

  return (
    <>
      <span className="lab">{t('Step {n} of 6', { n: 4 })}</span>
      <h2 className="wh">{t('The')} <em>{t('interview.')}</em></h2>
      <p className="lede">{t('25 questions across six parts of who they are. Best answered with them, in their own words. Skip anything; come back any time.')}</p>
      <div className="fld"><span id="org-l">{t('Who is answering')}</span>
        <div className="chips" role="group" aria-labelledby="org-l">
          {ORIGINS.map(([v, label]) => (
            <button key={v} type="button" className="chip" aria-pressed={origin === v} disabled={persona.memorial && v === 'self'} onClick={() => setOrigin(v)}>
              {v === 'self' ? (persona.relationship === 'self' ? t('I am answering as myself') : t('{name} is answering', { name: persona.name })) : t(label)}
            </button>
          ))}
        </div>
      </div>
      <div className="dimtabs" role="group" aria-label={t('Interview dimensions')}>
        {DIMENSIONS.map((d, i) => (
          <button key={d.key} type="button" className="dt" aria-pressed={i === dimIndex} onClick={() => move(order.indexOf(d.ids[0]))}>
            {t(d.label)}<b>{d.ids.filter(id => answered.has(id)).length}/{d.ids.length}</b>
          </button>
        ))}
      </div>
      {error && <div className="alert" role="alert">{error}</div>}
      <div className="qcard" key={qid}>
        <div className="row-sb"><span className="lab">{t('Question {n} of 25', { n: qi + 1 })} · {t(DIMENSIONS[dimIndex]?.label || '')}</span>{isAnswered && <span className="badge ok">{t('Answered')}</span>}</div>
        <p className="qbig">{q ? t(q.question) : questions ? '' : t('Loading the questions…')}</p>
        <label className="sr-only" htmlFor="w-ans">{t('Answer')}</label>
        <textarea id="w-ans" className="field" maxLength={4000} value={text} onChange={e => setText(e.target.value)}
          placeholder={isAnswered ? t('Type a new answer to replace the saved one') : origin === 'self' ? t('In their own words…') : t('What would they say? Use their words where you remember them.')} />
        <div className="row-sb wrap-row gap12">
          <span className="prov"><i className={`pm${origin === 'self' ? '' : ' dash'}`} />{origin === 'self' ? t('Saved as their own words') : t('Saved as written by others')}</span>
          <div className="row wrap-row gap8">
            <Dictate onText={h => setText(x => (x ? `${x} ${h}` : h))} />
            <button type="button" className="btn btn-p btn-sm" disabled={!text.trim() || saving || !q} onClick={save}>{saving ? t('Saving…') : t('Save answer')}</button>
          </div>
        </div>
      </div>
      {followups.length > 0 && (
        <div className="fups">
          <span className="lab">{t('Follow-ups worth asking next')}</span>
          <ul>{followups.map(f => <FollowUp key={f.question} item={f} persona={persona} origin={origin}
            onJump={(id) => move(order.indexOf(id))} onSaved={() => api.persona(persona.id).then(onChange).catch(() => {})} />)}</ul>
        </div>
      )}
      <div className="col gap8">
        <span className="lab">{t('{n} of 25 answered', { n: answered.size })}{persona.followups_answered ? ` · ${t('{n} follow-ups', { n: persona.followups_answered })}` : ''}</span>
        <div className="bar"><i style={{ width: `${(answered.size / 25) * 100}%` }} /></div>
      </div>
      <div className="wfoot">
        <div className="row gap8">
          <button className="btn btn-s btn-sm" type="button" disabled={qi <= 0} onClick={() => move(qi - 1)}>{t('Previous')}</button>
          <button className="btn btn-s btn-sm" type="button" disabled={qi >= order.length - 1} onClick={() => move(qi + 1)}>{t('Next question')}</button>
        </div>
        <button className="btn btn-p btn-sm" type="button" onClick={onNext}>{t('Their voice')}<Icon name="arrow" size={16} /></button>
      </div>
    </>
  )
}
