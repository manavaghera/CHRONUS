import { useEffect, useState } from 'react'
import { api } from '../api'
import { useT } from '../i18n'
import { FIGURES, initials } from '../lib/data'
import { Reveal, Scramble, SplitWords, tiltHandlers } from '../lib/motion'
import Icon from '../lib/Icon'

// Pretrained figures are the warm-up: a way to try CHRONUS before preserving someone
export default function PretrainedStrip() {
  const t = useT()
  const [list, setList] = useState(null)
  useEffect(() => {
    api.personas().then(p => setList(p.filter(x => x.kind === 'pretrained'))).catch(() => setList([]))
  }, [])
  const tilt = tiltHandlers(8)
  return (
    <section className="sec" id="pretrained" aria-labelledby="h-pre">
      <div className="wrap">
        <div className="shead">
          <div className="l">
            <Scramble text={t('08 — Also included')} />
            <SplitWords id="h-pre" className="h2" text={t('Not ready yet?')} em={t('Try it on history first.')} />
          </div>
          <Reveal className="col gap16" delay={1}>
            <p className="lede">{t('Eight ready-made models, each built only from its own public-domain writing or public record, show what CHRONUS does with a person’s words.')}</p>
            <a className="btn btn-s" href="#/pretrained" style={{ alignSelf: 'flex-start' }}>{t('Browse pretrained models')}<Icon name="arrow" /></a>
          </Reveal>
        </div>
      </div>
      <div className="pre-rail" role="list">
        {list === null && Array.from({ length: 5 }, (_, i) => <div key={i} className="card pre-card is-skel" role="listitem" />)}
        {list?.length === 0 && <p className="small wrap">{t('Start the CHRONUS server to load the pretrained models.')}</p>}
        {list?.map((p) => {
          const f = FIGURES[p.id] || {}
          return (
            <a key={p.id} role="listitem" className="card pre-card tilt" href={p.status === 'ready' ? `#/chat/${p.id}` : '#/pretrained'} data-cursor={t('Talk')} {...tilt}>
              <span className="pre-av">{f.mono || initials(p.name)}</span>
              <span className="serif pre-name">{p.name}</span>
              <span className="lab">{f.years ? t(f.years) : ''}{f.field ? ` · ${t(f.field)}` : ''}</span>
              <span className="small pre-desc" lang="en">{p.description}</span>
              <span className="pre-go">{t('Talk')}<Icon name="arrow" size={16} /></span>
              <span className="glare" aria-hidden="true" />
            </a>
          )
        })}
      </div>
    </section>
  )
}
