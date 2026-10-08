import { applyTheme, storedTheme, THEME_EVENT } from '../theme'
import { useEffect, useState } from 'react'
import { LANGUAGES, tx, useLanguage } from '../i18n'
import Icon from '../lib/Icon'

const THEMES = [['auto', tx('System')], ['light', tx('Light')], ['dark', tx('Dark')]]

export default function Footer() {
  const { lang, setLang, t } = useLanguage()
  const [theme, setTheme] = useState(storedTheme)
  useEffect(() => {
    const update = () => setTheme(storedTheme())
    window.addEventListener(THEME_EVENT, update)
    return () => window.removeEventListener(THEME_EVENT, update)
  }, [])
  return (
    <footer className="foot">
      <div className="wrap">
        <div className="fgrid">
          <div className="a">
            <a className="brand" href="#/"><Icon name="logo" size={24} />CHRONUS</a>
            <p className="small" style={{ maxWidth: 340 }}>{t('Preserve a person’s personality, memories and voice from their own words, with their consent.')}</p>
          </div>
          <div className="b">
            <span className="lab">{t('Preserve')}</span>
            <a className="flink" href="#/create">{t('Preserve someone')}</a>
            <a className="flink" href="#/models">{t('Your models')}</a>
            <a className="flink" href="#/voice">{t('Voice studio')}</a>
            <a className="flink" href="#/insights">{t('Insights')}</a>
          </div>
          <div className="c">
            <span className="lab">{t('Explore')}</span>
            <a className="flink" href="#how">{t('How it works')}</a>
            <a className="flink" href="#field">{t('Memory field')}</a>
            <a className="flink" href="#/pretrained">{t('Pretrained models')}</a>
            <a className="flink" href="#/roundtable">{t('Roundtable')}</a>
            <a className="flink" href="#faq">{t('Questions')}</a>
          </div>
          <div className="d">
            <span className="lab">{t('Theme')}</span>
            <div className="seg" role="group" aria-label={t('Theme')}>
              {THEMES.map(([k, label]) => <button key={k} type="button" aria-pressed={theme === k} onClick={() => applyTheme(k)}>{t(label)}</button>)}
            </div>
            <span className="lab" style={{ marginTop: 8 }}>{t('Language')}</span>
            <div className="seg" role="group" aria-label={t('Language')}>
              {LANGUAGES.map(([code, name]) => <button key={code} type="button" lang={code} aria-pressed={lang === code} onClick={() => setLang(code)}>{name}</button>)}
            </div>
          </div>
        </div>
        <div className="fbottom">
          <span className="lab">© 2026 CHRONUS</span>
          <span className="lab">{t('Runs on your machine · consent first')}</span>
        </div>
      </div>
    </footer>
  )
}
