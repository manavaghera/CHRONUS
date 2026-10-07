import { useState } from 'react'
import useScrollReveal from './useScrollReveal'
import { useT } from '../i18n'

// faq.q1/faq.a1 to faq.q6/faq.a6 in strings/home.js
const questions = [1, 2, 3, 4, 5, 6]

function FaqItem({ item }) {
  const t = useT()
  const [ref, inView] = useScrollReveal()
  const [open, setOpen] = useState(false)
  return (
    <div ref={ref} className={`faq-item ${inView?'in-view':''} ${open?'open':''}`}>
      <button className="faq-q" onClick={() => setOpen(!open)}>
        <span>{t(`faq.q${item}`)}</span>
        <span className="faq-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width=".875rem" height=".875rem"><path d="M12 5v14M5 12h14"/></svg></span>
      </button>
      <div className="faq-a"><div className="faq-a-inner">{t(`faq.a${item}`)}</div></div>
    </div>
  )
}

export default function FAQ() {
  const t = useT()
  const [hRef, hIn] = useScrollReveal()
  return (
    <section className="faq-section" id="faq" style={{ position: 'relative', zIndex: 10 }}>
      <div className="shell faq-inner">
        <div ref={hRef} className={`sr ${hIn?'in-view':''}`}><div className="eyebrow eyebrow--dark">{t('faq.eyebrow')}</div></div>
        <div className={`sr ${hIn?'in-view':''}`} style={{transitionDelay:'.1s',marginBottom:'3rem'}}>
          <h2 style={{maxWidth:'20ch',fontSize:'2.25rem',fontWeight:600,letterSpacing:'-.02em'}} className="line-clip"><span>{t('faq.title')}</span></h2>
        </div>
        <div className="faq-list">{questions.map((q,i) => <FaqItem key={i} item={q}/>)}</div>
      </div>
    </section>
  )
}