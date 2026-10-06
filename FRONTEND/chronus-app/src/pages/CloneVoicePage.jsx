import { useState, useEffect } from 'react'
import { api } from '../api'
import { navigate } from '../router'

export default function CloneVoicePage() {
  const [voices, setVoices] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('chronus_saved_voices') || '[]')
    } catch { return [] }
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [customText, setCustomText] = useState('')
  const [audioUrl, setAudioUrl] = useState(null)
  const [activeVoice, setActiveVoice] = useState(null)
  
  const [isRecording, setIsRecording] = useState(false)
  const [mediaRecorder, setMediaRecorder] = useState(null)

  useEffect(() => {
    localStorage.setItem('chronus_saved_voices', JSON.stringify(voices))
  }, [voices])

  const processFile = async (file) => {
    if (!file) return
    const name = prompt("Enter a name for this cloned voice (e.g. My Voice, John's Voice):", "Recorded Voice")
    if (!name) return

    setBusy(true); setError(''); setAudioUrl(null)
    try {
      const id = await api.quickClone(file)
      const newVoice = { id, name, date: new Date().toISOString() }
      setVoices([...voices, newVoice])
      setActiveVoice(id)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const handleUpload = (e) => {
    const file = e.target.files[0]
    e.target.value = ''
    processFile(file)
  }

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      const chunks = []
      recorder.ondataavailable = e => chunks.push(e.data)
      recorder.onstop = () => {
        const blob = new Blob(chunks, { type: recorder.mimeType })
        const ext = recorder.mimeType.includes('mp4') ? 'mp4' : 'webm'
        const file = new File([blob], `recording.${ext}`, { type: recorder.mimeType })
        processFile(file)
      }
      recorder.start()
      setMediaRecorder(recorder)
      setIsRecording(true)
    } catch (err) {
      setError("Microphone access denied or unavailable.")
    }
  }

  const stopRecording = () => {
    if (mediaRecorder) {
      mediaRecorder.stop()
      mediaRecorder.stream.getTracks().forEach(t => t.stop())
      setIsRecording(false)
    }
  }

  const handleSpeak = async (text, voiceId) => {
    if (!text) return;
    setBusy(true); setError(''); setAudioUrl(null)
    try {
      const url = await api.quickSpeak(text, voiceId)
      setAudioUrl(url)
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  const handleDelete = (idToRemove) => {
    setVoices(voices.filter(v => v.id !== idToRemove))
    if (activeVoice === idToRemove) setActiveVoice(null)
  }

  return (
    <div className="page" style={{ paddingTop: '100px', minHeight: '100vh', background: 'var(--bg)' }}>
      <section className="page-hero page-hero--compact shell">
        <button className="page-back" onClick={() => navigate('/')}>&larr; Home</button>
        <div className="eyebrow eyebrow--accent">Voice Sandbox</div>
        <h1 className="page-h1">Clone & Test Voices</h1>
        <p className="page-sub">Upload a short audio clip to clone a voice instantly. Save them locally and test text-to-speech without creating a full model.</p>
      </section>

      <section className="shell page-section" style={{ display: 'grid', gap: '2rem', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))' }}>
        
        {/* Left Col: Saved Voices & Upload */}
        <div className="create-card">
          <h2 className="page-h2">Your Voices</h2>
          
          <div style={{ padding: '1rem', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '8px', marginBottom: '1.5rem' }}>
            <p style={{ fontWeight: 'bold', marginBottom: '0.5rem', color: 'var(--text)' }}>Ready to clone your voice?</p>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-dim)', marginBottom: '1rem' }}>Click Record and read the following text clearly:</p>
            <blockquote style={{ fontSize: '0.95rem', fontStyle: 'italic', borderLeft: '3px solid #00d2ff', paddingLeft: '1rem', color: 'var(--text)', margin: 0, lineHeight: 1.5 }}>
              "The quick brown fox jumps over the lazy dog. Voice cloning technology allows us to capture the unique phonetic patterns, pitch, and cadence of a speaker. By reading this short paragraph, the system has enough acoustic data to synthesize my voice naturally."
            </blockquote>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
            {isRecording ? (
              <button className="pill-btn" style={{ flex: 1, background: '#ff6b6b', color: 'white', borderColor: '#ff6b6b', animation: 'pulse 1.5s infinite' }} onClick={stopRecording}>
                <span className="pill-inner">⏹ Stop Recording</span>
              </button>
            ) : (
              <button className="pill-btn pill-btn--accent" style={{ flex: 1 }} disabled={busy} onClick={startRecording}>
                <span className="pill-inner">🎙 Record</span>
              </button>
            )}
            
            <label className="pill-btn pill-btn--dark create-file" style={{ flex: 1, textAlign: 'center', cursor: 'pointer' }}>
              <span className="pill-inner">{busy && !activeVoice && !isRecording ? 'Uploading...' : '📁 Upload .wav'}</span>
              <input type="file" accept=".wav,audio/wav" disabled={busy || isRecording} onChange={handleUpload} />
            </label>
          </div>

          {voices.length === 0 ? (
            <p className="page-note">No voices saved yet.</p>
          ) : (
            <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {voices.map(v => (
                <li key={v.id} style={{ 
                  padding: '1rem', 
                  background: activeVoice === v.id ? 'rgba(0, 210, 255, 0.1)' : 'var(--bg)', 
                  border: activeVoice === v.id ? '1px solid #00d2ff' : '1px solid var(--border)',
                  borderRadius: '8px',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease'
                }} onClick={() => setActiveVoice(v.id)}>
                  <div>
                    <strong style={{ display: 'block', color: 'var(--text)' }}>{v.name}</strong>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: '4px' }}>ID: {v.id.substring(0,8)}...</div>
                  </div>
                  <button onClick={(e) => { e.stopPropagation(); handleDelete(v.id) }} style={{ background: 'rgba(255,0,0,0.1)', border: '1px solid rgba(255,0,0,0.2)', color: '#ff6b6b', cursor: 'pointer', padding: '0.5rem', borderRadius: '4px' }}>✕</button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Right Col: Testing Area */}
        <div className="create-card">
          <h2 className="page-h2">Testing Area</h2>
          {error && <div className="page-alert" style={{ marginBottom: '1rem' }}>{error}</div>}
          
          {!activeVoice ? (
            <p className="page-note">Select a voice from the left or upload a new one to start testing.</p>
          ) : (
            <div>
              <p style={{ marginBottom: '1.5rem', fontSize: '1.1rem', color: 'var(--text)' }}>Active Voice: <strong style={{ color: '#00d2ff' }}>{voices.find(v => v.id === activeVoice)?.name}</strong></p>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <button className="demo-quick-btn" disabled={busy} onClick={() => handleSpeak("Hello! This is a quick test to see how my cloned voice sounds.", activeVoice)}>
                  Quick Test: "Hello! This is a quick test..."
                </button>
                
                <div style={{ position: 'relative', marginTop: '1rem' }}>
                  <textarea 
                    rows={4}
                    value={customText}
                    onChange={e => setCustomText(e.target.value)}
                    placeholder="Type anything here to hear it in the cloned voice..."
                    style={{ width: '100%', padding: '1rem', background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text)', borderRadius: '8px', fontFamily: 'inherit', resize: 'vertical' }}
                  />
                  <button 
                    className="pill-btn pill-btn--accent" 
                    disabled={busy || !customText.trim()} 
                    onClick={() => handleSpeak(customText, activeVoice)}
                    style={{ marginTop: '1rem', width: '100%' }}
                  >
                    <span className="pill-inner">{busy ? 'Synthesizing...' : 'Speak Custom Text'}</span>
                  </button>
                </div>
              </div>

              {audioUrl && (
                <div style={{ marginTop: '2rem', animation: 'fadeIn 0.5s ease-in', padding: '1.5rem', background: 'rgba(0,210,255,0.05)', borderRadius: '8px', border: '1px solid rgba(0,210,255,0.2)' }}>
                  <p style={{ marginBottom: '0.5rem', color: '#00d2ff', fontSize: '0.9rem', fontWeight: 'bold' }}>Synthesis Complete!</p>
                  <audio controls src={audioUrl} autoPlay style={{ width: '100%' }} />
                </div>
              )}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
