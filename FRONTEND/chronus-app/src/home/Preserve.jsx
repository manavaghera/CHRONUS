import { useState } from 'react'
import { DIMENSIONS } from '../lib/data'
import { tx, useT } from '../i18n'
import { Magnetic, Reveal, Scramble, SplitWords, tiltHandlers } from '../lib/motion'
import Icon from '../lib/Icon'
import Radar from '../components/Radar'

const SAMPLE = [0.92, 0.74, 0.86, 0.66, 0.8, 0.9]

const PILLARS = [
  ['doc', tx('Their words'), tx('Letters, journals, photos of handwritten pages and voice notes become memories, each labelled by whose words it is.')],
  ['sparkle', tx('Their personality'), tx('A guided interview across six dimensions, with adaptive follow-ups, maps how they think, what they value and how they talk.')],
  ['wave', tx('Their voice'), tx('With consent, a short recording becomes their cloned voice, so every answer can be heard the way they said things.')],
]

export default function Preserve() {
  const t = useT()
  const [dim, setDim] = useState(0)
  const [fx, setFx] = useState(0)
  const d = DIMENSIONS[dim]
  const tilt = tiltHandlers(8)
  return (
    <section className="sec" id="preserve" aria-labelledby="h-preserve">
      <div className="wrap">
        <div className="shead">
          <div className="l">
            <Scramble text={t('01 — Preserve someone')} />
            <SplitWords id="h-preserve" className="h2" text={t('Their personality,')} em={t('preserved.')} />
          </div>
          <Reveal as="p" className="lede" delay={1}>{t('Not a chatbot wearing a name. A private model of one real person, built only from what they wrote, said and answered, so it sounds like them because it is them.')}</Reveal>
        </div>

        <div className="pv-grid">
          <Reveal className="pv-map">
            <Radar values={SAMPLE} active={dim} labels="buttons" breathe onPick={(i) => { setDim(i); setFx(f => 1 - f) }} />
            <div className="card pv-q" aria-live="polite">
              <div className="row-sb"><span className="lab" style={{ color: 'var(--ink)' }}>{t(d.label)}</span><span className="lab">{t('{n} of 25 questions', { n: d.ids.length })}</span></div>
              <p key={fx} className="pv-qt">“{t(d.sample)}”</p>
              <span className="lab">{t('From the guided interview · tap a dimension')}</span>
            </div>
          </Reveal>
          <div className="pv-pillars">
            {PILLARS.map(([icon, title, body], i) => (
              <Reveal key={title} delay={i + 1} className="card pillar tilt" {...tilt}>
                <span className="pillar-ic"><Icon name={icon} size={22} /></span>
                <h3 className="h3">{t(title)}</h3>
                <p className="small">{t(body)}</p>
                <span className="glare" aria-hidden="true" />
              </Reveal>
            ))}
            <Reveal delay={4} className="pv-ctas">
              <Magnetic><a className="btn btn-a" href="#/create">{t('Preserve someone')}<Icon name="arrow" /></a></Magnetic>
              <a className="btn btn-s" href="#/models">{t('Your models')}</a>
            </Reveal>
          </div>
        </div>
      </div>
    </section>
  )
}
