import { useEffect, useRef, useState } from 'react'
import { applyTheme, isDark, THEME_EVENT } from '../theme'
import { LANGUAGES, tx, useLanguage } from '../i18n'
import Icon from '../lib/Icon'

export const SEARCH_EVENT = 'chronus:search'

const LINKS = [
  ['#/models', tx('Your models'), 'models'],
  ['#/pretrained', tx('Pretrained'), 'pretrained'],
  ['#/roundtable', tx('Roundtable'), 'roundtable'],
  ['#/voice', tx('Voice studio'), 'voice'],
  ['#/insights', tx('Insights'), 'insights'],
]

// Theme switch with a circular reveal from the button (View Transitions)
export function switchTheme(e) {
  const next = isDark() ? 'light' : 'dark'
  const reduce = !document.documentElement.classList.contains('motion')
  if (!document.startViewTransition || reduce) { applyTheme(next); return }
  const r = e?.currentTarget?.getBoundingClientRect?.()
  const x = r ? r.left + r.width / 2 : window.innerWidth - 60
  const y = r ? r.top + r.height / 2 : 32
  const de = document.documentElement.style
  de.setProperty('--vt-x', `${x}px`)
  de.setProperty('--vt-y', `${y}px`)
  de.setProperty('--vt-r', `${Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y))}px`)
  document.startViewTransition(() => applyTheme(next))
}

export function useDark() {
  const [dark, setDark] = useState(isDark)
  useEffect(() => {
    const update = () => setDark(isDark())
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
    window.addEventListener(THEME_EVENT, update)
    mq?.addEventListener?.('change', update)
    return () => { window.removeEventListener(THEME_EVENT, update); mq?.removeEventListener?.('change', update) }
  }, [])
  return dark
}

// Site language: a small menu of English, हिन्दी, ગુજરાતી
function LanguageMenu() {
  const { lang, setLang, t } = useLanguage()
  const [open, setOpen] = useState(false)
  const box = useRef(null)
  useEffect(() => {
    if (!open) return
    const close = (e) => { if (!box.current?.contains(e.target)) setOpen(false) }
    const esc = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('pointerdown', close)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('pointerdown', close); document.removeEventListener('keydown', esc) }
  }, [open])
  const current = LANGUAGES.find(l => l[0] === lang)
  return (
    <div className="langm" ref={box}>
      <button className="icbtn lang-btn" type="button" aria-haspopup="true" aria-expanded={open} aria-label={t('Language: {name}', { name: current[1] })} onClick={() => setOpen(o => !o)}>
        <span lang={lang}>{current[2]}</span>
      </button>
      {open && (
        <div className="lang-pop card" role="group" aria-label={t('Language')}>
          {LANGUAGES.map(([code, name]) => (
            <button key={code} type="button" lang={code} aria-pressed={lang === code} onClick={() => { setLang(code); setOpen(false) }}>
              {name}{lang === code && <Icon name="check" size={14} />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Nav({ page }) {
  const { t } = useLanguage()
  const dark = useDark()
  const [solid, setSolid] = useState(false)
  const [hidden, setHidden] = useState(false)
  const [menu, setMenu] = useState(false)

  // Solid after the first scroll; slides away scrolling down, back scrolling up
  useEffect(() => {
    let last = window.scrollY
    const onScroll = () => {
      const y = window.scrollY
      setSolid(y > 16)
      setHidden(y > 480 && y > last + 4)
      if (y < last - 4) setHidden(false)
      last = y
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])
  useEffect(() => setMenu(false), [page])

  return (
    <header className={`nav${solid || page || menu ? ' is-solid' : ''}${hidden && !menu ? ' is-hidden' : ''} ${dark ? 'is-dark' : 'is-light'}`}>
      <div className="wrap nav-in">
        <a className="brand" href="#/" aria-label={t('CHRONUS home')}><Icon name="logo" size={24} />CHRONUS</a>
        <nav className="nlinks" aria-label={t('Main')}>
          {LINKS.map(([href, label, key]) => (
            <a key={href} className="nlink" href={href} aria-current={key && key === page ? 'page' : undefined}>{t(label)}</a>
          ))}
        </nav>
        <div className="nav-r">
          <button className="sbtn" type="button" aria-haspopup="dialog" onClick={() => window.dispatchEvent(new Event(SEARCH_EVENT))}>
            <Icon name="search" size={16} /><span className="sbtn-t">{t('Search')}</span><kbd>Ctrl K</kbd>
          </button>
          <LanguageMenu />
          <button className="icbtn" type="button" aria-label={dark ? t('Switch to light theme') : t('Switch to dark theme')} onClick={switchTheme}>
            <span style={{ display: 'grid' }}><Icon name="sun" className="th-sun" /><Icon name="moon" className="th-moon" /></span>
          </button>
          <a className="btn btn-a btn-sm nav-cta" href="#/create">{t('Preserve someone')}</a>
          <button className="icbtn menu-btn" type="button" aria-label={t('Menu')} aria-expanded={menu} onClick={() => setMenu(m => !m)}>
            <Icon name={menu ? 'close' : 'menu'} />
          </button>
        </div>
      </div>
      {menu && (
        <nav className="mpanel" aria-label={t('Main')}>
          {LINKS.map(([href, label]) => <a key={href} href={href} onClick={() => setMenu(false)}>{t(label)}</a>)}
          <a href="#/create" onClick={() => setMenu(false)}>{t('Preserve someone')}</a>
        </nav>
      )}
    </header>
  )
}
