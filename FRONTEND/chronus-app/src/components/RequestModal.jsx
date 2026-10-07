import { navigate } from '../router'
import useDialog from '../useDialog'
import { useT } from '../i18n'

// "Start with consent" / Contact. This used to be a form that pretended to
// send a message ("We reply within one business day") while sending
// nothing. Now it points to the things that really exist; a contact email
// appears only when one is configured (VITE_CONTACT_EMAIL at build time).
const CONTACT = import.meta.env.VITE_CONTACT_EMAIL
const REPO = 'https://github.com/manavaghera/chronus'

const OPTIONS = [
  { key: 'start.o1', to: '/create', cta: 'common.createModel' },
  { key: 'start.o2', to: '/models', cta: 'start.o2.cta' },
  { key: 'start.o3', to: '/clone-voice', cta: 'start.o3.cta' },
]

export default function RequestModal({ open, onClose }) {
  const t = useT()
  const go = (to) => { onClose(); setTimeout(() => navigate(to), 150) }
  const dialogRef = useDialog(open, onClose)
  return (
    <div className={`modal-overlay ${open ? 'open' : ''}`} role="dialog" aria-modal="true" aria-hidden={!open} aria-labelledby="start-title" onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal-panel start-panel" ref={dialogRef} tabIndex={-1} onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label={t('nav.close')}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4l16 16M20 4 4 20" /></svg></button>
        <div className="modal-heading">
          <div className="eyebrow eyebrow--accent">{t('start.eyebrow')}</div>
          <h2 id="start-title">{t('start.title')}</h2>
        </div>
        <div className="start-options">
          {OPTIONS.map(o => (
            <button key={o.to} className="start-option" onClick={() => go(o.to)} tabIndex={open ? 0 : -1}>
              <strong>{t(`${o.key}.title`)}</strong>
              <span>{t(`${o.key}.body`)}</span>
              <em>{t(o.cta)} →</em>
            </button>
          ))}
        </div>
        <p className="start-contact">
          {t('start.questions')}{' '}
          {CONTACT
            ? <a href={`mailto:${CONTACT}?subject=CHRONUS`} className="page-link">{t('start.email')}</a>
            : <a href={`${REPO}/issues`} target="_blank" rel="noreferrer" className="page-link">{t('start.issue')}</a>}
        </p>
      </div>
    </div>
  )
}
