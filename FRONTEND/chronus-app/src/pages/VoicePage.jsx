import { useEffect, useState } from 'react'
import { api } from '../api'
import { playExclusive, stopCurrent, toWav, wavSeconds } from '../audio'
import { useLanguage } from '../i18n'
import { SplitWords } from '../lib/motion'
import { useToast } from '../lib/toast'
import Icon from '../lib/Icon'
import { NotConfigured, ReadAloud, Recorder } from '../create/StepVoice'

// Voice studio (services/voice_sandbox.py): try cloning a voice on its own,
// tracked by the server and deletable here and at Fish Audio
export default function VoicePage() {
  const { t, lang } = useLanguage()
  const toast = useToast()
  const [voices, setVoices] = useState([])
  const [ready, setReady] = useState(null)
  const [consent, setConsent] = useState(false)
  const [cloud, setCloud] = useState(false)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [active, setActive] = useState(null)
  const [text, setText] = useState('')
  const [audioUrl, setAudioUrl] = useState(null)

  useEffect(() => {
    api.sandboxVoices().then(setVoices).catch(e => setError(e.message))
    api.voiceStatus().then(s => setReady(!!s.cloned?.configured)).catch(() => setReady(null))
    return () => stopCurrent()
  }, [])
  useEffect(() => () => { if (audioUrl) URL.revokeObjectURL(audioUrl) }, [audioUrl])

  const allowed = consent && cloud && ready !== false && name.trim()
  const clone = async (blob) => {
    setBusy('cloning'); setError('')
    try {
      const wav = await toWav(blob)
      const s = wavSeconds(wav)
      if (s < 6) throw new Error(t('That recording is only {s} seconds; record at least 10.', { s: s.toFixed(0) }))
      const v = await api.sandboxClone(name.trim(), wav)
      setVoices(list => [...list, v]); setActive(v.id); setName(''); toast(t('{name}’s voice is ready', { name: v.name }))
    } catch (e) { setError(e.message) } finally { setBusy('') }
  }
  const speak = async (line) => {
    if (!line.trim() || !active) return
    setBusy('speaking'); setError('')
    try { const url = await api.sandboxSpeak(line.trim(), active); setAudioUrl(url); await playExclusive(new Audio(url)) } catch (e) { setError(e.message) } finally { setBusy('') }
  }
  const remove = async (v) => {
    if (!window.confirm(t('Delete {name}’s voice here and at Fish Audio?', { name: v.name }))) return
    setBusy('deleting'); setError('')
    try { await api.sandboxDelete(v.id); setVoices(list => list.filter(x => x.id !== v.id)); if (active === v.id) setActive(null); toast(t('Voice deleted')) }
    catch (e) { setError(e.message) } finally { setBusy('') }
  }
  const current = voices.find(v => v.id === active)
  const busyText = { cloning: t('Cloning the voice…'), speaking: t('Speaking…'), deleting: t('Deleting…') }[busy]

  return (
    <div className="page">
      <section className="page-hero">
        <div className="page-hero-bg" aria-hidden="true" />
        <div className="wrap">
          <nav className="crumbs" aria-label={t('Breadcrumb')}><a href="#/">{t('Home')}</a><span aria-hidden="true">/</span><span>{t('Voice studio')}</span></nav>
          <span className="over">{t('Voice cloning · with consent')}</span>
          <SplitWords as="h1" className="h1" text={t('Keep the voice')} em={t('you’d know anywhere.')} />
          <p className="lede">{t('Try cloning a voice from 10 to 60 seconds of speech. To give a preserved model their voice, add it on the model’s Voice step instead.')}</p>
        </div>
      </section>
      <section className="sec" style={{ paddingTop: 24 }}>
        <div className="wrap vgrid">
          <div className="card vcard">
            <h2 className="h3">{t('New voice')}</h2>
            {ready === false && <NotConfigured />}
            <label className="check"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} /><span><b>{t('Consent.')}</b> {t('The person speaking agreed to their voice being cloned.')}</span></label>
            <label className="check"><input type="checkbox" checked={cloud} onChange={e => setCloud(e.target.checked)} /><span><b>{t('Cloud processing.')}</b> {t('The recording is sent to Fish Audio to make the voice. Deleting it here deletes it there.')}</span></label>
            <label className="fld" htmlFor="vname">{t('Whose voice is this?')}<input id="vname" className="field" maxLength={60} placeholder={t('Name')} value={name} onChange={e => setName(e.target.value)} /></label>
            <ReadAloud label={t('Read this aloud')} />
            <Recorder disabled={!allowed} busy={!!busy} onAudio={clone} />
            {busy && <p className="row gap8 small"><span className="spinner" />{busyText}</p>}
            {error && <div className="alert" role="alert">{error}</div>}
          </div>
          <div className="card vcard">
            <div className="row-sb"><h2 className="h3">{t('Your voices')}</h2><span className="badge">{voices.length}</span></div>
            {!voices.length && <p className="small">{t('No voices yet. Clone one on the left.')}</p>}
            <ul className="vlist">
              {voices.map(v => (
                <li key={v.id} className={active === v.id ? 'is-on' : ''}>
                  <button type="button" className="vpick" onClick={() => setActive(v.id)} aria-pressed={active === v.id}>
                    <span className="vr-ic"><Icon name="wave" size={18} /></span>
                    <span className="col"><b>{v.name}</b><span className="lab">{t('{s} s sample', { s: v.seconds })} · {new Date(v.created_at).toLocaleDateString(lang)}</span></span>
                  </button>
                  <button type="button" className="icbtn" aria-label={t('Delete {name}', { name: v.name })} disabled={!!busy} onClick={() => remove(v)}><Icon name="trash" size={16} /></button>
                </li>
              ))}
            </ul>
            {current && (
              <div className="vtest">
                <span className="lab">{t('Test {name}’s voice', { name: current.name })}</span>
                <button type="button" className="btn btn-s btn-sm" disabled={!!busy} onClick={() => speak('Hello, it’s good to hear from you again.')}><Icon name="play" size={14} />{t('Quick test')}</button>
                <textarea className="field" rows={3} maxLength={2000} placeholder={t('Type anything for them to say')} value={text} onChange={e => setText(e.target.value)} />
                <button type="button" className="btn btn-a btn-sm" disabled={!!busy || !text.trim()} onClick={() => speak(text)}>{busy === 'speaking' ? t('Speaking…') : t('Speak it')}</button>
                {audioUrl && <audio className="vaudio" controls src={audioUrl} />}
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
