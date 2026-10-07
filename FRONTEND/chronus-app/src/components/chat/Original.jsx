import { useEffect, useRef, useState } from 'react'
import { originalUrl } from '../../api'
import { useT } from '../../i18n'

// The voice note or photo a memory came from (services/originals.py): play the
// moment it was said, or open the scanned letter.
export default function Original({ personaId, original }) {
  const audio = useRef(null)
  const [playing, setPlaying] = useState(false)
  const t = useT()
  useEffect(() => () => audio.current?.pause(), [])
  if (!personaId || !original) return null
  const url = originalUrl(personaId, original.file)

  if (original.kind !== 'audio') {
    return (
      <a className="src-open" href={url} target="_blank" rel="noopener noreferrer">
        {t('chat.viewOriginal')}{original.page ? ` (${t('chat.page', { page: original.page })})` : ''}
      </a>
    )
  }
  const toggle = () => {
    if (playing) { audio.current?.pause(); return }
    // Media fragment: just the stretch of the recording this memory came from
    const range = original.start != null ? `#t=${original.start}${original.end != null ? `,${original.end}` : ''}` : ''
    audio.current = new Audio(url + range)
    audio.current.onpause = audio.current.onended = () => setPlaying(false)
    audio.current.play().then(() => setPlaying(true)).catch(() => setPlaying(false))
  }
  return (
    <button className="src-open" onClick={toggle}>
      {playing ? t('chat.stop') : `${t('chat.playOriginal')}${original.at ? ` (${original.at})` : ''}`}
    </button>
  )
}
