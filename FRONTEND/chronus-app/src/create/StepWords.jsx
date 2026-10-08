import { useEffect, useState } from 'react'
import { api, AUDIO_ACCEPT, MAX_UPLOAD_MB, UPLOAD_ACCEPT } from '../api'
import { halves, useT } from '../i18n'
import { useToast } from '../lib/toast'
import Icon from '../lib/Icon'

export default function StepWords({ persona, onChange, onNext }) {
  const t = useT()
  const toast = useToast()
  const [by, setBy] = useState('self')
  const [status, setStatus] = useState(null)
  const [errors, setErrors] = useState([])
  const [audio, setAudio] = useState(false)
  const [drag, setDrag] = useState(false)
  const [removing, setRemoving] = useState('')
  useEffect(() => { api.voiceStatus().then(s => setAudio(!!s.speech_to_text?.available)).catch(() => {}) }, [])

  const accept = audio ? `${UPLOAD_ACCEPT},${AUDIO_ACCEPT}` : UPLOAD_ACCEPT
  const allowed = accept.split(',')

  const upload = async (list) => {
    const files = [...(list || [])]
    const failed = []
    for (const file of files) {
      const ext = `.${(file.name.split('.').pop() || '').toLowerCase()}`
      if (!allowed.includes(ext)) {
        failed.push(AUDIO_ACCEPT.includes(ext) ? t('{file}: voice notes need local transcription (faster-whisper) on the server', { file: file.name }) : t('{file}: CHRONUS can’t read {ext} files', { file: file.name, ext }))
        continue
      }
      if (file.size > MAX_UPLOAD_MB * 1024 * 1024) { failed.push(t('{file}: larger than {mb} MB', { file: file.name, mb: MAX_UPLOAD_MB })); continue }
      setStatus({ name: file.name, progress: 0, message: t('Uploading') })
      try {
        const r = await api.uploadDocumentWithProgress(persona.id, file, by, (progress, message) => setStatus({ name: file.name, progress, message }))
        onChange(r.persona)
        toast(t('{file}: {n} memories added', { file: file.name, n: r.upload?.memories ?? 0 }))
      } catch (err) { failed.push(`${file.name}: ${err.message}`) }
    }
    setStatus(null); setErrors(failed)
  }

  const remove = async (filename) => {
    setRemoving(filename)
    try { await api.deleteDocument(persona.id, filename); onChange(await api.persona(persona.id)); toast(t('{file} and its memories were removed', { file: filename })) }
    catch (e) { setErrors([e.message]) } finally { setRemoving('') }
  }

  return (
    <>
      <span className="lab">{t('Step {n} of 6', { n: 3 })}</span>
      <h2 className="wh">{halves(t('Gather|their words.'))}</h2>
      <p className="lede">{audio ? t('Letters, journals, notes, photos of handwritten pages and voice notes. Label each batch by whose words it is: only their own words are ever quoted as theirs.') : t('Letters, journals, notes and photos of handwritten pages. Label each batch by whose words it is: only their own words are ever quoted as theirs.')}</p>
      <div className="seg" role="group" aria-label={t('Whose words are these files')}>
        <button type="button" aria-pressed={by === 'self'} onClick={() => setBy('self')}>{t('{name}’s own words', { name: persona.name })}</button>
        <button type="button" aria-pressed={by === 'other'} onClick={() => setBy('other')}>{t('Written by someone else')}</button>
      </div>
      <label className={`drop${drag ? ' is-drag' : ''}${status ? ' is-busy' : ''}`} htmlFor="w-files" data-cursor={t('Drop')}
        onDragOver={e => { e.preventDefault(); setDrag(true) }} onDragEnter={e => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)} onDrop={e => { e.preventDefault(); setDrag(false); if (!status) upload(e.dataTransfer?.files) }}>
        <span className="drop-ic" aria-hidden="true"><Icon name="upload" size={26} /></span>
        <span className="drop-t">{status ? t('Reading {file}…', { file: status.name }) : t('Drop files here, or choose them')}</span>
        <span className="lab">{accept.replaceAll(',', ' ')} · {t('up to {mb} MB each', { mb: MAX_UPLOAD_MB })}</span>
        <input className="sr-only" id="w-files" type="file" multiple accept={accept} disabled={!!status} onChange={e => { upload(e.target.files); e.target.value = '' }} />
      </label>
      {status && (
        <div className="upl" role="status">
          <div className="row-sb"><span className="small">{status.name}</span><span className="lab">{status.message}</span></div>
          <div className="bar"><i style={{ width: `${Math.round((status.progress || 0) * 100)}%` }} /></div>
        </div>
      )}
      {errors.map(e => <div key={e} className="alert" role="alert">{e}</div>)}
      {persona.uploads.length > 0 && (
        <ul className="flist">
          {persona.uploads.map(u => (
            <li key={u.filename} className="frow">
              <span className="fico" aria-hidden="true">{(u.filename.split('.').pop() || '').slice(0, 4)}</span>
              <span className="col" style={{ minWidth: 0 }}>
                <span className="fname">{u.filename}</span>
                <span className="lab">{t('{n} memories', { n: u.memories })}{u.duplicates_skipped ? ` · ${t('{n} already known', { n: u.duplicates_skipped })}` : ''}{u.kind === 'audio' ? ` · ${t('transcribed')}` : ''}</span>
              </span>
              <span className="prov"><i className={`pm${u.authored_by === 'self' ? '' : ' dash'}`} />{u.authored_by === 'self' ? t('Their words') : t('By others')}</span>
              <button className="icbtn" type="button" aria-label={t('Remove {file}', { file: u.filename })} disabled={!!removing} onClick={() => remove(u.filename)}>
                {removing === u.filename ? <span className="spinner" /> : <Icon name="trash" size={16} />}
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="wfoot">
        <span className="lab">{t('{n} memories so far', { n: persona.memories.toLocaleString() })}</span>
        <button className="btn btn-p btn-sm" type="button" disabled={!!status} onClick={onNext}>{persona.uploads.length ? t('Start the interview') : t('Skip to the interview')}<Icon name="arrow" size={16} /></button>
      </div>
    </>
  )
}
