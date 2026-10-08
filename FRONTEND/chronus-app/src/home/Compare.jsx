import { useRef } from 'react'
import { useT } from '../i18n'
import { Reveal, Scramble, SplitWords } from '../lib/motion'
import Icon from '../lib/Icon'

// Drag (or use the arrow keys on the slider) to wipe between the two answer modes.
// The sample's quoted words stay in English: they are presented as her own.
export default function Compare() {
  const t = useT()
  const box = useRef(null)
  const dragging = useRef(false)
  const source = t('[1] notes.txt · her own words · sample model')
  const set = (clientX) => {
    const el = box.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const v = Math.min(98, Math.max(2, ((clientX - r.left) * 100) / r.width))
    el.style.setProperty('--cmp', `${v.toFixed(2)}%`)
    const input = el.querySelector('input')
    if (input) input.value = String(Math.round(v))
  }
  return (
    <section className="sec" id="modes" aria-labelledby="h-modes">
      <div className="wrap">
        <div className="shead">
          <div className="l">
            <Scramble text={t('03 — Two ways to hear them')} />
            <SplitWords id="h-modes" className="h2" text={t('Same question.')} em={t('Drag to compare.')} />
          </div>
          <Reveal as="p" className="lede" delay={1}>{t('Quotes only gives you their exact sentences. AI voice rephrases them conversationally, cites every claim, and falls back to quotes when it can’t stay grounded.')}</Reveal>
        </div>
        <Reveal delay={2}>
          <div className="cmpbox" ref={box} data-cursor={t('Drag')}
            onPointerDown={e => { dragging.current = true; e.currentTarget.setPointerCapture?.(e.pointerId); set(e.clientX) }}
            onPointerMove={e => dragging.current && set(e.clientX)}
            onPointerUp={() => { dragging.current = false }} onPointerCancel={() => { dragging.current = false }}>
            <div className="cmp-l" aria-hidden="true">
              <div className="row-sb"><span className="lab">{t('Kamla Patel · sample')}</span><span className="badge" style={{ background: 'var(--surface)' }}>{t('AI voice')}</span></div>
              <div className="bub-q">{t('How did you teach fractions?')}</div>
              <p className="cmp-ai">{t('For thirty years I taught fractions at our village school, and mostly I used mangoes to do it.')}<span className="cite">1</span></p>
              <span className="lab">{source}</span>
              <div className="cmp-pts"><span>{t('Natural phrasing')}</span><span>{t('Every claim cited')}</span><span>{t('Quotes if ungrounded')}</span></div>
            </div>
            <div className="cmp-l cmp-a">
              <div className="row-sb"><span className="badge">{t('Quotes only')}</span><span className="lab">{t('Kamla Patel · sample')}</span></div>
              <div className="bub-q">{t('How did you teach fractions?')}</div>
              <p className="cmp-q" lang="en">“I taught fractions to the children of our village school for thirty years, mostly with mangoes.”<span className="cite">1</span></p>
              <span className="lab">{source}</span>
              <div className="cmp-pts"><span>{t('Exact sentences')}</span><span>{t('Fillers removed')}</span><span>{t('Works with no API key')}</span></div>
            </div>
            <div className="cmp-h" aria-hidden="true"><span className="cmp-knob"><Icon name="swap" size={20} /></span></div>
            <label className="sr-only" htmlFor="cmp-r">{t('Compare Quotes only (left) with AI voice (right)')}</label>
            <input className="cmp-rng" id="cmp-r" type="range" min="2" max="98" defaultValue="50"
              onInput={e => box.current?.style.setProperty('--cmp', `${e.currentTarget.value}%`)} />
          </div>
        </Reveal>
      </div>
    </section>
  )
}
