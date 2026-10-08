import { useEffect, useRef } from 'react'
import { useT } from '../i18n'
import { Magnetic, usePinnedProgress } from '../lib/motion'
import Icon from '../lib/Icon'
import { startVoiceField } from './voiceField'

// Pinned hero: the headline gives way, on scroll, to a sample personal
// model answering from its own words, and then saying "I don't know".
// The sample's words come from the project's own test archive (Kamla Patel)
// and stay in English: they are presented as her own words.
export default function Hero() {
  const t = useT()
  const track = useRef(null)
  const stage = useRef(null)
  const canvas = useRef(null)
  const progress = useRef(0)
  usePinnedProgress(track, '--p', (p) => { progress.current = p })
  useEffect(() => startVoiceField(canvas.current, stage.current, () => progress.current), [])

  return (
    <section className="hero-track" ref={track} aria-labelledby="hero-title">
      <div className="hs" ref={stage}>
        <canvas className="vf" ref={canvas} aria-hidden="true" />
        <div className="hero-glow" aria-hidden="true" />

        <div className="mchip c1" aria-hidden="true"><span className="fade-in d4"><Icon name="doc" size={15} />{t('Letter')}<em>1979</em></span></div>
        <div className="mchip c2" aria-hidden="true"><span className="fade-in d4"><Icon name="wave" size={15} />{t('Voice note')}<em>2:14</em></span></div>
        <div className="mchip c3" aria-hidden="true"><span className="fade-in d5"><Icon name="file" size={15} />{t('Journal')}<em>{t('12 pages')}</em></span></div>
        <div className="mchip c4" aria-hidden="true"><span className="fade-in d5"><Icon name="sparkle" size={15} />{t('Interview')}<em>Q17</em></span></div>

        <div className="hcopy">
          <span className="hpill fade-in"><span className="pulse" />{t('Personality preservation · consent first')}</span>
          <h1 className="h1 hero-h1" id="hero-title">
            <span className="ln"><span>{t('Preserve a person.')}</span></span>
            <span className="ln"><span>{t('Talk with them')}</span></span>
            <span className="ln"><span><em>{t('in their own words.')}</em></span></span>
          </h1>
          <p className="lede fade-in d2">{t('CHRONUS learns how someone thinks, speaks and remembers from their letters, journals, voice notes and a guided interview, with their consent. Then it answers as them and cites every memory it uses.')}</p>
          <div className="hero-ctas fade-in d3">
            <Magnetic><a className="btn btn-a" href="#/create" data-cursor={t('Begin')}>{t('Preserve someone')}<Icon name="arrow" /></a></Magnetic>
            <Magnetic strength={0.2}><a className="btn btn-s" href="#preserve">{t('See how it works')}</a></Magnetic>
          </div>
        </div>

        <div className="duo" aria-hidden="true">
          <div className="hchat">
            <div className="hchat-h">
              <span className="av av-sm">KP</span>
              <div className="col"><b>Kamla Patel</b><span className="lab">{t('Sample model · retired teacher')}</span></div>
              <span className="badge">{t('Their words')}</span>
            </div>
            <div className="hchat-b">
              <div className="bub-q k1">{t('How did you teach fractions?')}</div>
              <div className="col gap10">
                <span className="lab k2">{t('Her own words · notes.txt')}</span>
                <p className="hq" lang="en">
                  <span className="qline k3">“I taught fractions to the children</span>
                  <span className="qline k4">of our village school for thirty years,</span>
                  <span className="qline k5">mostly with mangoes.”<span className="cite k6">1</span></span>
                </p>
                <div className="k6r conf-row"><span className="lab">{t('Confidence · high')}</span><span className="hmeter"><i /></span><span className="lab">{t('1 source')}</span></div>
              </div>
              <div className="bub-q k8">{t('What do you think of cryptocurrency?')}</div>
              <div className="k9 col gap8">
                <p className="idk">{t('I don’t know. I never talked about that.')}</p>
                <span className="lab">{t('Nothing in her archive came close · no AI was asked')}</span>
              </div>
            </div>
          </div>
          <div className="hsrc">
            <div className="card scard">
              <div className="row-sb"><span className="lab">{t('Source')}</span><span className="cite">1</span></div>
              <p className="serif" style={{ fontSize: 24, lineHeight: 1.05 }}>notes.txt</p>
              <p className="small">{t('Typed from her notebooks and uploaded by her family, with her consent.')}</p>
              <span className="prov"><i className="pm" />{t('Own words')}</span>
            </div>
            <div className="card scard">
              <span className="lab">{t('Her voice')}</span>
              <div className="mini-wave">{Array.from({ length: 28 }, (_, i) => <i key={i} style={{ '--h': `${30 + ((i * 37) % 70)}%`, '--d': `${(i % 6) * 0.08}s` }} />)}</div>
              <p className="small">{t('Read aloud in her cloned voice, made from a consented recording.')}</p>
            </div>
          </div>
        </div>

        <p className="cap" aria-hidden="true">
          <span>{t('Every answer comes from something they really said.')}</span>
          <span className="muted">{t('When they never said it, CHRONUS won’t make it up.')}</span>
        </p>
        <div className="hmeta hm-l" aria-hidden="true">{t('6 dimensions · 25 questions · 1 person')}</div>
        <div className="hmeta hm-r" aria-hidden="true">{t('Scroll')}<span className="sline" /></div>
      </div>
    </section>
  )
}
