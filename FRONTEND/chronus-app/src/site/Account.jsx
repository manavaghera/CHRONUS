import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { Backup } from '../create/StepBuild'
import Icon from '../lib/Icon'
import { useToast } from '../lib/toast'
import { navigate } from '../router'
import { Field, SitePage } from './parts'

// Sign in and the account page, on today's sign-in (services/access.py): a
// shared access code, or accounts set up by whoever runs the server (a name
// and a code each). No open sign-up, email or password reset yet: those come
// with real accounts, once hosting is decided. Until then "sign up" means
// the waitlist, and a forgotten code means writing to us.

function useAuth() {
  const [state, setState] = useState(null)
  const load = useCallback(() => api.authStatus().then(setState).catch(() => setState({ offline: true })), [])
  useEffect(() => { load() }, [load])
  return [state, load]
}

export function SignIn() {
  const [auth] = useAuth()
  const [user, setUser] = useState('')
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try { await api.login(code, auth.accounts ? user : undefined); window.location.hash = '#/account'; window.location.reload() }
    catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return (
    <SitePage crumb="Sign in" eyebrow="Private beta" title="Sign in|to your models." narrow
      lede="CHRONUS is in private beta: accounts are by invitation for now.">
      <section className="sec site-sec is-tight"><div className="wrap wrap-narrow col gap16">
        {!auth && <p className="lab">Checking…</p>}
        {auth?.offline && <div className="alert">Can’t reach the CHRONUS server right now.</div>}
        {auth && !auth.offline && !auth.required && (
          <div className="card site-form">
            <p className="small">This CHRONUS doesn’t need signing in.</p>
            <a className="btn btn-a" href="#/models">Go to your models<Icon name="arrow" /></a>
          </div>
        )}
        {auth?.required && auth.signed_in && (
          <div className="card site-form">
            <p className="small">You’re signed in{auth.user ? ` as ${auth.user}` : ''}.</p>
            <a className="btn btn-a" href="#/account">Your account<Icon name="arrow" /></a>
          </div>
        )}
        {auth?.required && !auth.signed_in && (
          <form className="card site-form" onSubmit={submit}>
            {auth.accounts && <Field id="si-user" label="Name" autoComplete="username" required value={user} onChange={e => setUser(e.target.value)} />}
            <Field id="si-code" label="Access code" type="password" autoComplete="current-password" required value={code} onChange={e => setCode(e.target.value)} />
            {error && <div className="alert" role="alert">{error}</div>}
            <button className="btn btn-a" disabled={busy || !code || (auth.accounts && !user)}>{busy ? 'Checking…' : 'Sign in'}</button>
          </form>
        )}
        <div className="card site-form">
          <a className="qlink" href="#/waitlist">New here? Join the waitlist<Icon name="arrow" size={14} /></a>
          <a className="qlink" href="#/contact/support">Forgot your code? Write to us<Icon name="arrow" size={14} /></a>
        </div>
      </div></section>
    </SitePage>
  )
}

function DeleteEverything({ models, onDone }) {
  const toast = useToast()
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  const go = async (e) => {
    e.preventDefault()
    setBusy(true)
    let gone = 0
    for (const m of models) {
      try { await api.deletePersona(m.id); gone++ } catch (err) { toast(`${m.name}: ${err.message}`) }
    }
    setBusy(false); setTyped('')
    toast(`Deleted ${gone} of ${models.length} models, with their memories, files, voices, logs and feedback.`)
    onDone()
  }
  return (
    <form className="card site-form danger-zone" onSubmit={go}>
      <h2 className="h3">Delete everything</h2>
      <p className="small">Deletes all {models.length} of your models, with every memory, file, cloned voice (here and at the voice provider), log entry and piece of feedback. It can’t be undone; download backups first if you might want them.</p>
      <Field id="del-confirm" label={'Type DELETE to confirm'} autoComplete="off" value={typed} onChange={e => setTyped(e.target.value)} />
      <button className="btn btn-d" disabled={busy || typed !== 'DELETE' || !models.length}>{busy ? 'Deleting…' : 'Delete all my models'}</button>
    </form>
  )
}

export function Account() {
  const [auth] = useAuth()
  const [models, setModels] = useState(null)
  const [error, setError] = useState('')
  const load = useCallback(() => api.personas().then(list => setModels(list.filter(p => p.kind === 'custom'))).catch(e => setError(e.message)), [])
  useEffect(() => { load() }, [load])
  const signOut = async () => { try { await api.logout() } finally { navigate('/signin'); window.location.reload() } }
  return (
    <SitePage crumb="Account" eyebrow="Your account" title="Your account|and your data." narrow
      lede="Download what you’ve made, see what you’ve agreed to, and delete it all whenever you choose.">
      <section className="sec site-sec is-tight"><div className="wrap wrap-narrow col gap16">
        <div className="card site-form">
          <div className="row-sb">
            <div className="col gap4"><span className="lab">Signed in</span><b>{auth?.user || (auth?.required ? 'With the access code' : 'No sign-in on this server')}</b></div>
            {auth?.required && auth.signed_in && <button type="button" className="btn btn-s btn-sm" onClick={signOut}>Sign out</button>}
          </div>
          <p className="note">During the private beta, accounts are set up by whoever runs this CHRONUS server; ask them to remove yours. Email, password reset and two-step sign-in come with full accounts.</p>
        </div>
        {error && <div className="alert" role="alert">{error}</div>}
        {models && (
          <div className="card site-form">
            <h2 className="h3">Your models ({models.length})</h2>
            {!models.length && <p className="small">You haven’t preserved anyone yet. <a href="#/create">Start here</a>.</p>}
            {models.map(m => (
              <div key={m.id} className="acct-model">
                <div className="row-sb"><b>{m.name}</b>
                  <span className="row gap8"><a className="linkbtn" href={`#/person/${m.id}`}>Consent and settings</a><a className="linkbtn" href={`#/memories/${m.id}`}>Memories</a></span></div>
                <Backup persona={m} />
              </div>
            ))}
          </div>
        )}
        {models?.length > 0 && <DeleteEverything models={models} onDone={load} />}
      </div></section>
    </SitePage>
  )
}
