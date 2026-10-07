// Browser-side audio helpers.
//
// The server only accepts 16-bit PCM .wav voice samples (it checks their
// length before anything is sent to Fish Audio), but microphones record
// WebM/MP4 and people have .mp3/.m4a files. toWav() decodes any format the
// browser can play and re-encodes it as mono 16-bit WAV.

const TARGET_RATE = 24000 // plenty for speech; keeps 60 s under 3 MB

export async function toWav(blob) {
  const Ctx = window.AudioContext || window.webkitAudioContext
  if (!Ctx) throw new Error('This browser cannot convert audio; please upload a .wav file')
  const ctx = new Ctx()
  let decoded
  try {
    decoded = await ctx.decodeAudioData(await blob.arrayBuffer())
  } catch {
    throw new Error("Couldn't read this audio file; try a .wav, .mp3 or .m4a recording")
  } finally {
    ctx.close?.()
  }
  // Mix down to mono and resample with an offline context
  const length = Math.ceil(decoded.duration * TARGET_RATE)
  const offline = new OfflineAudioContext(1, length, TARGET_RATE)
  const source = offline.createBufferSource()
  source.buffer = decoded
  source.connect(offline.destination)
  source.start()
  const rendered = await offline.startRendering()
  return new Blob([encodeWav(rendered.getChannelData(0), TARGET_RATE)], { type: 'audio/wav' })
}

export function encodeWav(samples, rate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2)
  const view = new DataView(buffer)
  const text = (offset, s) => { for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i)) }
  text(0, 'RIFF'); view.setUint32(4, 36 + samples.length * 2, true); text(8, 'WAVE')
  text(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true)
  view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true); view.setUint16(32, 2, true); view.setUint16(34, 16, true)
  text(36, 'data'); view.setUint32(40, samples.length * 2, true)
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return buffer
}

export function wavSeconds(blob) {
  // 44-byte header, 16-bit mono at TARGET_RATE (only for blobs made by toWav)
  return Math.max(0, (blob.size - 44) / 2 / TARGET_RATE)
}

// Record from the microphone. Returns { stop() -> Promise<Blob>, cancel(), done }.
// onSilence: called once after the speaker has talked and then been quiet
// for silenceMs (hands-free voice conversation stops itself this way).
export async function startRecording({ onSilence, silenceMs = 1400, maxMs = 30000 } = {}) {
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
    throw new Error('Recording is not supported in this browser')
  }
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  const recorder = new MediaRecorder(stream)
  const chunks = []
  let watcher = null, ctx = null
  recorder.ondataavailable = e => e.data.size && chunks.push(e.data)
  const release = () => {
    clearInterval(watcher)
    ctx?.close?.()
    stream.getTracks().forEach(t => t.stop())
  }
  const done = new Promise((resolve, reject) => {
    recorder.onstop = () => { release(); resolve(new Blob(chunks, { type: recorder.mimeType })) }
    recorder.onerror = (e) => { release(); reject(e.error || new Error('Recording failed')) }
  })
  recorder.start()
  if (onSilence) {
    const Ctx = window.AudioContext || window.webkitAudioContext
    ctx = new Ctx()
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 1024
    ctx.createMediaStreamSource(stream).connect(analyser)
    const buf = new Float32Array(analyser.fftSize)
    const started = Date.now()
    let heard = false, lastLoud = started
    watcher = setInterval(() => {
      analyser.getFloatTimeDomainData(buf)
      const rms = Math.sqrt(buf.reduce((s, v) => s + v * v, 0) / buf.length)
      const now = Date.now()
      if (rms > 0.02) { heard = true; lastLoud = now }
      if ((heard && now - lastLoud > silenceMs) || now - started > maxMs) {
        clearInterval(watcher)
        onSilence()
      }
    }, 100)
  }
  return {
    done,
    stop: () => { if (recorder.state !== 'inactive') recorder.stop(); return done },
    cancel: () => { if (recorder.state !== 'inactive') recorder.stop(); release() },
  }
}

// Speak with the browser's built-in voice; resolves when finished.
export function speakBrowser(text, lang) {
  return new Promise((resolve) => {
    if (!window.speechSynthesis) { resolve(); return }
    stopCurrent()
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    if (lang) u.lang = lang
    u.onend = u.onerror = () => resolve()
    window.speechSynthesis.speak(u)
  })
}

// Play an audio URL exclusively; resolves when it ends or is stopped.
export function playUntilEnd(url) {
  return new Promise((resolve) => {
    const audio = new Audio(url)
    const finish = () => { URL.revokeObjectURL(url); resolve() }
    audio.onended = finish
    audio.onerror = finish
    playExclusive(audio, finish).catch(finish)
  })
}

// One audio element at a time across the whole site: starting a new answer
// stops whatever was playing (two Listen buttons used to talk over each other).
let current = null
export function playExclusive(audio, onStop) {
  if (current && current.audio !== audio) {
    current.audio.pause()
    current.onStop?.()
  }
  current = { audio, onStop }
  window.speechSynthesis?.cancel()
  return audio.play()
}
export function stopCurrent() {
  if (current) { current.audio.pause(); current.onStop?.(); current = null }
}
