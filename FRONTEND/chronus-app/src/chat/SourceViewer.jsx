import { useEffect, useState } from 'react'
import { api } from '../api'
import { tx, useT } from '../i18n'
import useDialog from '../useDialog'
import Icon from '../lib/Icon'

export const VOICES = { first_person: tx('Own words'), third_party: tx('Written by others'), synthesized: tx('Synthesized') }
export const matchPct = (d) => Math.max(0, Math.round((1 - d) * 100))

// Interview transcripts that don't name their speakers may run the host's
// words into the quote (services/provenance.py speaker_verified)
export function SpeakerNote({ source, t }) {
  if (source?.speaker_verified !== false) return null
  return (
    <span className="badge" title={t('This transcript doesn’t say who is speaking, so the quote may include the interviewer’s words.')}>
      {source.speaker_inferred ? t('Speaker identified by AI') : t('Speaker not verified')}
    </span>
  )
}

// A cited memory in full, with the text around it
export default function SourceViewer({ personaId, source, index, onClose }) {
  const t = useT()
  const [memory, setMemory] = useState(null)
  const [error, setError] = useState('')
  const memoryId = source?.memory_id
  const ref = useDialog(!!source, onClose)

  useEffect(() => {
    if (!memoryId) return
    let cancelled = false
    api.memory(personaId, memoryId).then(m => !cancelled && setMemory(m)).catch(e => !cancelled && setError(e.message))
    return () => { cancelled = true }
  }, [personaId, memoryId])

  if (!source) return null
  const context = memory?.context
  return (
    <div className="dlg center" role="dialog" aria-modal="true" aria-labelledby="viewer-title">
      <button className="dlg-bg" type="button" aria-label={t('Close')} tabIndex={-1} onClick={onClose} />
      <div className="card dlg-p viewer" ref={ref}>
        <button className="icbtn dlg-x" type="button" aria-label={t('Close')} onClick={onClose}><Icon name="close" size={16} /></button>
        <span className="over">{t('Source {n}', { n: index + 1 })}</span>
        <h2 id="viewer-title" className="h3" lang="en">{source.citation || source.source_file}</h2>
        <div className="row wrap-row gap8">
          {source.voice && <span className="prov"><i className={`pm${source.voice === 'first_person' ? '' : source.voice === 'synthesized' ? ' dot' : ' dash'}`} />{t(VOICES[source.voice] || source.voice)}</span>}
          {source.distance != null && <span className="badge">{t('Match {pct}%', { pct: matchPct(source.distance) })}</span>}
          <SpeakerNote source={source} t={t} />
          {memory?.date && !['unknown', 'protocol'].includes(memory.date) && <span className="badge">{memory.date}</span>}
          {memory?.page && <span className="badge">{t('Page {n}', { n: memory.page })}</span>}
        </div>
        {error && <div className="alert" role="alert">{error}</div>}
        <blockquote className="v-quote" lang="en">{memory?.text || source.quote}</blockquote>
        {context?.kind === 'paragraph' && <div className="v-ctx"><span className="lab">{t('In context')}</span><p lang="en">{context.text}</p></div>}
        {context?.kind === 'pages' && (
          <div className="v-ctx"><span className="lab">{t('Neighbouring pages')}</span>{context.pages.map(p => <p key={p.page} lang="en"><b>p. {p.page}</b> {p.text}</p>)}</div>
        )}
        {/^https:\/\/(www\.)?(youtube\.com|youtu\.be|x\.com|twitter\.com)\//.test(source.url || '') && (
          <a className="btn btn-s btn-sm" href={source.url} target="_blank" rel="noopener noreferrer">{source.at ? t('Watch at {at}', { at: source.at }) : t('Open the original')}<Icon name="out" size={14} /></a>
        )}
      </div>
    </div>
  )
}
