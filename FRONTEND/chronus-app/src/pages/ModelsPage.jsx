import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { useLanguage } from '../i18n'
import { coverage, initials, relLabel } from '../lib/data'
import { Magnetic, Reveal, SplitWords, tiltHandlers } from '../lib/motion'
import { useToast } from '../lib/toast'
import useDialog from '../useDialog'
import Icon from '../lib/Icon'
import Radar from '../components/Radar'

const SAMPLE = [0.92, 0.74, 0.86, 0.66, 0.8, 0.9]

// The one thing that would help this model most right now
function nextStep(p, t) {
  const n = p.interview_answered.length
  if (p.consent?.status === 'paused') return t('Paused: resume it on its page to talk again')
  if (p.consent?.review_due) return t('Consent is due for renewal')
  if (!p.uploads.length && n < 5) return t('Next: add some of their own words')
  if (p.memories < p.min_memories) return t('Next: {n} more memories before it can be built', { n: p.min_memories - p.memories })
  if (p.status !== 'ready') return t('Next: build the model')
  if (n < 10) return t('Next: answer more interview questions ({n} of 25)', { n })
  if (!p.voice) return t('Optional: add their cloned voice')
  return t('Everything is in place')
}

function DeleteDialog({ persona, onClose, onDeleted, t }) {
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const ref = useDialog(!!persona, onClose)
  if (!persona) return null
  const ok = text.trim().toLowerCase() === persona.name.trim().toLowerCase()
  const go = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try { await api.deletePersona(persona.id); onDeleted(persona) } catch (err) { setError(err.message); setBusy(false) }
  }
  return (
    <div className="dlg center" role="alertdialog" aria-modal="true" aria-labelledby="del-h">
      <button className="dlg-bg" type="button" aria-label={t('Cancel')} tabIndex={-1} onClick={onClose} />
      <form className="card dlg-p" ref={ref} onSubmit={go}>
        <h2 id="del-h" className="h3">{t('Delete {name}?', { name: persona.name })}</h2>
        <p className="small">{t('This removes everything the model was made of, here and at Fish Audio. It can’t be undone.')}</p>
        <div className="row wrap-row gap8">{[t('Memory vectors'), t('Uploaded files'), t('Cloned voice'), t('Q&A log'), t('Feedback')].map(x => <span key={x} className="badge">{x}</span>)}</div>
        <label className="fld" htmlFor="del-in">{t('Type {name} to confirm', { name: persona.name })}
          <input id="del-in" className="field" autoComplete="off" autoFocus value={text} onChange={e => setText(e.target.value)} />
        </label>
        {error && <div className="alert" role="alert">{error}</div>}
        <div className="row gap10" style={{ justifyContent: 'flex-end' }}>
          <button className="btn btn-s btn-sm" type="button" onClick={onClose}>{t('Cancel')}</button>
          <button className="btn btn-a btn-sm" disabled={!ok || busy}>{busy ? t('Deleting…') : t('Delete forever')}</button>
        </div>
      </form>
    </div>
  )
}

function ImportCard({ onImported, t }) {
  const [file, setFile] = useState(null)
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try { onImported(await api.importModel(file, password)); setFile(null); setPassword('') } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return (
    <form className="card ymcard ymcard--import" onSubmit={submit}>
      <span className="mini-ic"><Icon name="key" size={20} /></span>
      <h3 className="h3 sm">{t('Import a backup')}</h3>
      <p className="small">{t('A password-protected .chronus file exported from any CHRONUS install.')}</p>
      <label className={`btn btn-s btn-sm file-btn${busy ? ' is-off' : ''}`}>
        {file ? file.name : t('Choose a .chronus file')}
        <input type="file" accept=".chronus" disabled={busy} onChange={e => { setFile(e.target.files[0] || null); e.target.value = '' }} />
      </label>
      {file && <input className="field" type="password" autoComplete="current-password" placeholder={t('Backup password')} aria-label={t('Backup password')} value={password} onChange={e => setPassword(e.target.value)} />}
      {error && <div className="alert" role="alert">{error}</div>}
      {file && <button className="btn btn-p btn-sm" disabled={password.length < 8 || busy}>{busy ? t('Decrypting…') : t('Import')}</button>}
    </form>
  )
}

function ModelCard({ p, onDelete, t, lang }) {
  const ready = p.status === 'ready'
  const answered = p.interview_answered.length
  const first = p.name.split(' ')[0]
  return (
    <article className="card ymcard tilt" {...tiltHandlers(6)}>
      <div className="row-sb">
        <span className="av">{initials(p.name)}</span>
        <span className="row gap8">
          {p.memorial && <span className="badge acc">{t('Memorial')}</span>}
          {p.voice && <span className="badge"><Icon name="wave" size={12} />{t('Voice')}</span>}
          <span className={`badge${ready ? ' ok' : ''}`}>{ready ? t('Ready') : t('Draft')}</span>
        </span>
      </div>
      <h3 className="serif ym-name">{p.name}</h3>
      <span className="lab">{t(relLabel(p.relationship))}{p.created_at ? ` · ${t('since {date}', { date: new Date(p.created_at).toLocaleDateString(lang, { month: 'short', year: 'numeric' }) })}` : ''}</span>
      {p.description && <p className="small ym-desc">{p.description}</p>}
      <div className="ym-stats">
        <div><b>{p.memories.toLocaleString()}</b><span className="lab">{t('Memories')}</span></div>
        <div><b>{p.uploads.length}</b><span className="lab">{t('Files')}</span></div>
        <div><b>{answered}/25</b><span className="lab">{t('Interview')}</span></div>
      </div>
      <div className="bar"><i style={{ width: `${(answered / 25) * 100}%` }} /></div>
      <p className="next-step"><Icon name="sparkle" size={14} />{nextStep(p, t)}</p>
      <div className="ym-actions">
        {ready && <a className="btn btn-a btn-sm" href={`#/chat/${p.id}`}>{t('Talk to {name}', { name: first })}</a>}
        <a className="btn btn-s btn-sm" href={`#/create/${p.id}`}>{ready ? t('Add memories') : t('Continue building')}</a>
        <span className="row gap8" style={{ marginLeft: 'auto' }}>
          <a className="icbtn" href={`#/memories/${p.id}`} aria-label={t('{name}’s memories', { name: p.name })} title={t('Memories')}><Icon name="search" size={16} /></a>
          <a className="icbtn" href={`#/insights/${p.id}`} aria-label={t('Insights for {name}', { name: p.name })} title={t('Insights')}><Icon name="chart" size={16} /></a>
          <button className="icbtn" type="button" aria-label={t('Delete {name}', { name: p.name })} title={t('Delete')} onClick={() => onDelete(p)}><Icon name="trash" size={16} /></button>
        </span>
      </div>
      <span className="glare" aria-hidden="true" />
    </article>
  )
}

export default function ModelsPage() {
  const { t, lang } = useLanguage()
  const toast = useToast()
  const [personas, setPersonas] = useState(null)
  const [error, setError] = useState('')
  const [del, setDel] = useState(null)
  const [dim, setDim] = useState(-1)

  const load = useCallback(() => {
    api.personas().then(p => { setPersonas(p); setError('') }).catch(e => { setError(e.message); setPersonas([]) })
  }, [])
  useEffect(load, [load])

  const custom = (personas || []).filter(p => p.kind === 'custom')
  const latest = custom[0]
  const values = latest ? coverage(latest.interview_answered).map(v => Math.max(v, 0.06)) : SAMPLE
  const imported = (p) => { toast(t('{name} was imported.', { name: p.name })); load() }

  return (
    <div className="page">
      <section className="page-hero">
        <div className="page-hero-bg" aria-hidden="true" />
        <div className="wrap"><div className="ph-grid">
          <div className="l">
            <nav className="crumbs" aria-label={t('Breadcrumb')}><a href="#/">{t('Home')}</a><span aria-hidden="true">/</span><span>{t('Your models')}</span></nav>
            <span className="over">{t('Private · consent first')}</span>
            <SplitWords as="h1" className="h1" text={t('Preserve the people')} em={t('who made you.')} />
            <p className="lede">{t('Build a private model of someone in your life from their letters, journals, voice notes and a guided interview. Then talk with them, in their words and, with consent, their voice.')}</p>
            <div className="row wrap-row gap12">
              <Magnetic><a className="btn btn-a" href="#/create">{t('Preserve someone')}<Icon name="arrow" /></a></Magnetic>
              <a className="btn btn-s" href="#/voice">{t('Voice studio')}</a>
            </div>
          </div>
          <Reveal className="r">
            <Radar values={values} active={dim} labels="buttons" breathe={!latest} onPick={setDim} />
            <p className="note" style={{ textAlign: 'center' }}>{latest ? t('{name}’s personality map · {n} of 25 answered', { name: latest.name, n: latest.interview_answered.length }) : t('Sample personality map · it fills in as you answer the interview')}</p>
          </Reveal>
        </div></div>
      </section>

      <section className="sec" style={{ paddingTop: 40 }} aria-labelledby="h-list">
        <div className="wrap">
          <div className="shead">
            <div className="l"><span className="over">{t('Your models')}</span><h2 className="h2" id="h-list">{custom.length ? t('The people you’ve preserved.') : t('Who will you preserve first?')}</h2></div>
            {custom.length > 0 && <a className="btn btn-p" href="#/create">{t('Preserve someone new')}</a>}
          </div>
          {error && <div className="alert" role="alert">{error} <button className="linkbtn" type="button" onClick={load}>{t('Try again')}</button></div>}
          {personas === null && <div className="ygrid">{[0, 1, 2].map(i => <div key={i} className="card ymcard is-skel" />)}</div>}
          {personas !== null && (
            custom.length ? (
              <div className="ygrid">
                {custom.map(p => <ModelCard key={p.id} p={p} onDelete={setDel} t={t} lang={lang} />)}
                <a className="card ymcard ymcard--new" href="#/create" data-cursor={t('New')}><span className="plus" aria-hidden="true"><Icon name="plus" size={28} /></span><span className="h3 sm">{t('Preserve someone new')}</span><span className="lab">{t('Starts with consent')}</span></a>
                <ImportCard onImported={imported} t={t} />
              </div>
            ) : !error && (
              <div className="empty">
                <div className="l"><span className="plus" aria-hidden="true"><Icon name="plus" size={30} /></span></div>
                <div className="r">
                  <p className="serif" style={{ fontSize: 'clamp(30px, 3.4vw, 46px)', lineHeight: 1.05 }}>{t('No one preserved yet.')}</p>
                  <p className="lede">{t('Start with a parent, a grandparent, a mentor, or yourself. It takes a few steps, and you can keep adding their words at any time.')}</p>
                  <div className="row wrap-row gap12">
                    <a className="btn btn-a" href="#/create">{t('Start with consent')}<Icon name="arrow" /></a>
                    <a className="btn btn-s" href="#/pretrained">{t('Try a pretrained model first')}</a>
                  </div>
                </div>
                <div className="imp"><ImportCard onImported={imported} t={t} /></div>
              </div>
            )
          )}
        </div>
      </section>
      <DeleteDialog persona={del} t={t} onClose={() => setDel(null)} onDeleted={(p) => { setDel(null); toast(t('{name} was deleted: memories, files, voice, log entries and feedback.', { name: p.name })); load() }} />
    </div>
  )
}
