import { useEffect, useState } from 'react'
import { useT } from '../i18n'

const items = [['home','nav.home'],['demo','nav.demo'],['models','nav.models'],['create','nav.createYourModel'],['roundtable','nav.roundtable'],['clone-voice','nav.voiceSandbox'],['insights','nav.insights'],['train','nav.howItWorks'],['ethics','nav.trust'],['roadmap','nav.roadmap'],['contact','nav.contact']]

export default function NavMenu({ open, onClose, onNav, onCta }) {
  const [time, setTime] = useState('')
  const t = useT()
  useEffect(() => {
    function tick() { const d=new Date(),h=d.getHours()%12||12; setTime(h+':'+String(d.getMinutes()).padStart(2,'0')+(d.getHours()>=12?'pm':'am')) }
    tick(); const id=setInterval(tick,1000); return ()=>clearInterval(id)
  }, [])

  return (
    <div className={`nav-overlay ${open?'open':''}`} aria-hidden={!open}>
      <div className="nav-top">
        <div className="nav-brand"><svg viewBox="0 0 48 48" fill="currentColor" width="1.25rem" height="1.25rem" style={{color:'var(--accent-from)'}}><path d="M24 2c2.2 13.8 7.9 19.6 22 22-14.1 2.4-19.8 8.2-22 22-2.2-13.8-7.9-19.6-22-22 14.1-2.4 19.8-8.2 22-22Z"/></svg>CHRONUS</div>
        <button className="nav-close" onClick={onClose}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width=".875rem" height=".875rem"><path d="M4 4l16 16M20 4 4 20"/></svg>{t('nav.close')}</button>
      </div>
      <nav className="nav-body">
        <ul className="nav-list">
          {items.map(([id,key],i) => (
            <li key={id}><button className="nav-item-btn" style={{transitionDelay:(i*45+80)+'ms'}} onClick={()=>onNav(id)}>
              <span className="nav-item-idx">{String(i+1).padStart(2,'0')}</span>
              <span className="nav-item-label">{t(key)}</span>
            </button></li>
          ))}
        </ul>
      </nav>
      <div className="nav-bottom">
        <span>{t('nav.localTime')} — {time}</span>
        <button className="nav-cta-btn" onClick={onCta}>{t('nav.getStarted')} &rarr;</button>
      </div>
    </div>
  )
}