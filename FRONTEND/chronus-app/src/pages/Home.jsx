import { useEffect, useState } from 'react'
import { api } from '../api'
import { tx, useT } from '../i18n'
import { useCountUp } from '../lib/motion'
import Icon from '../lib/Icon'
import Hero from '../home/Hero'
import Preserve from '../home/Preserve'
import Journey from '../home/Journey'
import Compare from '../home/Compare'
import HowItWorks from '../home/HowItWorks'
import MemoryField from '../home/MemoryField'
import Features from '../home/Features'
import Trust from '../home/Trust'
import PretrainedStrip from '../home/PretrainedStrip'
import Faq from '../home/Faq'

const KEEP = [tx('The way they tell a story'), tx('Their advice'), tx('Their sense of humour'), tx('What they believed'), tx('How they said goodnight'), tx('The stories only they knew')]

const STATS = [
  [6, tx('dimensions of personality the interview maps')],
  [25, tx('guided questions, with adaptive follow-ups')],
  [17, tx('file types it reads: documents, photos of pages and voice notes')],
  [1, tx('person who can open your model: you')],
]

function Marquee() {
  const t = useT()
  const items = [...KEEP, ...KEEP]
  return (
    <div className="mq-wrap">
      <div className="mq">
        {items.map((s, i) => (
          <div key={i} className="mq-item" aria-hidden={i >= KEEP.length}><q>{t(s)}</q><i /></div>
        ))}
      </div>
    </div>
  )
}

function Stats() {
  const t = useT()
  const [ref, k] = useCountUp()
  return (
    <section className="stats-sec" aria-label={t('CHRONUS in numbers')}>
      <div className="wrap">
        <div className="stats" ref={ref}>
          {STATS.map(([v, label]) => (
            <div key={label} className="stat"><b>{Math.round(v * k)}</b><span>{t(label)}</span></div>
          ))}
        </div>
      </div>
    </section>
  )
}

// Your own CHRONUS, live: is the server up, who have you preserved, where to pick up
function LiveStrip() {
  const t = useT()
  const [list, setList] = useState(null)
  const [offline, setOffline] = useState(false)
  useEffect(() => { api.personas().then(setList).catch(() => setOffline(true)) }, [])
  const mine = (list || []).filter(p => p.kind === 'custom')
  const memories = mine.reduce((s, p) => s + p.memories, 0)
  const latest = mine[0]
  const first = latest?.name.split(' ')[0]
  return (
    <section className="live-strip" aria-label={t('Your CHRONUS right now')}>
      <div className="wrap">
        <div className="card ls-card">
          <span className={`live${offline ? ' is-off' : ''}`}><i />{offline ? t('Server offline') : list ? t('Your CHRONUS is live') : t('Connecting')}</span>
          {offline ? <span className="small">{t('Start it with')} <code>CHRONUS/start_server.bat</code> {t('to preserve someone.')}</span> : <>
            <span className="ls-stat"><b>{mine.length}</b><span className="lab">{t('preserved')}</span></span>
            <span className="ls-stat"><b>{memories.toLocaleString()}</b><span className="lab">{t('memories')}</span></span>
            <span className="ls-stat"><b>{(list || []).filter(p => p.kind !== 'custom').length}</b><span className="lab">{t('pretrained')}</span></span>
            <a className="btn btn-s btn-sm ls-go" href={latest ? (latest.status === 'ready' ? `#/chat/${latest.id}` : `#/create/${latest.id}`) : '#/create'}>
              {latest ? (latest.status === 'ready' ? t('Talk to {name}', { name: first }) : t('Continue {name}', { name: first })) : t('Preserve your first person')}<Icon name="arrow" size={15} />
            </a>
          </>}
        </div>
      </div>
    </section>
  )
}

export default function Home() {
  return (
    <>
      <Hero />
      <Marquee />
      <LiveStrip />
      <Stats />
      <Preserve />
      <Journey />
      <Compare />
      <HowItWorks />
      <MemoryField />
      <Features />
      <Trust />
      <PretrainedStrip />
      <Faq />
    </>
  )
}
