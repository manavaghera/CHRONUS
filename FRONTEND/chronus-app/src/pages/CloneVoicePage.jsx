import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { navigate } from '../router'
import { playExclusive, startRecording, stopCurrent, toWav, wavSeconds } from '../audio'

// Voices this page kept only in the browser before the server tracked them.
// They still exist at Fish Audio, so we offer to delete them there.
const LEGACY_KEY = 'chronus_saved_voices'
const MAX_SECONDS = 60
const READ_ALOUD = 'The quick brown fox jumps over the lazy dog. I am recording this short paragraph so a private test voice can be made from it. I can delete this voice whenever I want, and it is deleted from the cloud service too.'

function readLegacy() {
  try { return JSON.parse(localStorage.getItem(LEGACY_KEY) || '[]').filter(v => v && v.id) } catch { return [] }
}

function writeLegacy(list) {
  try { list.length ? localStorage.setItem(LEGACY_KEY, JSON.stringify(list)) : localStorage.removeItem(LEGACY_KEY) } catch { /* storage blocked */ }
}

export default function CloneVoicePage() {
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
    setBusy('Making the voice…'); setError('')
    try {
      const wav = await toWav(blob)
      const seconds = wavSeconds(wav)
      if (seconds < 6) throw new Error(`That was ${seconds.toFixed(0)} s; please record 6-60 seconds of clear speech`)
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
      setError(e.name === 'NotAllowedError' ? 'Microphone access was denied.' : e.message)
    }
  }

  async function stopAndClone() {
    const r = recording
    setRecording(null)
    if (r) clone(await r.stop())
  }

  const remove = async (voiceId, isLegacy = false) => {
    if (!confirm('Delete this voice here and at Fish Audio? This cannot be undone.')) return
    setBusy('Deleting…'); setError('')
    try {
      await api.sandboxDelete(voiceId)
      if (isLegacy) { const rest = legacy.filter(v => v.id !== voiceId); setLegacy(rest); writeLegacy(rest) }
      else setVoices(v => v.filter(x => x.id !== voiceId))
      if (active === voiceId) setActive(null)
    } catch (e) { setError(e.message) } finally { setBusy('') }
  }

  const speak = async (line) => {
    if (!line.trim() || !active) return
    setBusy('Speaking…'); setError('')
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
        <button className="page-back" onClick={() => navigate('/')}>&larr; Home</button>
        <div className="eyebrow eyebrow--accent">Voice sandbox</div>
        <h1 className="page-h1">Clone &amp; test a voice</h1>
        <p className="page-sub">Try a cloned voice without building a whole model. Only clone a voice with the speaker's permission: the recording goes to Fish Audio, and deleting the voice here deletes it there too.</p>
      </section>

      <section className="shell page-section clone-grid">
        <div className="create-card clone-card">
          <h2 className="page-h2">1. New voice</h2>
          {cloudReady === false && (
            <div className="page-alert">Cloud voice isn't set up yet: add <code>FISH_API_KEY=your_key</code> to <code>CHRONUS/.env</code>, then restart the server.</div>
          )}
          <label className="create-check">
            <input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />
            <span><strong>Voice consent.</strong> This is my voice, or the speaker (or their estate) agreed to it being cloned.</span>
          </label>
          <label className="create-check">
            <input type="checkbox" checked={cloud} onChange={e => setCloud(e.target.checked)} />
            <span><strong>Cloud processing.</strong> I agree that the recording, and any text I play, is sent to Fish Audio.</span>
          </label>
          <input className="create-select" placeholder="Name this voice (e.g. My voice)" maxLength={60} value={name} onChange={e => setName(e.target.value)} />
          <blockquote className="clone-script">Read this aloud: “{READ_ALOUD}”</blockquote>
          <div className="clone-actions">
            {recording ? (
              <button className="pill-btn pill-btn--dark clone-recording" onClick={stopAndClone}>
                <span className="pill-inner">■ Stop · {Math.floor(elapsed)} s</span>
              </button>
            ) : (
              <button className="pill-btn pill-btn--accent" disabled={!allowed || !!busy} onClick={record}>
                <span className="pill-inner">🎙 Record</span>
              </button>
            )}
            <label className={`pill-btn pill-btn--outline create-file${allowed && !busy && !recording ? '' : ' is-disabled'}`}>
              <span className="pill-inner">Upload audio</span>
              <input type="file" accept="audio/*,.wav,.mp3,.m4a" disabled={!allowed || !!busy || !!recording} onChange={onFile} />
            </label>
          </div>
          <p className="page-note clone-hint">6-60 seconds of clear speech. Any audio format works; it is converted to .wav in your browser.</p>
          {busy && <p className="page-note">{busy}</p>}
          {error && <div className="page-alert">{error}</div>}
        </div>

        <div className="create-card clone-card">
          <h2 className="page-h2">2. Your test voices <span className="create-count">{voices.length}</span></h2>
          {voices.length === 0 ? <p className="page-note">No voices yet.</p> : (
            <ul className="clone-list">
              {voices.map(v => (
                <li key={v.id} className={active === v.id ? 'is-active' : ''}>
                  <button className="clone-pick" onClick={() => setActive(v.id)}>
                    <strong>{v.name}</strong>
                    <span>{v.seconds} s sample · {new Date(v.created_at).toLocaleDateString()}</span>
                  </button>
                  <button className="model-delete" disabled={!!busy} onClick={() => remove(v.id)}>Delete</button>
                </li>
              ))}
            </ul>
          )}

          {legacy.length > 0 && (
            <div className="clone-legacy">
              <p className="page-note">Saved only in this browser by an older version of this page. They still exist at Fish Audio:</p>
              <ul className="clone-list">
                {legacy.map(v => (
                  <li key={v.id}>
                    <span className="clone-pick"><strong>{v.name || 'Unnamed voice'}</strong></span>
                    <button className="model-delete" disabled={!!busy} onClick={() => remove(v.id, true)}>Delete from Fish Audio</button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {activeVoice && (
            <div className="clone-test">
              <h3>Test “{activeVoice.name}”</h3>
              <button className="demo-quick-btn" disabled={!!busy} onClick={() => speak('Hello! This is a quick test of how this cloned voice sounds.')}>Quick test</button>
              <textarea className="create-select" rows={3} maxLength={2000} value={text} onChange={e => setText(e.target.value)} placeholder="Type anything to hear it in this voice…" />
              <button className="pill-btn pill-btn--accent" disabled={!!busy || !text.trim()} onClick={() => speak(text)}>
                <span className="pill-inner">{busy === 'Speaking…' ? 'Synthesizing…' : 'Speak'}</span>
              </button>
              {audioUrl && <audio className="clone-audio" controls src={audioUrl} />}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
