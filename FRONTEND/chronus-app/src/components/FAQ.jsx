import { useState } from 'react'
import useScrollReveal from './useScrollReveal'

const questions = [
  { q: 'Is this meant to be the person?', a: "No. CHRONUS is a memory retrieval tool, not a resurrection. It helps you revisit what someone actually said and believed." },
  { q: "What happens if it doesn't know something?", a: "It says \"I don't know.\" CHRONUS uses a strict confidence threshold and refuses to answer rather than guess." },
  { q: 'Who approves new answers?', a: 'A trusted human reviewer — typically a family member. The system never auto-generates content.' },
  { q: 'Can I delete everything later?', a: 'Yes — immediately and unrecoverably. A single action deletes all local vectors, models, and voice samples.' },
  { q: 'Who can access these memories?', a: 'Only people explicitly authorized. Access controls live with the family, not the platform.' },
  { q: 'What if the person is still alive?', a: 'The strongest use case. They build their own archive — choosing what to include and how the system represents them.' },
]

function FaqItem({ item }) {
  const [ref, inView] = useScrollReveal()
  const [open, setOpen] = useState(false)
  return (
    <div ref={ref} className={`faq-item ${inView?'in-view':''} ${open?'open':''}`}>
      <button className="faq-q" onClick={() => setOpen(!open)}>
        <span>{item.q}</span>
        <span className="faq-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width=".875rem" height=".875rem"><path d="M12 5v14M5 12h14"/></svg></span>
      </button>
      <div className="faq-a"><div className="faq-a-inner">{item.a}</div></div>
    </div>
  )
}

export default function FAQ() {
  const [hRef, hIn] = useScrollReveal()
  return (
    <section className="faq-section" id="faq" style={{ position: 'relative', zIndex: 10 }}>
      <div className="shell faq-inner">
        <div ref={hRef} className={`sr ${hIn?'in-view':''}`}><div className="eyebrow eyebrow--dark">FAQ</div></div>
        <div className={`sr ${hIn?'in-view':''}`} style={{transitionDelay:'.1s',marginBottom:'3rem'}}>
          <h2 style={{maxWidth:'20ch',fontSize:'2.25rem',fontWeight:600,letterSpacing:'-.02em'}} className="line-clip"><span>Common questions</span></h2>
        </div>
        <div className="faq-list">{questions.map((q,i) => <FaqItem key={i} item={q}/>)}</div>
      </div>
    </section>
  )
}