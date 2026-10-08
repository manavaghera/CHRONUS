import { useRef, useState } from 'react'
import { tx, useT } from '../i18n'
import { Reveal, Scramble, SplitWords, tiltHandlers } from '../lib/motion'
import Icon from '../lib/Icon'

const LANGS = [
  ['en', 'English', 'What did you love about teaching?'],
  ['hi', 'हिंदी', 'आपको पढ़ाने में क्या अच्छा लगता था?'],
  ['gu', 'ગુજરાતી', 'તમને ભણાવવામાં શું ગમતું હતું?'],
]
const ERAS = [[tx('Childhood stories'), tx('Voice notes'), 1952], [tx('Letters to Ravi'), tx('Letters'), 1979], [tx('School diaries'), tx('Journals'), 1994], [tx('The interview'), tx('Interview'), 2026]]
const GONE = [tx('Memory vectors'), tx('Uploaded files'), tx('Cloned voice at Fish Audio'), tx('Q&A log entries'), tx('Feedback')]
const MINI = [
  ['search', tx('Memory browser'), tx('Search what a model knows. Edit, hide from quotes or delete any memory.'), '#/models'],
  ['chart', tx('Knowledge gaps'), tx('See what people asked that the archive couldn’t answer, with the interview question that would fill it.'), '#/insights'],
  ['shield', tx('Encrypted backup'), tx('Export a model as a password-protected .chronus file and import it on any install.'), '#/models'],
  ['buoy', tx('Wellbeing'), tx('Crisis language brings up helplines. Long sessions with a personal model get a gentle break reminder.'), ''],
]
const BARS = Array.from({ length: 44 }, (_, i) => ({ h: 26 + Math.round(70 * Math.abs(Math.sin(i * 1.7) * Math.cos(i * 0.45))), d: ((i % 7) * 0.09).toFixed(2) }))

// The spotlight follows the pointer inside each tile
const spot = (e) => {
  const el = e.currentTarget, r = el.getBoundingClientRect()
  el.style.setProperty('--sx', `${(((e.clientX - r.left) * 100) / r.width).toFixed(1)}%`)
  el.style.setProperty('--sy', `${(((e.clientY - r.top) * 100) / r.height).toFixed(1)}%`)
}

export default function Features() {
  const t = useT()
  const [voice, setVoice] = useState(false)
  const [lang, setLang] = useState(1)
  const [from, setFrom] = useState(1960)
  const [to, setTo] = useState(2000)
  const [gone, setGone] = useState(0)
  const timer = useRef(0)
  const runDelete = () => {
    if (gone >= GONE.length) { setGone(0); return }
    if (timer.current) return
    let g = 0
    timer.current = setInterval(() => { g += 1; setGone(g); if (g >= GONE.length) { clearInterval(timer.current); timer.current = 0 } }, 340)
  }
  const pos = (y) => ((y - 1945) * 100) / 85
  const tilt = tiltHandlers(5)

  return (
    <section className="sec" id="features" aria-labelledby="h-features">
      <div className="wrap">
        <div className="shead">
          <div className="l">
            <Scramble text={t('06 — Around the conversation')} />
            <SplitWords id="h-features" className="h2" text={t('Everything it takes to')} em={t('keep them close.')} />
          </div>
          <Reveal as="p" className="lede" delay={1}>{t('All of this is part of CHRONUS today. The controls here work.')}</Reveal>
        </div>
        <div className="bento">
          <Reveal className="tile s7" onPointerMove={spot}>
            <div className="row-sb"><span className="lab">{t('Their cloned voice')}</span><span className="lab" style={{ color: 'var(--ink)' }}>{voice ? t('Listening') : t('Off')}</span></div>
            <h3 className="h3">{t('Ask aloud. Hear them answer.')}</h3>
            <p className="small">{t('With consent, a short recording becomes their cloned voice. Turn on hands-free and simply talk: CHRONUS listens, answers from their words and reads it in their voice.')}</p>
            <div className={`vbars${voice ? ' is-on' : ''}`} aria-hidden="true">{BARS.map((b, i) => <i key={i} style={{ height: `${b.h}%`, animationDelay: `${b.d}s` }} />)}</div>
            <div className="row-sb wrap-row">
              <button className="switch inline" type="button" role="switch" aria-checked={voice} onClick={() => setVoice(v => !v)}><span className="tr" /><span className="t1">{t('Hands-free conversation')}</span></button>
              <a className="btn btn-s btn-sm" href="#/voice">{t('Open the voice studio')}<Icon name="arrow" size={16} /></a>
            </div>
          </Reveal>
          <Reveal className="tile s5" delay={1} onPointerMove={spot}>
            <div className="row-sb"><span className="lab">{t('Time travel')}</span><span className="lab" style={{ color: 'var(--ink)' }}>{from}–{to}</span></div>
            <h3 className="h3">{t('Talk to them at 30, or at 70.')}</h3>
            <p className="small">{t('Limit answers to memories dated within the years you choose.')}</p>
            <div className="tl" aria-hidden="true">
              <div className="tl-base" />
              <div className="tl-rng" style={{ left: `${pos(from)}%`, width: `${pos(to) - pos(from)}%` }} />
              {ERAS.map(([, , y]) => <i key={y} className={`tl-dot${y >= from && y <= to ? ' is-on' : ''}`} style={{ left: `${pos(y)}%` }} />)}
            </div>
            <div className="rng">
              <label htmlFor="tt-f"><span>{t('From')} <b>{from}</b></span><input id="tt-f" type="range" min="1945" max="2030" value={from} onChange={e => setFrom(Math.min(Number(e.target.value), to))} /></label>
              <label htmlFor="tt-t"><span>{t('To')} <b>{to}</b></span><input id="tt-t" type="range" min="1945" max="2030" value={to} onChange={e => setTo(Math.max(Number(e.target.value), from))} /></label>
            </div>
            <div>{ERAS.map(([title, kind, y]) => (
              <div key={title} className={`wk${y >= from && y <= to ? ' is-on' : ''}`}><span>{t(title)}<span className="lab" style={{ marginLeft: 8 }}>{t(kind)} · {y}</span></span><span className="st">{y >= from && y <= to ? t('In range') : t('Left out')}</span></div>
            ))}</div>
            <span className="note">{t('Sample archive')}</span>
          </Reveal>
          <Reveal className="tile s4" onPointerMove={spot}>
            <span className="lab">{t('Languages')}</span>
            <h3 className="h3">{t('Ask in Hindi, Gujarati and more.')}</h3>
            <div className="seg" role="group" aria-label={t('Question language')}>
              {LANGS.map(([code, label], i) => <button key={code} type="button" lang={code} aria-pressed={lang === i} onClick={() => setLang(i)}>{label}</button>)}
            </div>
            <p className="lq" lang={LANGS[lang][0]}>{LANGS[lang][2]}</p>
            <p className="note">{t('Translated in and out, with the original shown. Needs the AI voice.')}</p>
          </Reveal>
          <Reveal className="tile s4 tilt" delay={1} {...tilt}>
            <span className="lab">{t('Memorial mode')}</span>
            <h3 className="h3">{t('For someone who has died.')}</h3>
            <p className="small">{t('Built with the family’s agreement, with gentler framing and break reminders for long conversations.')}</p>
            <div className="candle" aria-hidden="true"><i /></div>
            <span className="glare" aria-hidden="true" />
          </Reveal>
          <Reveal className="tile s4" delay={2} onPointerMove={spot}>
            <div className="row-sb"><span className="lab">{t('Delete means delete')}</span><span className="lab" style={{ color: 'var(--ink)' }}>{gone >= GONE.length ? t('Nothing left') : gone ? t('Removing') : t('Five places')}</span></div>
            <h3 className="h3">{t('Remove a model, remove all of it.')}</h3>
            <div>{GONE.map((g, i) => <div key={g} className={`dl${gone > i ? ' is-gone' : ''}`}><i className="x" />{t(g)}</div>)}</div>
            <button className="btn btn-s btn-sm" type="button" disabled={gone > 0 && gone < GONE.length} onClick={runDelete}>{gone >= GONE.length ? t('Restore the demo') : gone ? t('Deleting…') : t('Try it on a sample')}</button>
          </Reveal>
          {MINI.map(([ic, title, body, href], i) => (
            <Reveal key={title} className="tile s3 mini" delay={i} onPointerMove={spot}>
              <span className="mini-ic"><Icon name={ic} size={20} /></span>
              <h3 className="h3 sm">{t(title)}</h3>
              <p className="small">{t(body)}</p>
              {href && <a className="linkbtn" href={href}>{t('Open')}<Icon name="arrow" size={13} /></a>}
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  )
}
