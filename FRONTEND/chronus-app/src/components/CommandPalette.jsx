import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { navigate } from '../router'
import { tx, useT } from '../i18n'
import useDialog from '../useDialog'
import Icon from '../lib/Icon'
import { SEARCH_EVENT, switchTheme } from './Nav'

const PAGES = tx('Pages'), HOME = tx('On the home page'), YOURS = tx('Your models'), PRE = tx('Pretrained models')
const STATIC = [
  { g: PAGES, t: tx('Preserve someone'), go: '/create', k: tx('Start') },
  { g: PAGES, t: tx('Your models'), go: '/models', k: tx('Page') },
  { g: PAGES, t: tx('Pretrained models'), go: '/pretrained', k: tx('Page') },
  { g: PAGES, t: tx('Voice studio'), go: '/voice', k: tx('Page') },
  { g: PAGES, t: tx('Roundtable'), go: '/roundtable', k: tx('Page') },
  { g: PAGES, t: tx('Insights'), go: '/insights', k: tx('Page') },
  { g: PAGES, t: tx('How it works'), go: '/how-it-works', k: tx('Page') },
  { g: PAGES, t: tx('Pricing'), go: '/pricing', k: tx('Page') },
  { g: PAGES, t: tx('CHRONUS Lab'), go: '/lab', k: tx('Page') },
  { g: PAGES, t: tx('About us'), go: '/about', k: tx('Page') },
  { g: PAGES, t: tx('Trust centre'), go: '/trust', k: tx('Page') },
  { g: PAGES, t: tx('All policies'), go: '/legal', k: tx('Page') },
  { g: PAGES, t: tx('Join the waitlist'), go: '/waitlist', k: tx('Page') },
  { g: PAGES, t: tx('Contact'), go: '/contact', k: tx('Page') },
  { g: PAGES, t: tx('Your account'), go: '/account', k: tx('Page') },
  { g: HOME, t: tx('How preserving works'), anchor: 'preserve', k: tx('Jump') },
  { g: HOME, t: tx('How an answer is made'), anchor: 'how', k: tx('Jump') },
  { g: HOME, t: tx('Memory field'), anchor: 'field', k: tx('Jump') },
  { g: HOME, t: tx('Features'), anchor: 'features', k: tx('Jump') },
  { g: HOME, t: tx('Questions'), anchor: 'faq', k: tx('Jump') },
  { g: tx('Actions'), t: tx('Switch light and dark theme'), action: 'theme', k: tx('Theme') },
]

// Ctrl/⌘ K: jump to any page, section or model
export default function CommandPalette() {
  const t = useT()
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [idx, setIdx] = useState(0)
  const [models, setModels] = useState([])
  const listRef = useRef(null)
  const ref = useDialog(open, () => setOpen(false))

  useEffect(() => {
    const show = () => { setOpen(true); setQ(''); setIdx(0) }
    const key = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setOpen(o => !o); setQ(''); setIdx(0) }
    }
    window.addEventListener(SEARCH_EVENT, show)
    window.addEventListener('keydown', key)
    return () => { window.removeEventListener(SEARCH_EVENT, show); window.removeEventListener('keydown', key) }
  }, [])

  // Real models, fetched when the palette opens
  useEffect(() => {
    if (!open) return
    api.personas().then(list => setModels([
      ...list.filter(p => p.status === 'ready').map(p => ({ g: p.kind === 'custom' ? YOURS : PRE, t: t('Talk to {name}', { name: p.name }), raw: true, go: `/chat/${p.id}`, k: p.kind === 'custom' ? t('Yours') : t('Chat') })),
      ...list.filter(p => p.kind === 'custom').map(p => ({ g: YOURS, t: t('{name}’s memories', { name: p.name }), raw: true, go: `/memories/${p.id}`, k: t('Memories') })),
    ])).catch(() => setModels([]))
  }, [open, t])

  const items = useMemo(() => {
    const all = [...STATIC.slice(0, 6), ...models, ...STATIC.slice(6)].map(it => (it.raw ? { ...it, g: t(it.g) } : { ...it, g: t(it.g), t: t(it.t), k: t(it.k) }))
    const s = q.trim().toLowerCase()
    return all.filter(it => !s || `${it.t} ${it.g} ${it.k}`.toLowerCase().includes(s))
  }, [q, models, t])
  const active = Math.min(idx, Math.max(0, items.length - 1))

  useEffect(() => { listRef.current?.querySelector('[data-active="y"]')?.scrollIntoView({ block: 'nearest' }) }, [active])

  if (!open) return null
  const run = (it) => {
    setOpen(false)
    if (it.action === 'theme') switchTheme()
    else if (it.go) navigate(it.go)
    else if (it.anchor) { window.location.hash = it.anchor }
  }
  const onKey = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setIdx((active + 1) % Math.max(1, items.length)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setIdx((active - 1 + items.length) % Math.max(1, items.length)) }
    else if (e.key === 'Enter' && items[active]) { e.preventDefault(); run(items[active]) }
  }

  return (
    <div className="dlg" role="dialog" aria-modal="true" aria-label={t('Search CHRONUS')}>
      <button className="dlg-bg" type="button" aria-label={t('Close search')} tabIndex={-1} onClick={() => setOpen(false)} />
      <div className="card dlg-p cmd-p" ref={ref}>
        <div className="cmd-in">
          <Icon name="search" size={20} />
          <label className="sr-only" htmlFor="cmd-q">{t('Search pages, sections and models')}</label>
          <input id="cmd-q" autoFocus autoComplete="off" placeholder={t('Search pages, sections, models…')} value={q}
            onChange={e => { setQ(e.target.value.slice(0, 60)); setIdx(0) }} onKeyDown={onKey} />
          <kbd>Esc</kbd>
        </div>
        <div className="cmd-list" ref={listRef}>
          {items.map((it, i) => (
            <div key={`${it.g}-${it.t}`}>
              {(i === 0 || items[i - 1].g !== it.g) && <div className="cmd-g lab">{it.g}</div>}
              <button type="button" className="cmd-it" data-active={i === active ? 'y' : 'n'} onMouseEnter={() => setIdx(i)} onClick={() => run(it)}>
                <span>{it.t}</span><span className="k">{it.k}</span>
              </button>
            </div>
          ))}
          {!items.length && <p className="small" style={{ padding: '24px 12px' }}>{t('Nothing matches “{q}”.', { q })}</p>}
        </div>
        <div className="cmd-f"><span><kbd>↑</kbd> <kbd>↓</kbd> {t('move')}</span><span><kbd>Enter</kbd> {t('open')}</span><span><kbd>Esc</kbd> {t('close')}</span></div>
      </div>
    </div>
  )
}
