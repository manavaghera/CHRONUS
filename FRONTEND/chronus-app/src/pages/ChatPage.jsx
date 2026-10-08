import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { useLanguage } from '../i18n'
import Icon from '../lib/Icon'
import Conversation from '../chat/Conversation'
import SourceViewer, { matchPct, VOICES } from '../chat/SourceViewer'

// Questions stay in English, like the archives they search
const CUSTOM_QUICK = ['What was your favourite birthday?', 'What did you love about your work?', 'What are you most proud of?', 'What advice would you give me?']

function greeting(p, t) {
  if (p.kind === 'pretrained') return t('I’m {name}. Ask me anything; I answer only from my own writing, and I’ll show you where each answer comes from.', { name: p.name })
  if (p.memorial) return t('This is {name}, in their own words. Ask them anything. Every answer comes from something they said or wrote, and if they never spoke about it, it will say so.', { name: p.name })
  return t('Hi, it’s {name}. Ask me anything. I’ll answer from what I’ve actually said and written, and show you where it came from.', { name: p.name })
}

function About({ id, t, lang }) {
  const [a, setA] = useState(null)
  useEffect(() => { api.about(id).then(setA).catch(() => setA(null)) }, [id])
  if (!a) return null
  const total = Object.values(a.by_voice || {}).reduce((s, n) => s + n, 0) || 1
  return (
    <div className="card side-card">
      <span className="lab">{t('About this model')}</span>
      <div className="vmix" aria-label={t('Memories by whose words they are')}>
        {Object.entries(a.by_voice || {}).map(([k, n]) => <i key={k} className={`vm-${k}`} style={{ width: `${(n / total) * 100}%` }} title={`${t(VOICES[k] || k)}: ${n}`} />)}
      </div>
      <div className="col">
        {Object.entries(a.by_voice || {}).map(([k, n]) => <div key={k} className="prow"><span className="prov"><i className={`pm${k === 'first_person' ? '' : k === 'synthesized' ? ' dot' : ' dash'}`} />{t(VOICES[k] || k)}</span><b>{n.toLocaleString()}</b></div>)}
        {a.years && <div className="prow"><span>{t('Dated')}</span><b>{a.years.first}–{a.years.last}</b></div>}
        {a.threshold != null && <div className="prow"><span>{t('“I don’t know” threshold')}</span><b>{t('{pct}% match', { pct: matchPct(a.threshold) })}</b></div>}
        {a.consent_given_at && <div className="prow"><span>{t('Consent recorded')}</span><b>{new Date(a.consent_given_at).toLocaleDateString(lang)}</b></div>}
        {a.license && <div className="prow"><span>{t('Licence')}</span><b lang="en">{a.license.split(' (')[0]}</b></div>}
      </div>
      {a.top_sources?.length > 0 && (
        <details className="mdet"><summary>{t('Built from {n} main sources', { n: a.top_sources.length })}</summary>
          <ul className="col gap8" style={{ marginTop: 10 }}>{a.top_sources.map(s => <li key={s.source_file} className="row-sb small"><span className="ell">{s.source_file}</span><span className="lab">{s.memories}</span></li>)}</ul>
        </details>
      )}
    </div>
  )
}

export default function ChatPage({ id }) {
  const { t, lang } = useLanguage()
  const [persona, setPersona] = useState(null)
  const [error, setError] = useState('')
  const [focus, setFocus] = useState(null)
  const [viewer, setViewer] = useState(null)

  useEffect(() => { api.persona(id).then(setPersona).catch(e => setError(e.message)) }, [id])
  const onSources = useCallback((m) => setFocus(m), [])
  const onCite = useCallback((source, index) => source && setViewer({ source, index }), [])

  const notReady = persona && persona.status !== 'ready'
  const quick = !persona ? [] : persona.suggested_questions?.length ? persona.suggested_questions.slice(0, 4) : CUSTOM_QUICK
  const pre = persona?.kind === 'pretrained'

  return (
    <div className="page chat-page">
      <div className="wrap">
        <div className="chat-top">
          <nav className="crumbs" aria-label={t('Breadcrumb')}><a href="#/">{t('Home')}</a><span aria-hidden="true">/</span>
            <a href={pre ? '#/pretrained' : '#/models'}>{pre ? t('Pretrained') : t('Your models')}</a><span aria-hidden="true">/</span><span>{persona?.name || '…'}</span></nav>
          {persona && (
            <div className="row wrap-row gap8">
              <a className="btn btn-s btn-sm" href={`#/memories/${persona.id}`}><Icon name="search" size={14} />{t('Memories')}</a>
              <a className="btn btn-s btn-sm" href={`#/insights/${persona.id}`}><Icon name="chart" size={14} />{t('Insights')}</a>
              <a className="btn btn-s btn-sm" href={`#/roundtable/${persona.id}`}><Icon name="table" size={14} />{t('Roundtable')}</a>
              {persona.kind === 'custom' && <a className="btn btn-a btn-sm" href={`#/create/${persona.id}`}>{t('Add memories')}</a>}
            </div>
          )}
        </div>
        {error && <div className="alert" role="alert">{error}</div>}
        {notReady && <div className="alert">{t('{name} isn’t built yet.', { name: persona.name })} <a href={`#/create/${persona.id}`}>{t('Finish preserving them')}</a> {t('to start talking.')}</div>}
        {!persona && !error && <div className="row gap12" style={{ padding: '80px 0' }}><span className="spinner" />{t('Loading…')}</div>}
        {persona && !notReady && (
          <div className="chat-grid">
            <Conversation persona={persona} greeting={greeting(persona, t)} quick={quick} onCite={onCite} onSources={onSources} focusedId={focus?.id} />
            <aside className="chat-side" aria-label={t('Sources and model details')}>
              <div className="card side-card">
                <div className="row-sb"><span className="lab">{t('Sources')}</span>{focus?.sources?.length > 0 && <span className="lab">{t('{n} cited', { n: focus.sources.length })}</span>}</div>
                {!focus?.sources?.length && <p className="small">{t('Ask something. The memories each answer comes from appear here, with how closely they match.')}</p>}
                {focus?.sources?.map((s, i) => (
                  <div key={i} className="src">
                    <div className="row gap8"><span className="cite" style={{ margin: 0 }}>{i + 1}</span><b className="ell" lang="en">{s.citation || s.source_file}</b></div>
                    {s.quote && <p className="src-q" lang="en">“{s.quote}”</p>}
                    <div className="row wrap-row gap8">
                      {s.voice && <span className="prov"><i className={`pm${s.voice === 'first_person' ? '' : s.voice === 'synthesized' ? ' dot' : ' dash'}`} />{t(VOICES[s.voice] || s.voice)}</span>}
                      {s.distance != null && <span className="lab">{t('Match {pct}%', { pct: matchPct(s.distance) })}</span>}
                    </div>
                    {s.memory_id && <button type="button" className="linkbtn" onClick={() => setViewer({ source: s, index: i })}>{t('View in context')}<Icon name="arrow" size={13} /></button>}
                  </div>
                ))}
              </div>
              <About id={persona.id} t={t} lang={lang} />
              <p className="note">{persona.kind === 'custom'
                ? t('An AI simulation built from memories shared with consent. It is not the real person, and not a substitute for grief support or professional help.')
                : t('Built only from {titles}.', { titles: persona.sources?.map(s => s.title).join(', ') || t('its own archive') })}</p>
            </aside>
          </div>
        )}
      </div>
      {viewer && <SourceViewer personaId={persona.id} source={viewer.source} index={viewer.index} onClose={() => setViewer(null)} />}
    </div>
  )
}
