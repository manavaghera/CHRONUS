import { useEffect, useState } from 'react'

const months = ['January','February','March','April','May','June','July','August','September','October','November','December']

export default function Header({ go, openNav }) {
  const [time, setTime] = useState('')
  const [date, setDate] = useState('')

  useEffect(() => {
    function tick() {
      const d = new Date(), h = d.getHours()%12||12, m = String(d.getMinutes()).padStart(2,'0')
      setTime(h+':'+m+(d.getHours()>=12?'pm':'am'))
      setDate(d.getDate()+' '+months[d.getMonth()]+', '+d.getFullYear())
    }
    tick(); const id = setInterval(tick, 1000); return () => clearInterval(id)
  }, [])

  return (
    <header id="header">
      <div className="header-inner">
        <button className="header-brand" onClick={() => go('home')}>
          <span className="brand-text">
            <svg viewBox="0 0 48 48" fill="currentColor" width="1.25rem" height="1.25rem" style={{color:'var(--accent)'}}><path d="M24 2c2.2 13.8 7.9 19.6 22 22-14.1 2.4-19.8 8.2-22 22-2.2-13.8-7.9-19.6-22-22 14.1-2.4 19.8-8.2 22-22Z"/></svg>
            CHRONUS
          </span>
        </button>
        <nav className="header-nav">
          {[['home','Home'],['demo','Live Demo'],['models','Models'],['create','Create'],['clone-voice','Voice Clone'],['ethics','Trust'],['faq','FAQ'],['contact','Contact']].map(([id,label]) => (
            <button key={id} onClick={() => go(id)}>
              <span className="nav-label">{label}</span>
            </button>
          ))}
        </nav>
        <div className="header-right">
          <div className="clock-chip">
            <span className="clock-label">Local time</span>
            <span className="clock-time">{time}</span>
            <span className="clock-dot">&bull;</span>
            <span className="clock-date">{date}</span>
          </div>
          <button className="menu-btn" onClick={openNav}>
            <span className="menu-label">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width=".875rem" height=".875rem"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
              <span className="menu-text">Menu</span>
            </span>
          </button>
        </div>
      </div>
    </header>
  )
}