import { useEffect, useState } from 'react'
import { useT } from '../i18n'
import Icon from '../lib/Icon'

// Reading progress bar, the floating "Preserve someone" dock (home only)
// and a back-to-top button whose ring fills as you read.
export default function ScrollChrome({ home }) {
  const t = useT()
  const [dock, setDock] = useState(false)
  const [top, setTop] = useState(false)

  useEffect(() => {
    let raf = 0
    const update = () => {
      raf = 0
      const se = document.scrollingElement || document.documentElement
      const max = se.scrollHeight - window.innerHeight
      const y = window.scrollY
      document.documentElement.style.setProperty('--sp', max > 0 ? Math.min(1, y / max).toFixed(4) : '0')
      setTop(y > window.innerHeight)
      setDock(y > window.innerHeight * 2.4 && y < max - 900)
    }
    const onScroll = () => { if (!raf) raf = requestAnimationFrame(update) }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => { window.removeEventListener('scroll', onScroll); window.removeEventListener('resize', onScroll); cancelAnimationFrame(raf) }
  }, [])

  return (
    <>
      <div className="prog" aria-hidden="true" />
      {home && (
        <a className={`dock${dock ? ' is-on' : ''}`} href="#/create" tabIndex={dock ? 0 : -1} aria-hidden={!dock}>
          <span className="pulse" aria-hidden="true" />
          {t('Preserve someone you love')}
          <span className="go" aria-hidden="true"><Icon name="arrow" /></span>
        </a>
      )}
      <a className={`totop${top ? ' is-on' : ''}`} href="#main" aria-label={t('Back to top')} tabIndex={top ? 0 : -1}
        onClick={e => { e.preventDefault(); window.scrollTo({ top: 0, behavior: 'smooth' }) }}>
        <Icon name="up" />
      </a>
    </>
  )
}
