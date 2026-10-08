import { useEffect, useRef, useState } from 'react'
import { tx, useT } from '../i18n'
import { Scramble, SplitWords, usePinnedProgress } from '../lib/motion'
import Icon from '../lib/Icon'

const STEPS = [
  { n: '01', t: tx('Consent'), b: tx('They agree to be preserved, or for memorial mode, their family does. The record stays with the model.') },
  { n: '02', t: tx('Their words'), b: tx('Upload what they wrote and recorded. Anything someone else wrote is labelled, never quoted as theirs.') },
  { n: '03', t: tx('The interview'), b: tx('25 questions across six dimensions, with follow-ups that dig into what the documents miss.') },
  { n: '04', t: tx('Their voice'), b: tx('A consented recording becomes their cloned voice. Removing it deletes it everywhere.') },
  { n: '05', t: tx('Talk'), b: tx('Ask anything. Every answer cites the memory it came from, and an empty archive says “I don’t know”.') },
]

function Visual({ i, t }) {
  if (i === 0) return (
    <div className="jv-record">
      <span className="lab">{t('Consent record')}</span>
      <span>{t('Model')} ········ <b>Kamla Patel</b></span>
      <span>{t('Relationship')} · <b>{t('Family')}</b></span>
      <span>{t('Statement')} ···· <b>{t('Recorded in English')}</b></span>
      <span>{t('Status')} ······· <b className="acc">{t('Active')}</b></span>
    </div>
  )
  if (i === 1) return (
    <div className="jv-files">
      {[['letters-to-ravi.pdf', t('Own words'), ''], ['voice-note-stories.m4a', t('Transcribed'), ''], ['memories-by-cousin.txt', t('By others'), 'dash'], ['notebook-page.jpg', t('Read from photo'), '']].map(([f, l, m], k) => (
        <div key={f} className="jv-file" style={{ '--k': k }}><Icon name={f.endsWith('m4a') ? 'wave' : 'file'} size={16} /><span>{f}</span><span className="prov"><i className={`pm ${m}`} />{l}</span></div>
      ))}
    </div>
  )
  if (i === 2) return (
    <div className="jv-q">
      <span className="lab">{t('Beliefs and values')} · Q17</span>
      <p className="serif">“{t('What principle would you never compromise on, no matter the cost?')}”</p>
      <div className="jv-type"><span>{t('Honesty with children. They always know')}</span><i /></div>
    </div>
  )
  if (i === 3) return (
    <div className="jv-voice">
      <div className="jv-bars">{Array.from({ length: 36 }, (_, k) => <i key={k} style={{ '--h': `${25 + ((k * 53) % 75)}%`, '--d': `${(k % 9) * 0.07}s` }} />)}</div>
      <span className="prov"><i className="pm" />{t('Cloned with consent · delete any time')}</span>
    </div>
  )
  return (
    <div className="jv-chat">
      <div className="bub-q">{t('What was your favourite part of teaching?')}</div>
      <p className="serif">“{t('The moment a child’s face changes, when the sum finally makes sense.')}”<span className="cite">1</span></p>
      <span className="lab">{t('Sample · cites interview answer Q14')}</span>
    </div>
  )
}

// Pinned horizontal scroll: vertical scrolling moves the five steps sideways
export default function Journey() {
  const t = useT()
  const sec = useRef(null)
  const trackRef = useRef(null)
  const [active, setActive] = useState(0)
  const [pinned, setPinned] = useState(false)

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 860px)')
    const update = () => setPinned(mq.matches && document.documentElement.classList.contains('motion'))
    update()
    mq.addEventListener?.('change', update)
    return () => mq.removeEventListener?.('change', update)
  }, [])

  usePinnedProgress(sec, '--jp', (p) => {
    const tr = trackRef.current
    if (!tr || !pinned) { if (tr) tr.style.transform = ''; return }
    const shift = Math.max(0, tr.scrollWidth - tr.parentElement.clientWidth)
    tr.style.transform = `translate3d(${(-p * shift).toFixed(1)}px, 0, 0)`
    const idx = Math.min(STEPS.length - 1, Math.floor(p * STEPS.length * 0.999))
    setActive(a => (a === idx ? a : idx))
  })

  return (
    <section className={`jny${pinned ? ' is-pinned' : ''}`} ref={sec} id="journey" aria-labelledby="h-journey">
      <div className="jny-stage">
        <div className="wrap jny-head">
          <div className="col gap16">
            <Scramble text={t('02 — From memories to a conversation')} />
            <SplitWords id="h-journey" className="h2" text={t('Five steps.')} em={t('Consent comes first.')} />
          </div>
          <div className="jny-count" aria-hidden="true"><b>0{active + 1}</b><span>/ 05</span></div>
        </div>
        <div className="jny-view">
          <ol className="jny-track" ref={trackRef}>
            {STEPS.map((s, i) => (
              <li key={s.n} className={`card jcard${i === active || !pinned ? ' is-active' : ''}`}>
                <div className="row-sb"><span className="jn">{s.n}</span><span className="lab">{t('Step {n} of 5', { n: i + 1 })}</span></div>
                <div className="jvis"><Visual i={i} t={t} /></div>
                <h3 className="h3">{t(s.t)}</h3>
                <p className="small">{t(s.b)}</p>
              </li>
            ))}
          </ol>
        </div>
        <div className="wrap"><div className="jny-bar" aria-hidden="true"><i /></div></div>
      </div>
    </section>
  )
}
