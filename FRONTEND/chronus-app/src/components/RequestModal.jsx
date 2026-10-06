import { navigate } from '../router'
import useDialog from '../useDialog'

// "Start with consent" / Contact. This used to be a form that pretended to
// send a message ("We reply within one business day") while sending
// nothing. Now it points to the things that really exist; a contact email
// appears only when one is configured (VITE_CONTACT_EMAIL at build time).
const CONTACT = import.meta.env.VITE_CONTACT_EMAIL
const REPO = 'https://github.com/manavaghera/chronus'

const OPTIONS = [
  { title: 'Build a model of someone', body: 'Record consent, add their letters and answers, and talk to it. Everything stays on this computer by default.', to: '/create', cta: 'Create a model' },
  { title: 'Talk to a pretrained model', body: 'Elon Musk and seven historical figures, built only from public interviews and public-domain texts.', to: '/models', cta: 'Browse models' },
  { title: 'Hear a consented voice', body: 'Clone your own voice (with consent) in the sandbox, and delete it whenever you like.', to: '/clone-voice', cta: 'Open the sandbox' },
]

export default function RequestModal({ open, onClose }) {
  const go = (to) => { onClose(); setTimeout(() => navigate(to), 150) }
  const dialogRef = useDialog(open, onClose)
  return (
    <div className={`modal-overlay ${open ? 'open' : ''}`} role="dialog" aria-modal="true" aria-hidden={!open} aria-labelledby="start-title" onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal-panel start-panel" ref={dialogRef} tabIndex={-1} onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Close"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4l16 16M20 4 4 20" /></svg></button>
        <div className="modal-heading">
          <div className="eyebrow eyebrow--accent">Start with consent</div>
          <h2 id="start-title">Where would you like to begin?</h2>
        </div>
        <div className="start-options">
          {OPTIONS.map(o => (
            <button key={o.to} className="start-option" onClick={() => go(o.to)} tabIndex={open ? 0 : -1}>
              <strong>{o.title}</strong>
              <span>{o.body}</span>
              <em>{o.cta} →</em>
            </button>
          ))}
        </div>
        <p className="start-contact">
          Questions about the research?{' '}
          {CONTACT
            ? <a href={`mailto:${CONTACT}?subject=CHRONUS`} className="page-link">Email the team</a>
            : <a href={`${REPO}/issues`} target="_blank" rel="noreferrer" className="page-link">Open an issue on GitHub</a>}
        </p>
      </div>
    </div>
  )
}
