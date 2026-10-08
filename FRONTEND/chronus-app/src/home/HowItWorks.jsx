import { useState } from 'react'
import { tx, useT } from '../i18n'
import { Reveal, Scramble, SplitWords } from '../lib/motion'

const STEPS = [
  { t: tx('Crisis check'), b: tx('Every question is checked for crisis language first. If it is there, the model steps out of character and shows helplines.'), h: [tx('Runs on every message'), tx('Breaks character on purpose')] },
  { t: tx('Translate'), b: tx('Asked in Hindi, Gujarati or another language? It is translated to English, answered, and translated back, with the English original shown.'), h: [tx('Untranslated sources stay visible'), tx('Needs the AI voice')] },
  { t: tx('Profile facts'), b: tx('Simple facts like “When were you born?” are answered from a checked profile, without searching the archive.'), h: [tx('Hand-checked corrections'), tx('No retrieval needed')] },
  { t: tx('Retrieve'), b: tx('Sentence-BERT embeddings search this person’s own ChromaDB collection. Nothing close enough means “I don’t know”, and no language model is called.'), h: [tx('Threshold calibrated per model'), tx('Near-duplicates dropped'), tx('Optional hybrid BM25 + rerank'), tx('Optional year range')] },
  { t: tx('Answer'), b: tx('Quotes only returns the one to three sentences of each memory that answer you. AI voice rewrites their words with [n] citations, and falls back to quotes if it is not grounded.'), h: [tx('Short, normal or detailed'), tx('Streamed as it is written')] },
  { t: tx('Show its work'), b: tx('Every answer arrives with its sources, a confidence level and the reason for it, and a grounding score.'), h: [tx('View in context for every source'), tx('Logged for Insights')] },
]

export default function HowItWorks() {
  const t = useT()
  const [step, setStep] = useState(3)
  const s = STEPS[step]
  return (
    <section className="sec how" id="how" aria-labelledby="h-how">
      <div className="wrap">
        <div className="shead">
          <div className="l">
            <Scramble text={t('04 — How an answer is made')} />
            <SplitWords id="h-how" className="h2" text={t('Six checks between your question and')} em={t('their answer.')} />
          </div>
          <Reveal as="p" className="lede" delay={1}>{t('Each step keeps it honest: grounded in their archive, labelled by whose words it is, and quiet when it should be.')}</Reveal>
        </div>
        <Reveal delay={2}>
          <div className="steps" role="group" aria-label={t('Pipeline steps')}>
            {STEPS.map((x, i) => (
              <button key={x.t} type="button" className="stp" aria-pressed={i === step} aria-controls="step-panel" onClick={() => setStep(i)}>
                <span className="n">0{i + 1}</span><span className="t">{t(x.t)}</span>
              </button>
            ))}
          </div>
          <div className="track" aria-hidden="true"><i style={{ width: `${(step * 100) / 6}%` }} /><b style={{ left: `${(step * 100) / 6}%` }} /></div>
          <div className="spanel" id="step-panel" aria-live="polite" key={step}>
            <div className="l">
              <span className="bignum" aria-hidden="true">0{step + 1}</span>
              <div className="col gap14"><h3 className="h3 big">{t(s.t)}</h3><p className="lede">{t(s.b)}</p></div>
            </div>
            <div className="r">
              <span className="lab" style={{ paddingBottom: 8 }}>{t('Under the hood')}</span>
              {s.h.map(h => <div key={h} className="hood">{t(h)}</div>)}
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
