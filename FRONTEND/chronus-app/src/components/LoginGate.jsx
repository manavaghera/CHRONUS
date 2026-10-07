import { useEffect, useState } from 'react'
import { api, LOGIN_EVENT } from '../api'
import useDialog from '../useDialog'
import { useT } from '../i18n'

// Shown when the server has an access code (CHRONUS_ACCESS_CODE) and this
// browser hasn't signed in yet. The code is checked by the server, which
// sets an HttpOnly cookie; nothing is stored in the page.
export default function LoginGate() {
  const t = useT()
  const [open, setOpen] = useState(false)
  const [accounts, setAccounts] = useState(false)
  const [user, setUser] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const dialogRef = useDialog(open, () => {})

  useEffect(() => {
    api.authStatus().then(s => { setAccounts(!!s.accounts); setOpen(s.required && !s.signed_in) }).catch(() => {})
    const show = () => setOpen(true)
    window.addEventListener(LOGIN_EVENT, show)
    return () => window.removeEventListener(LOGIN_EVENT, show)
  }, [])

  if (!open) return null
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try { await api.login(code, accounts ? user : undefined); window.location.reload() } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return (
    <div className="login-gate" role="dialog" aria-modal="true" aria-labelledby="login-title">
      <form className="login-card" ref={dialogRef} onSubmit={submit}>
        <div className="eyebrow eyebrow--accent">{t('login.eyebrow')}</div>
        <h2 id="login-title">{accounts ? t('login.signIn') : t('login.enterCode')}</h2>
        <p className="page-note">{accounts ? t('login.accountsNote') : t('login.codeNote')}</p>
        {accounts && <input className="create-select" autoFocus autoComplete="username" value={user} onChange={e => setUser(e.target.value)} placeholder={t('login.name')} aria-label={t('login.name')} />}
        <input className="create-select" type="password" autoFocus={!accounts} autoComplete="current-password" value={code} onChange={e => setCode(e.target.value)} placeholder={t('login.code')} />
        {error && <div className="page-alert">{error}</div>}
        <button className="pill-btn pill-btn--dark" disabled={!code || (accounts && !user) || busy}><span className="pill-inner">{busy ? t('login.checking') : t('login.signIn')}</span></button>
      </form>
    </div>
  )
}
