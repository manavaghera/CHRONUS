import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { navigate } from '../router'
import { playExclusive, startRecording, stopCurrent, toWav, wavSeconds } from '../audio'
import { useT } from '../i18n'

// Voices this page kept only in the browser before the server tracked them.
// They still exist at Fish Audio, so we offer to delete them there.
const LEGACY_KEY = 'chronus_saved_voices'
const MAX_SECONDS = 60

function readLegacy() {
  try { return JSON.parse(localStorage.getItem(LEGACY_KEY) || '[]').filter(v => v && v.id) } catch { return [] }
}

function writeLegacy(list) {
  try { list.length ? localStorage.setItem(LEGACY_KEY, JSON.stringify(list)) : localStorage.removeItem(LEGACY_KEY) } catch { /* storage blocked */ }
}

export default function CloneVoicePage() {
  const t = useT()
  const [voices, setVoices] = useState([])
  const [legacy, setLegacy] = useState(readLegacy)
  const [consent, setConsent] = useState(false)
  const [cloud, setCloud] = useState(false)
  const [cloudReady, setCloudReady] = useState(null)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [recording, setRecording] = useState(null)
  const [elapsed, setElapsed] = useState(0)
  const [active, setActive] = useState(null)
  const [text, setText] = useState('')
  const [audioUrl, setAudioUrl] = useState(null)

  useEffect(() => {
    api.sandboxVoices().then(setVoices).catch(e => setError(e.message))
    api.voiceStatus().then(s => setCloudReady(s.cloned.configured)).catch(() => setCloudReady(null))
  }, [])

  // Release the previous clip's memory whenever a new one replaces it
  useEffect(() => () => { if (audioUrl) URL.revokeObjectURL(audioUrl) }, [audioUrl])
  // Leaving the page: stop the microphone and any playing clip
  const recordingRef = useRef(null)
  recordingRef.current = recording
  useEffect(() => () => { recordingRef.current?.cancel(); stopCurrent() }, [])

  // Recording timer, auto-stop at the server's 60 s limit
  useEffect(() => {
    if (!recording) return
    const started = Date.now()
    const id = setInterval(() => {
      const s = (Date.now() - started) / 1000
      setElapsed(s)
      if (s >= MAX_SECONDS) stopAndClone()
    }, 250)
    return () => clearInterval(id)
  }, [recording]) // eslint-disable-line react-hooks/exhaustive-deps

  const allowed = consent && cloud && cloudReady !== false && name.trim()

  const clone = async (blob) => {
    setBusy('vs.making'); setError('')
    try {
      const wav = await toWav(blob)
      const seconds = wavSeconds(wav)
      if (seconds < 6) throw new Error(t('vs.tooShort', { seconds: seconds.toFixed(0) }))
      const voice = await api.sandboxClone(name.trim(), wav)
      setVoices(v => [...v, voice])
      setActive(voice.id)
      setName('')
    } catch (e) { setError(e.message) } finally { setBusy('') }
  }

  const onFile = (e) => {
    const file = e.target.files[0]
    e.target.value = ''
    if (file) clone(file)
  }

  const record = async () => {
    setError('')
    try { setElapsed(0); setRecording(await startRecording()) } catch (e) {
      setError(e.name === 'NotAllowedError' ? t('voiceIn.denied') : e.message)
    }
  }

  async function stopAndClone() {
    const r = recording
    setRecording(null)
    if (r) clone(await r.stop())
  }

  const remove = async (voiceId, isLegacy = false) => {
    if (!confirm(t('vs.deleteConfirm'))) return
    setBusy('common.deleting'); setError('')
    try {
      await api.sandboxDelete(voiceId)
      if (isLegacy) { const rest = legacy.filter(v => v.id !== voiceId); setLegacy(rest); writeLegacy(rest) }
      else setVoices(v => v.filter(x => x.id !== voiceId))
      if (active === voiceId) setActive(null)
    } catch (e) { setError(e.message) } finally { setBusy('') }
  }

  const speak = async (line) => {
    if (!line.trim() || !active) return
    setBusy('vs.speaking'); setError('')
    try {
      const url = await api.sandboxSpeak(line.trim(), active)
      setAudioUrl(url)
      await playExclusive(new Audio(url))
    } catch (e) { setError(e.message) } finally { setBusy('') }
  }

  const activeVoice = voices.find(v => v.id === active)

  return (
    <div className="page">
      <section className="page-hero page-hero--compact shell">
        <button className="page-back" onClick={() => navigate('/')}>{t('vs.home')}</button>
        <div className="eyebrow eyebrow--accent">{t('nav.voiceSandbox')}</div>
        <h1 className="page-h1">{t('vs.title')}</h1>
        <p className="page-sub">{t('vs.sub')}</p>
      </section>

      <section className="shell page-section clone-grid">
        <div className="create-card clone-card">
          <h2 className="page-h2">{t('vs.new')}</h2>
          {cloudReady === false && (
            <div className="page-alert">{t('vs.notSetUp').split(/\{(key|file)\}/).map((part, i) => (i % 2 ? <code key={i}>{part === 'key' ? 'FISH_API_KEY=your_key' : 'CHRONUS/.env'}</code> : part))}</div>
          )}
          <label className="create-check">
            <input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />
            <span><strong>{t('create.voiceConsentTitle')}</strong> {t('vs.consentText')}</span>
          </label>
          <label className="create-check">
            <input type="checkbox" checked={cloud} onChange={e => setCloud(e.target.checked)} />
            <span><strong>{t('create.cloudTitle')}</strong> {t('vs.cloudText')}</span>
          </label>
          <input className="create-select" placeholder={t('vs.namePlaceholder')} maxLength={60} value={name} onChange={e => setName(e.target.value)} />
          <blockquote className="clone-script">{t('vs.readThis')} “{t('vs.script')}”</blockquote>
          <div className="clone-actions">
            {recording ? (
              <button className="pill-btn pill-btn--dark clone-recording" onClick={stopAndClone}>
                <span className="pill-inner">{t('vs.stop', { seconds: Math.floor(elapsed) })}</span>
              </button>
            ) : (
              <button className="pill-btn pill-btn--accent" disabled={!allowed || !!busy} onClick={record}>
                <span className="pill-inner">{t('vs.record')}</span>
              </button>
            )}
            <label className={`pill-btn pill-btn--outline create-file${allowed && !busy && !recording ? '' : ' is-disabled'}`}>
              <span className="pill-inner">{t('vs.upload')}</span>
              <input type="file" accept="audio/*,.wav,.mp3,.m4a" disabled={!allowed || !!busy || !!recording} onChange={onFile} />
            </label>
          </div>
          <p className="page-note clone-hint">{t('vs.hint')}</p>
          {busy && <p className="page-note">{t(busy)}</p>}
          {error && <div className="page-alert">{error}</div>}
        </div>

        <div className="create-card clone-card">
          <h2 className="page-h2">{t('vs.yours')} <span className="create-count">{voices.length}</span></h2>
          {voices.length === 0 ? <p className="page-note">{t('vs.none')}</p> : (
            <ul className="clone-list">
              {voices.map(v => (
                <li key={v.id} className={active === v.id ? 'is-active' : ''}>
                  <button className="clone-pick" onClick={() => setActive(v.id)}>
                    <strong>{v.name}</strong>
                    <span>{t('vs.sample', { seconds: v.seconds, date: new Date(v.created_at).toLocaleDateString() })}</span>
                  </button>
                  <button className="model-delete" disabled={!!busy} onClick={() => remove(v.id)}>{t('mem.delete')}</button>
                </li>
              ))}
            </ul>
          )}

          {legacy.length > 0 && (
            <div className="clone-legacy">
              <p className="page-note">{t('vs.legacy')}</p>
              <ul className="clone-list">
                {legacy.map(v => (
                  <li key={v.id}>
                    <span className="clone-pick"><strong>{v.name || t('vs.unnamed')}</strong></span>
                    <button className="model-delete" disabled={!!busy} onClick={() => remove(v.id, true)}>{t('vs.deleteFish')}</button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {activeVoice && (
            <div className="clone-test">
              <h3>{t('vs.test', { name: activeVoice.name })}</h3>
              <button className="demo-quick-btn" disabled={!!busy} onClick={() => speak(t('vs.quickLine'))}>{t('vs.quickTest')}</button>
              <textarea className="create-select" rows={3} maxLength={2000} value={text} onChange={e => setText(e.target.value)} placeholder={t('vs.typePlaceholder')} />
              <button className="pill-btn pill-btn--accent" disabled={!!busy || !text.trim()} onClick={() => speak(text)}>
                <span className="pill-inner">{busy === 'vs.speaking' ? t('vs.synth') : t('vs.speak')}</span>
              </button>
              {audioUrl && <audio className="clone-audio" controls src={audioUrl} />}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
