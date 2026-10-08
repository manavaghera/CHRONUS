import { useEffect, useRef, useState } from 'react'
import { tx, useT } from '../i18n'
import { Reveal, Scramble, SplitWords } from '../lib/motion'
import { startField } from './fieldEngine'

const PROV = {
  own: [tx('Own words'), 'pm', tx('Can be quoted word for word when it answers the question.')],
  others: [tx('Written by others'), 'pm dash', tx('Used for context and labelled, but never shown as their quote.')],
  synth: [tx('Synthesized'), 'pm dot', tx('An answer you reviewed and approved. Marked as such wherever it appears.')],
}

export default function MemoryField() {
  const t = useT()
  const canvas = useRef(null)
  const engine = useRef(null)
  const params = useRef({ k: 3, theta: 0.16, pick: null, label: t })
  const [k, setK] = useState(3)
  const [th, setTh] = useState(16)
  const [read, setRead] = useState(null)
  const [pick, setPick] = useState(null)

  useEffect(() => {
    engine.current = startField(canvas.current, () => params.current, setRead)
    return () => engine.current?.stop()
  }, [])
  useEffect(() => {
    params.current = { k, theta: th / 100, pick: pick?.i ?? null, label: t }
    engine.current?.kick?.()
  }, [k, th, pick, t])

  const status = !read ? t('Move over the field') : read.idk ? t('Nothing inside θ') : read.hits.length === 1 ? t('1 memory inside θ') : t('{n} memories inside θ', { n: read.hits.length })
  return (
    <section className="sec" id="field" aria-labelledby="h-field">
      <div className="wrap">
        <div className="shead">
          <div className="l">
            <Scramble text={t('05 — Memory field')} />
            <SplitWords id="h-field" className="h2" text={t('Watch a question')} em={t('find their words.')} />
          </div>
          <Reveal as="p" className="lede" delay={1}>{t('Your cursor is the question. CHRONUS searches only this person’s memories, keeps the closest few inside its threshold, and answers from those. Outside the circle, it says “I don’t know.”')}</Reveal>
        </div>
        <div className="mf-grid">
          <Reveal className="mf-l">
            <div className="field-box" data-cursor={t('Ask')}>
              <canvas ref={canvas} className="field-cv" role="img" aria-label={t('A map of one person’s memories. The pointer is a question; the nearest memories inside the threshold light up.')}
                onClick={e => setPick(engine.current?.pick(e.clientX, e.clientY) || null)} />
              <div className="field-leg" aria-hidden="true"><span><i className="lg-own" />{t('Own words')}</span><span><i className="lg-oth" />{t('By others')}</span><span><i className="lg-syn" />{t('Synthesized')}</span><span><i className="lg-th" />{t('Threshold θ')}</span></div>
              <span className="lab field-note">{t('Sample archive · real embeddings have 384 dimensions')}</span>
            </div>
            <div className="fctl">
              <label className="frng" htmlFor="f-k"><span>{t('Top-k')} <b>{k}</b></span><input id="f-k" type="range" min="1" max="5" value={k} onChange={e => setK(Number(e.target.value))} /></label>
              <label className="frng" htmlFor="f-t"><span>{t('Threshold θ')} <b>{(th / 100).toFixed(2)}</b></span><input id="f-t" type="range" min="5" max="35" value={th} onChange={e => setTh(Number(e.target.value))} /></label>
            </div>
          </Reveal>
          <Reveal className="mf-r" delay={1}>
            <div className="card mf-card" aria-live="polite">
              <div className="row-sb"><span className="lab">{t('Searching')}</span><span className="lab" style={{ color: 'var(--ink)' }}>{t('One person’s archive')}</span></div>
              <p className="fstat">{status}</p>
              {read && !read.idk && (
                <>
                  <p className="small">{t('The answer is built from these memories and cites each one.')}</p>
                  <div>{read.hits.map(h => (
                    <div key={h.n} className="hit"><span className="cite">{h.n}</span><span>{t(h.label)}<i className={PROV[h.prov][1]} /></span><span className="lab">d {h.d}</span></div>
                  ))}</div>
                </>
              )}
              {read?.idk && (
                <>
                  <p className="serif" style={{ fontSize: 28 }}>“{t('I don’t know.')}”</p>
                  <p className="small">{t('The closest memory is {near} away and θ is {theta}, so nothing is cited and no language model is called.', { near: read.near, theta: (th / 100).toFixed(2) })}</p>
                </>
              )}
            </div>
            <div className="card mf-card">
              <span className="lab">{t('Selected memory')}</span>
              {pick ? (
                <>
                  <p style={{ fontWeight: 500 }}>{t(pick.label)}</p>
                  <span className="prov"><i className={PROV[pick.prov][1]} />{t(PROV[pick.prov][0])}</span>
                  <p className="small">{t(PROV[pick.prov][2])}</p>
                </>
              ) : <p className="small">{t('Click any point to see what kind of memory it is.')}</p>}
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  )
}
