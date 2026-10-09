import { useState } from 'react'
import { halves } from '../i18n'
import Icon from '../lib/Icon'
import { Reveal } from '../lib/motion'

// Shared pieces of the company website pages (English only for now).

/** Hero + body, in the same style as the app's pages */
export function SitePage({ crumb, eyebrow, title, lede, actions, children, narrow }) {
  return (
    <div className="page site">
      <section className="page-hero">
        <div className="page-hero-bg" aria-hidden="true" />
        <div className={`wrap${narrow ? ' wrap-narrow' : ''}`}>
          <nav className="crumbs" aria-label="Breadcrumb"><a href="#/">Home</a>{crumb && <><span aria-hidden="true">/</span><span>{crumb}</span></>}</nav>
          {eyebrow && <span className="over">{eyebrow}</span>}
          <h1 className="h1 h1-sm">{halves(title)}</h1>
          {lede && <p className="lede">{lede}</p>}
          {actions && <div className="row wrap-row gap12">{actions}</div>}
        </div>
      </section>
      {children}
    </div>
  )
}

/** A titled section of a site page */
export function Sec({ id, title, intro, children, tight }) {
  return (
    <section className={`sec site-sec${tight ? ' is-tight' : ''}`} id={id} aria-labelledby={id ? `${id}-h` : undefined}>
      <div className="wrap">
        {title && <Reveal className="site-sec-h"><h2 className="h2" id={id ? `${id}-h` : undefined}>{halves(title)}</h2>{intro && <p className="lede">{intro}</p>}</Reveal>}
        {children}
      </div>
    </section>
  )
}

export function CtaBand({ title, text, href = '#/waitlist', label = 'Join the waitlist' }) {
  return (
    <section className="sec site-cta">
      <div className="wrap">
        <Reveal className="card site-cta-in">
          <h2 className="h2">{halves(title)}</h2>
          {text && <p className="lede">{text}</p>}
          <a className="btn btn-a" href={href}>{label}<Icon name="arrow" /></a>
        </Reveal>
      </div>
    </section>
  )
}

/** Cards from [title, text, href?] rows */
export function Cards({ rows, cols = 3 }) {
  return (
    <div className={`site-cards c${cols}`}>
      {rows.map(([title, text, href], i) => (
        <Reveal key={title} className="card site-card" delay={Math.min(i, 3)}>
          <h3 className="h3">{title}</h3>
          <p className="small">{text}</p>
          {href && <a className="linkbtn" href={href}>Learn more</a>}
        </Reveal>
      ))}
    </div>
  )
}

/** Submit a form to *send(values)*; tracks busy, error and the result */
export function useSend(send) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(null)
  const submit = async (e, values) => {
    e.preventDefault()
    setBusy(true); setError('')
    try { setDone(await send(values)) } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return { busy, error, done, submit }
}

export function Field({ id, label, hint, as = 'input', children, ...props }) {
  const Tag = as
  return (
    <label className="fld" htmlFor={id}>{label}
      <Tag id={id} name={id} className="field" {...props}>{children}</Tag>
      {hint && <span className="note">{hint}</span>}
    </label>
  )
}

export function Check({ id, checked, onChange, children }) {
  return (
    <label className="check" htmlFor={id}><input id={id} type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} /><span>{children}</span></label>
  )
}

/** A field people never see; bots fill it in (services/site_forms.py) */
export function Trap({ value, onChange }) {
  return (
    <label className="site-trap" aria-hidden="true">Website
      <input tabIndex={-1} autoComplete="off" value={value} onChange={e => onChange(e.target.value)} />
    </label>
  )
}

export function Done({ title, children }) {
  return (
    <div className="card site-done" role="status">
      <span className="badge ok">Done</span>
      <h2 className="h3">{title}</h2>
      {children}
    </div>
  )
}
