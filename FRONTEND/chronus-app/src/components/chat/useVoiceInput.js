import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../../api'
import { startRecording, toWav } from '../../audio'

// Voice input. Prefers the server's local Whisper (services/stt.py: audio
// never leaves this computer); otherwise the browser's own speech
// recognition, which in Chrome sends audio to Google, so callers show that.
//
// listen({ auto }) resolves with the transcript; auto stops on silence
// (hands-free conversation). state: idle | listening | transcribing.

let statusPromise = null
function sttStatus() {
  statusPromise ??= api.voiceStatus().then(s => !!s.speech_to_text?.available).catch(() => false)
  return statusPromise
}

const BrowserRecognition = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition)

const LANG_TAGS = { en: 'en-IN', hi: 'hi-IN', gu: 'gu-IN', mr: 'mr-IN', bn: 'bn-IN', ta: 'ta-IN', te: 'te-IN', kn: 'kn-IN', ml: 'ml-IN', pa: 'pa-IN', ur: 'ur-IN' }

export default function useVoiceInput(language) {
  const [engine, setEngine] = useState(BrowserRecognition ? 'browser' : null)
  const [state, setState] = useState('idle')
  const [error, setError] = useState('')
  const active = useRef(null)

  useEffect(() => {
    let cancelled = false
    sttStatus().then(local => { if (!cancelled && local) setEngine('local') })
    return () => { cancelled = true; active.current?.cancel?.() }
  }, [])

  const stop = useCallback(() => active.current?.finish?.(), [])

  const listen = useCallback(async ({ auto = false } = {}) => {
    setError('')
    if (engine === 'local') {
      let rec
      try {
        rec = await startRecording(auto ? { onSilence: () => active.current?.finish?.() } : {})
      } catch (e) {
        setError(e.name === 'NotAllowedError' ? 'Microphone access was denied.' : e.message)
        throw e
      }
      setState('listening')
      return new Promise((resolve, reject) => {
        active.current = {
          cancel: () => { rec.cancel(); setState('idle'); reject(new Error('cancelled')) },
          finish: async () => {
            active.current = null
            try {
              const blob = await rec.stop()
              setState('transcribing')
              const { text } = await api.transcribe(await toWav(blob), language && language !== 'auto' ? language : undefined)
              resolve(text)
            } catch (e) { setError(e.message); reject(e) } finally { setState('idle') }
          },
        }
      })
    }
    if (engine === 'browser') {
      return new Promise((resolve, reject) => {
        const r = new BrowserRecognition()
        r.lang = LANG_TAGS[language] || navigator.language || 'en-US'
        r.interimResults = false
        r.maxAlternatives = 1
        let text = ''
        r.onresult = (e) => { text = Array.from(e.results).map(x => x[0].transcript).join(' ') }
        r.onerror = (e) => { setError(e.error === 'not-allowed' ? 'Microphone access was denied.' : `Speech recognition: ${e.error}`) }
        r.onend = () => { active.current = null; setState('idle'); text ? resolve(text) : reject(new Error('nothing heard')) }
        active.current = { cancel: () => r.abort(), finish: () => r.stop() }
        setState('listening')
        r.start()
      })
    }
    throw new Error('Voice input is not available in this browser')
  }, [engine, language])

  return { engine, state, error, listen, stop, cancel: () => active.current?.cancel?.() }
}
