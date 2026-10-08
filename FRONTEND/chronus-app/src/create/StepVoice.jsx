import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { playExclusive, startRecording, stopCurrent, toWav, wavSeconds } from '../audio'
import { halves, useT } from '../i18n'
import { useToast } from '../lib/toast'
import Icon from '../lib/Icon'

const MAX_SECONDS = 60
// About 100 words: 40-55 seconds read aloud, inside the 60 s limit. Statements,
// a question and an exclamation give the clone its range of intonation, and
// the words cover most English sounds (th, ch, sh, j, v, zh in “pleasure”).
const SCRIPT = [
  'Hello. I’m recording this so my voice can be kept, just the way it sounds today. When I was young, we lived in a small house near the river, and every morning my mother sang while she made tea.',
  'Do you remember the old radio in the kitchen? It crackled, but we loved it! It’s still a pleasure to take long walks, enjoy quiet evenings, and hear good stories told slowly. Some days are busy, some are calm, and that’s all right.',
  'If you’re listening to this one day, I hope it makes you smile. Thank you, and take care of each other.',
]

export function ReadAloud({ label }) {
  const t = useT()
  return (
    <blockquote className="script">
      <span className="lab">{label}</span>
      <div lang="en">{SCRIPT.map(p => <p key={p.slice(0, 12)}>{p}</p>)}</div>
      <span className="note">{t('About 45 seconds at a relaxed pace. Pauses are fine.')}</span>
    </blockquote>
  )
}

// Recording UI shared by the Create page and the voice studio
export function Recorder({ disabled, onAudio, busy }) {
  const t = useT()
  const [rec, setRec] = useState(null)
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState('')
  const recRef = useRef(null)
  recRef.current = rec
  useEffect(() => () => recRef.current?.cancel(), [])
  useEffect(() => {
    if (!rec) return
    const started = Date.now()
    const id = setInterval(() => {
      const s = (Date.now() - started) / 1000
      setElapsed(s)
      if (s >= MAX_SECONDS) stop()
    }, 200)
    return () => clearInterval(id)
  }, [rec]) // eslint-disable-line react-hooks/exhaustive-deps

  const start = async () => {
    setError('')
    try { setElapsed(0); setRec(await startRecording()) } catch (e) { setError(e.name === 'NotAllowedError' ? t('Microphone access was blocked. Allow it in your browser settings.') : e.message) }
  }
  async function stop() {
    const r = recRef.current
    setRec(null)
    if (r) onAudio(await r.stop())
  }
  return (
    <div className="recorder">
      <button type="button" className={`rec-btn${rec ? ' is-on' : ''}`} disabled={disabled || busy} onClick={rec ? stop : start}
        aria-label={rec ? t('Stop recording') : t('Start recording')} data-cursor={rec ? t('Stop') : t('Record')}>
        <Icon name={rec ? 'stop' : 'mic'} size={26} />
      </button>
      <div className="col gap8" style={{ flex: 1, minWidth: 0 }}>
        <div className={`rec-bars${rec ? ' is-on' : ''}`} aria-hidden="true">{Array.from({ length: 40 }, (_, i) => <i key={i} style={{ '--d': `${(i % 8) * 0.07}s`, '--h': `${25 + ((i * 41) % 70)}%` }} />)}</div>
        <div className="row-sb"><span className="lab">{rec ? t('Recording · {s} s of {max}', { s: Math.floor(elapsed), max: MAX_SECONDS }) : busy ? t('Working…') : t('Ready to record')}</span>
          <label className={`linkbtn${disabled || busy || rec ? ' is-off' : ''}`}>{t('or upload a recording')}
            <input className="sr-only" type="file" accept="audio/*,.wav,.mp3,.m4a" disabled={disabled || busy || !!rec} onChange={e => { const f = e.target.files[0]; e.target.value = ''; if (f) onAudio(f) }} />
          </label>
        </div>
      </div>
      {error && <div className="alert" role="alert" style={{ flexBasis: '100%' }}>{error}</div>}
    </div>
  )
}

export function NotConfigured() {
  const t = useT()
  return <div className="alert">{t('Voice cloning isn’t set up on this server. Add')} <code>FISH_API_KEY=your_key</code> {t('to')} <code>CHRONUS/.env</code> {t('and restart it.')}</div>
}

export default function StepVoice({ persona, onChange, consentText, onNext }) {
  const t = useT()
  const toast = useToast()
  const [consent, setConsent] = useState(false)
  const [cloud, setCloud] = useState(false)
  const [ready, setReady] = useState(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [line, setLine] = useState(`Hello. It’s ${persona.name.split(' ')[0]}.`)
  useEffect(() => { api.voiceStatus().then(s => setReady(!!s.cloned?.configured)).catch(() => setReady(null)) }, [])
  useEffect(() => () => stopCurrent(), [])

  const clone = async (blob) => {
    setBusy('making'); setError('')
    try {
      const wav = await toWav(blob)
      if (wavSeconds(wav) < 6) throw new Error(t('That recording is only {s} seconds. Record at least 10 seconds of them speaking.', { s: wavSeconds(wav).toFixed(0) }))
      onChange(await api.addVoice(persona.id, wav, consentText?.language || 'en'))
      toast(t('{name}’s voice is ready', { name: persona.name }))
    } catch (e) { setError(e.message) } finally { setBusy('') }
  }
  const test = async () => {
    setBusy('speaking'); setError('')
    try { const url = await api.speak(persona.id, line.trim()); await playExclusive(new Audio(url)) } catch (e) { setError(e.message) } finally { setBusy('') }
  }
  const remove = async () => {
    setBusy('removing'); setError('')
    try { onChange(await api.removeVoice(persona.id)); toast(t('Their voice was deleted here and at Fish Audio')) } catch (e) { setError(e.message) } finally { setBusy('') }
  }
  const busyText = { making: t('Making their voice…'), speaking: t('Speaking…'), removing: t('Removing…') }[busy]

  return (
    <>
      <span className="lab">{t('Step {n} of 6', { n: 5 })} · {t('optional')}</span>
      <h2 className="wh">{halves(t('Clone|their voice.'))}</h2>
      <p className="lede">{t('With consent, 10 to 60 seconds of {name} speaking becomes a private cloned voice, so answers can be heard the way they talk. Voice is biometric data: removing it deletes it everywhere.', { name: persona.name })}</p>
      {persona.voice ? (
        <div className="voice-ready">
          <div className="row gap12"><span className="vr-ic"><Icon name="wave" size={22} /></span><div className="col"><b>{t('Their voice is ready')}</b><span className="lab">{t('{s} s sample', { s: persona.voice.seconds })} · {persona.voice.provider}</span></div></div>
          <label className="fld" htmlFor="v-line">{t('Hear a line in their voice')}
            <input id="v-line" className="field" maxLength={300} value={line} onChange={e => setLine(e.target.value)} />
          </label>
          <div className="row wrap-row gap8">
            <button className="btn btn-a btn-sm" type="button" disabled={!!busy || !line.trim() || persona.status !== 'ready'} onClick={test}><Icon name="play" size={14} />{busy === 'speaking' ? t('Speaking…') : t('Play')}</button>
            <button className="btn btn-d btn-sm" type="button" disabled={!!busy} onClick={remove}><Icon name="trash" size={14} />{t('Remove their voice')}</button>
          </div>
          {persona.status !== 'ready' && <p className="note">{t('You can play it once the model is built.')}</p>}
        </div>
      ) : (
        <>
          {ready === false && <NotConfigured />}
          <label className="check"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} /><span><b>{t('Voice consent.')}</b> {consentText?.voice || t('This person, or their estate, agreed to their voice being used for this model.')}</span></label>
          <label className="check"><input type="checkbox" checked={cloud} onChange={e => setCloud(e.target.checked)} /><span><b>{t('Cloud processing.')}</b> {t('The recording is sent to Fish Audio to make the voice.')}</span></label>
          <ReadAloud label={t('If they are with you, ask them to read')} />
          <Recorder disabled={!consent || !cloud || ready === false} busy={!!busy} onAudio={clone} />
          {busy && <p className="row gap8 small"><span className="spinner" />{busyText}</p>}
        </>
      )}
      {error && <div className="alert" role="alert">{error}</div>}
      <div className="wfoot">
        <span className="lab">{persona.voice ? t('Voice added') : t('You can skip this')}</span>
        <button className="btn btn-p btn-sm" type="button" onClick={onNext}>{t('Review and build')}<Icon name="arrow" size={16} /></button>
      </div>
    </>
  )
}
