import { useEffect, useState } from 'react'
import { api, LOGIN_EVENT } from '../api'
import { useT } from '../i18n'
import useDialog from '../useDialog'

// Shown when the server has an access code (CHRONUS_ACCESS_CODE) or accounts
// (CHRONUS_USERS) and this browser hasn't signed in. The server checks the
// code and sets an HttpOnly cookie; nothing is stored in the page.
export default function LoginGate() {
  const t = useT()
  const [open, setOpen] = useState(false)
  const [accounts, setAccounts] = useState(false)
  const [user, setUser] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const ref = useDialog(open, () => {})

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
    <div className="dlg center" role="dialog" aria-modal="true" aria-labelledby="login-title">
      <div className="dlg-bg" aria-hidden="true" />
      <form className="card dlg-p" ref={ref} onSubmit={submit}>
        <span className="over">{t('Private archive')}</span>
        <h2 id="login-title" className="h3">{accounts ? t('Sign in to your models') : t('Enter the access code')}</h2>
        <p className="small">{accounts ? t('Each person sees only the models they created.') : t('This CHRONUS server is protected. Ask whoever runs it for the code.')}</p>
        {accounts && (
          <label className="fld" htmlFor="login-user">{t('Name')}
            <input id="login-user" className="field" autoFocus autoComplete="username" value={user} onChange={e => setUser(e.target.value)} />
          </label>
        )}
        <label className="fld" htmlFor="login-code">{t('Access code')}
          <input id="login-code" className="field" type="password" autoFocus={!accounts} autoComplete="current-password" value={code} onChange={e => setCode(e.target.value)} />
        </label>
        {error && <div className="alert" role="alert">{error}</div>}
        <button className="btn btn-p" disabled={!code || (accounts && !user) || busy}>{busy ? t('Checking…') : t('Sign in')}</button>
      </form>
    </div>
  )
}
