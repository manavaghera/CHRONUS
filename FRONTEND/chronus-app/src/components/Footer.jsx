import { applyTheme, storedTheme, THEME_EVENT } from '../theme'
import { useEffect, useState } from 'react'
import { tx, useT } from '../i18n'
import Icon from '../lib/Icon'
import { COMPANY } from '../site/content'

const THEMES = [['auto', tx('System')], ['light', tx('Light')], ['dark', tx('Dark')]]
const COLUMNS = [
  ['b', tx('Product'), [['#/how-it-works', tx('How it works')], ['#/pricing', tx('Pricing')], ['#/pretrained', tx('Pretrained models')],
    ['#/voice', tx('Voice studio')], ['#/roundtable', tx('Roundtable')], ['#/lab', tx('CHRONUS Lab')]]],
  ['c', tx('Company'), [['#/about', tx('About us')], ['#/vision', tx('Vision')], ['#/research', tx('Research')],
    ['#/partners', tx('For partners')], ['#/contact', tx('Contact')], ['#/waitlist', tx('Join the waitlist')]]],
  ['e', tx('Trust & legal'), [['#/trust', tx('Trust centre')], ['#/legal/privacy', tx('Privacy')], ['#/legal/terms', tx('Terms')],
    ['#/legal', tx('All policies')], ['#/report', tx('Report a model')], ['#/wellbeing', tx('Wellbeing and support')]]],
]

export default function Footer() {
  const t = useT()
  const [theme, setTheme] = useState(storedTheme)
  useEffect(() => {
    const update = () => setTheme(storedTheme())
    window.addEventListener(THEME_EVENT, update)
    return () => window.removeEventListener(THEME_EVENT, update)
  }, [])
  return (
    <footer className="foot">
      <div className="wrap">
        <div className="fgrid f4">
          <div className="a">
            <a className="brand" href="#/"><Icon name="logo" size={24} />CHRONUS</a>
            <p className="small" style={{ maxWidth: 340 }}>{t('Preserve a person’s personality, memories and voice from their own words, with their consent.')}</p>
            <span className="lab" style={{ marginTop: 8 }}>{t('Theme')}</span>
            <div className="seg" role="group" aria-label={t('Theme')}>
              {THEMES.map(([k, label]) => <button key={k} type="button" aria-pressed={theme === k} onClick={() => applyTheme(k)}>{t(label)}</button>)}
            </div>
          </div>
          {COLUMNS.map(([cls, title, links]) => (
            <nav key={cls} className={cls} aria-label={t(title)}>
              <span className="lab">{t(title)}</span>
              {links.map(([href, label]) => <a key={href} className="flink" href={href}>{t(label)}</a>)}
            </nav>
          ))}
        </div>
        <div className="fbottom">
          <span className="lab">© 2026 {COMPANY.name}</span>
          <span className="lab">{t('Registered in {where}, company no. {number}', { where: COMPANY.registeredIn, number: COMPANY.number })} · {COMPANY.office}</span>
        </div>
      </div>
    </footer>
  )
}
