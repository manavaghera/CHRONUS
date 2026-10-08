import { useState } from 'react'
import { tx, useT } from '../i18n'
import { Magnetic, Reveal, Scramble, SplitWords } from '../lib/motion'
import Icon from '../lib/Icon'

const FAQS = [
  [tx('Is it really them?'), tx('No, and it never pretends to be. It is a model built only from what they actually said, wrote and answered. Quotes only shows their exact sentences; AI voice rewrites them, cites each source, and falls back to quotes when it can’t stay grounded.')],
  [tx('What do I need to preserve someone?'), tx('Their consent, and some of their words: letters, journals, notes, photos of handwritten pages or voice notes. The 25-question interview fills in the rest, and you can keep adding memories later.')],
  [tx('Can I preserve someone who has died?'), tx('Yes, in memorial mode, built with the family’s agreement. Answers use gentler framing, and long sessions get a break reminder.')],
  [tx('How is their voice cloned?'), tx('With consent, a recording of them speaking is sent to Fish Audio to make a private voice. Removing the voice deletes it here and at Fish Audio. Pretrained figures use a clearly labelled stand-in voice, never a clone.')],
  [tx('What happens when it doesn’t know?'), tx('It says “I don’t know.” If no memory is close enough to your question, measured against a threshold calibrated for that model, no language model is called at all.')],
  [tx('Who can see the models I build?'), tx('CHRONUS runs on your own machine and listens only on 127.0.0.1. Turn on accounts and each person sees only the models they created. Delete a model and its memories, files, cloned voice, logs and feedback all go with it.')],
]

export default function Faq() {
  const t = useT()
  const [open, setOpen] = useState(0)
  return (
    <>
      <section className="sec" id="faq" aria-labelledby="h-faq">
        <div className="wrap grid12 faq-grid">
          <Reveal className="l">
            <Scramble text={t('09 — Questions')} />
            <SplitWords id="h-faq" className="h2" text={t('Fair')} em={t('questions.')} />
            <p className="lede">{t('The short version: it only says what their words support, and it tells you where each answer came from.')}</p>
          </Reveal>
          <Reveal className="r faq" delay={1}>
            {FAQS.map(([q, a], i) => (
              <div key={q} className="fq">
                <button type="button" aria-expanded={open === i} aria-controls={`faq-${i}`} onClick={() => setOpen(open === i ? -1 : i)}>
                  <span>{t(q)}</span><span className="pl" aria-hidden="true" />
                </button>
                <div className="fa" id={`faq-${i}`} aria-hidden={open !== i}><div><p>{t(a)}</p></div></div>
              </div>
            ))}
          </Reveal>
        </div>
      </section>
      <section className="closing" aria-labelledby="h-close">
        <div className="wrap">
          <SplitWords id="h-close" as="h2" className="closing-h" text={t('Keep their words.')} em={t('Keep talking.')} />
          <Reveal className="closing-ctas" delay={2}>
            <Magnetic><a className="btn btn-a" href="#/create" data-cursor={t('Begin')}>{t('Preserve someone')}<Icon name="arrow" /></a></Magnetic>
            <a className="btn btn-s" href="#/models">{t('Your models')}</a>
          </Reveal>
        </div>
      </section>
    </>
  )
}
