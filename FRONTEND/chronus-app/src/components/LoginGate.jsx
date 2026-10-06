import { useEffect, useState } from 'react'
import { api, LOGIN_EVENT } from '../api'

// Shown when the server has an access code (CHRONUS_ACCESS_CODE) and this
// browser hasn't signed in yet. The code is checked by the server, which
// sets an HttpOnly cookie; nothing is stored in the page.
export default function LoginGate() {
  const [open, setOpen] = useState(false)
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.authStatus().then(s => setOpen(s.required && !s.signed_in)).catch(() => {})
    const show = () => setOpen(true)
    window.addEventListener(LOGIN_EVENT, show)
    return () => window.removeEventListener(LOGIN_EVENT, show)
  }, [])

  if (!open) return null
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try { await api.login(code); window.location.reload() } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return (
    <div className="login-gate" role="dialog" aria-modal="true" aria-labelledby="login-title">
      <form className="login-card" onSubmit={submit}>
        <div className="eyebrow eyebrow--accent">Private server</div>
        <h2 id="login-title">Enter the access code</h2>
        <p className="page-note">This CHRONUS server is protected. Ask whoever runs it for the code.</p>
        <input className="create-select" type="password" autoFocus autoComplete="current-password" value={code} onChange={e => setCode(e.target.value)} placeholder="Access code" />
        {error && <div className="page-alert">{error}</div>}
        <button className="pill-btn pill-btn--dark" disabled={!code || busy}><span className="pill-inner">{busy ? 'Checking…' : 'Sign in'}</span></button>
      </form>
    </div>
  )
}
