import { useState } from 'react'
import { tx, useT } from '../i18n'
import { Magnetic, Reveal, Scramble, SplitWords } from '../lib/motion'
import Icon from '../lib/Icon'

const STEPS = [
  [tx('Consent'), tx('Their permission, recorded with the model and shown in About this model.')],
  [tx('Their words'), tx('Letters and journals (.txt .md .pdf .docx .csv .json), photos of pages, or voice notes.')],
  [tx('Interview'), tx('25 guided questions with adaptive follow-ups fill in what the documents miss.')],
  [tx('Voice and build'), tx('An optional cloned voice, then the build: it runs on your machine.')],
]
const PROVS = [
  ['pm', tx('Own words'), tx('What they said or wrote. The only text CHRONUS will ever present as their quote.')],
  ['pm dash', tx('Written by others'), tx('A biography, or a family member’s interview answer. Used, labelled, never quoted as theirs.')],
  ['pm dot', tx('Synthesized'), tx('Generated or reviewed answers, marked as such wherever they appear.')],
]

export default function Trust() {
  const t = useT()
  const [ok, setOk] = useState(false)
  return (
    <section id="consent" aria-labelledby="h-consent" className="trust-sec">
      <div className="inv">
        <div className="wrap">
          <div className="grid12 trust">
            <Reveal className="l">
              <Scramble text={t('07 — Consent first')} />
              <SplitWords id="h-consent" className="h2" text={t('A person is not a dataset.')} em={t('So nothing starts without their yes.')} />
              <p className="lede mut">{t('Upload letters, journals and voice notes, answer the interview, and CHRONUS builds a private model that only you can open. Memorial mode is there for someone who has died.')}</p>
              <div className="row wrap-row gap12">
                <label className="chk-inv"><input type="checkbox" checked={ok} onChange={e => setOk(e.target.checked)} /><span>{t('I have their consent')}</span></label>
                <Magnetic><a className="btn btn-inv" href="#/create">{t('Preserve someone')}<Icon name="arrow" /></a></Magnetic>
              </div>
            </Reveal>
            <Reveal className="r" delay={1}>
              {STEPS.map(([title, body], i) => {
                const locked = i > 0 && !ok
                return (
                  <div key={title} className={`cstep${locked ? ' is-locked' : ''}`}>
                    <span className="n">0{i + 1}</span>
                    <div><h3 className="h3 sm">{t(title)}</h3><p className="mut small-inv">{t(body)}</p></div>
                    <span className="cstate">
                      {i === 0 && !ok && <span className="need">{t('Needed')}</span>}
                      {!locked && (i > 0 || ok) && <Icon name="check" label={t('Ready')} />}
                      {locked && <Icon name="lock" label={t('Locked until consent')} />}
                    </span>
                  </div>
                )
              })}
            </Reveal>
          </div>
          <Reveal className="provs">
            {PROVS.map(([m, title, body]) => (
              <div key={title}><span className="prov inv"><i className={m} />{t(title)}</span><p className="mut small-inv">{t(body)}</p></div>
            ))}
          </Reveal>
        </div>
      </div>
    </section>
  )
}
