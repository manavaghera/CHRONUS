import { useEffect, useState } from 'react'
import { halves, tx, useT } from '../i18n'
import useDialog from '../useDialog'
import Icon from '../lib/Icon'
import { SEARCH_EVENT, switchTheme } from './Nav'

// First visit this session: the dial's hand sweeps once while the name
// writes itself, then the page shows through. Skipped for reduced motion.
export function Intro() {
  const [state, setState] = useState(() => {
    try { if (sessionStorage.getItem('chronus-intro')) return 'done' } catch { /* blocked */ }
    return document.documentElement.classList.contains('motion') ? 'on' : 'done'
  })
  useEffect(() => {
    if (state !== 'on') return
    try { sessionStorage.setItem('chronus-intro', '1') } catch { /* blocked */ }
    const a = setTimeout(() => setState('out'), 1250)
    const b = setTimeout(() => setState('done'), 2000)
    return () => { clearTimeout(a); clearTimeout(b) }
  }, [state])
  if (state === 'done') return null
  return (
    <div className={`intro${state === 'out' ? ' is-out' : ''}`} aria-hidden="true">
      <div className="intro-in">
        <svg viewBox="0 0 120 120" className="intro-dial">
          <circle cx="60" cy="60" r="54" className="id-ring" />
          <line x1="60" y1="60" x2="60" y2="14" className="id-hand" />
          <circle cx="60" cy="60" r="4" className="id-dot" />
        </svg>
        <span className="intro-word">{'CHRONUS'.split('').map((c, i) => <i key={i} style={{ animationDelay: `${0.25 + i * 0.06}s` }}>{c}</i>)}</span>
        <span className="intro-line"><i /></span>
      </div>
    </div>
  )
}

const KEYS = [
  [['Ctrl', 'K'], tx('Search pages, sections and models')],
  [['T'], tx('Switch light and dark theme')],
  [['/'], tx('Jump to the chat box (on a chat page)')],
  [['?'], tx('Show these shortcuts')],
  [['Esc'], tx('Close a dialog')],
]

// Global shortcuts (ignored while typing in a field) and a sheet listing them
export function Shortcuts() {
  const t = useT()
  const [open, setOpen] = useState(false)
  const ref = useDialog(open, () => setOpen(false))
  useEffect(() => {
    const onKey = (e) => {
      const el = e.target
      if (e.ctrlKey || e.metaKey || e.altKey || el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return
      if (e.key === '?') { e.preventDefault(); setOpen(o => !o) }
      else if (e.key === 't' || e.key === 'T') { switchTheme() }
      else if (e.key === '/') {
        e.preventDefault()
        const chat = document.getElementById('chat-in')
        if (chat) chat.focus(); else window.dispatchEvent(new Event(SEARCH_EVENT))
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  if (!open) return null
  return (
    <div className="dlg center" role="dialog" aria-modal="true" aria-labelledby="keys-h">
      <button className="dlg-bg" type="button" aria-label={t('Close')} tabIndex={-1} onClick={() => setOpen(false)} />
      <div className="card dlg-p" ref={ref}>
        <button className="icbtn dlg-x" type="button" aria-label={t('Close')} onClick={() => setOpen(false)}><Icon name="close" size={16} /></button>
        <span className="over">{t('Keyboard')}</span>
        <h2 id="keys-h" className="h3">{t('Shortcuts')}</h2>
        <ul className="keys">{KEYS.map(([k, d]) => <li key={d}><span>{t(d)}</span><span className="row gap8">{k.map(x => <kbd key={x}>{x}</kbd>)}</span></li>)}</ul>
      </div>
    </div>
  )
}

export function NotFound() {
  const t = useT()
  return (
    <section className="nf" aria-labelledby="nf-h">
      <div className="wrap col gap16" style={{ alignItems: 'center', textAlign: 'center' }}>
        <span className="nf-code" aria-hidden="true">404</span>
        <h1 id="nf-h" className="h2">{halves(t('This page wasn’t|preserved.'))}</h1>
        <p className="lede">{t('CHRONUS says “I don’t know” when it has nothing to go on. So does this address.')}</p>
        <div className="row wrap-row gap12" style={{ justifyContent: 'center' }}>
          <a className="btn btn-a" href="#/">{t('Go home')}<Icon name="arrow" /></a>
          <a className="btn btn-s" href="#/models">{t('Your models')}</a>
        </div>
      </div>
    </section>
  )
}
