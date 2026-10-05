import { useState, useRef, useEffect } from 'react'

export default function RequestModal({ open, onClose }) {
  const [sent, setSent] = useState(false), [sending, setSending] = useState(false)
  const formRef = useRef(null)

  useEffect(() => {
    if (!open) { const t=setTimeout(()=>{ setSent(false); setSending(false); formRef.current?.reset() },300); return ()=>clearTimeout(t) }
  }, [open])

  const submit = e => { e.preventDefault(); setSending(true); setTimeout(()=>{ setSending(false); setSent(true) },800) }

  return (
    <div className={`modal-overlay ${open?'open':''}`} role="dialog" aria-modal="true" aria-hidden={!open} onClick={e=>{if(e.target===e.currentTarget)onClose()}}>
      <div className="modal-panel" onClick={e=>e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Close"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4l16 16M20 4 4 20"/></svg></button>
        {!sent ? (
          <div>
            <div className="modal-heading"><div className="eyebrow-row"><span className="eyebrow-dot"/>Start with Consent</div><h2>Tell us about your situation.</h2></div>
            <form ref={formRef} className="modal-form" onSubmit={submit}>
              <div className="form-field"><label htmlFor="f-name">Name</label><input type="text" id="f-name" placeholder="Your name" required/></div>
              <div className="form-field"><label htmlFor="f-email">Email</label><input type="email" id="f-email" placeholder="you@example.com" required/></div>
              <div className="form-field"><label htmlFor="f-msg">Your Situation</label><textarea id="f-msg" rows="4" placeholder="Tell us about the person, the memories you'd like to preserve, and whether they consented." required/></div>
              <div className="form-bottom">
                <span className="form-note">We reply within one business day.</span>
                <button type="submit" className="pill-btn pill-btn--dark pill-btn--with-arrow"><span className="pill-inner"><span>{sending?'Sending\u2026':'Send request'}</span><span className="pill-badge pill-arrow-upright"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 17 17 7M8 7h9v9"/></svg></span></span></button>
              </div>
            </form>
          </div>
        ) : (
          <div className="modal-success show">
            <div className="success-icon"><svg viewBox="0 0 48 48" fill="currentColor"><path d="M24 2c2.2 13.8 7.9 19.6 22 22-14.1 2.4-19.8 8.2-22 22-2.2-13.8-7.9-19.6-22-22 14.1-2.4 19.8-8.2 22-22Z"/></svg></div>
            <h2>Request received</h2>
            <p>Thanks for reaching out — we'll get back to you within one business day.</p>
            <button className="pill-btn pill-btn--dark" onClick={onClose}><span className="pill-inner">Close</span></button>
          </div>
        )}
      </div>
    </div>
  )
}