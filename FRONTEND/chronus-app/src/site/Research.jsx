import { useState } from 'react'
import Icon from '../lib/Icon'
import { Reveal } from '../lib/motion'
import { FAQ } from './content'
import { Cards, CtaBand, Sec, SitePage } from './parts'

// Research (the paper behind CHRONUS) and the FAQ page

const IDEAS = [
  ['Retrieval, not imitation', 'Answers are built from the person’s own memories, found by meaning (Sentence-BERT embeddings in a per-person ChromaDB collection), never from what a general AI imagines about them.'],
  ['A calibrated “I don’t know”', 'Each archive gets its own distance threshold, set just below where questions it can’t answer start to match. Below it, no language model is called at all.'],
  ['Whose words is it?', 'Every memory is labelled as their own words, written about them, or synthesized. Only their own words are ever quoted as theirs, and answers are scored for how grounded they are.'],
  ['A structured interview', '25 questions across six dimensions of personality, with adaptive follow-ups, fill in what documents miss.'],
  ['Mix Method', 'A verbatim mode that answers in the person’s exact sentences, with no AI rewriting, as a faithful baseline and fallback.'],
  ['Style models with an exam', 'Per-person LoRA adapters trained only on their own answers, put in use only if they beat the plain model on held-out questions.'],
]

export function Research() {
  return (
    <SitePage crumb="Research" eyebrow="Research" title="The research|behind CHRONUS."
      lede="CHRONUS started as a research project on preserving a person’s personality from their own words. These are the ideas it rests on."
      actions={<span className="badge">Paper: [link once published]</span>}>
      <Sec id="ideas" title="Six|ideas.">
        <Cards rows={IDEAS} />
      </Sec>
      <Sec id="evaluation" title="How we|test it." tight>
        <div className="prose">
          <Reveal as="p">We hold back real interview answers the model never saw, ask it the same questions, and measure how close its answers come to what the person actually said, alongside how often an answer is grounded in their words. New style models must pass this same kind of exam before they are used.</Reveal>
          <Reveal as="p">Results, methods and limitations are in the paper. [Add citation and link once published.]</Reveal>
        </div>
      </Sec>
      <CtaBand title="Where the research|goes next." text="Style models, life chapters, and the brain science we watch." href="#/lab" label="Visit CHRONUS Lab" />
    </SitePage>
  )
}

export function FaqPage() {
  const [open, setOpen] = useState('')
  return (
    <SitePage crumb="FAQ" eyebrow="Questions" title="Fair|questions."
      lede="The short version: it only says what their words support, and it tells you where each answer came from."
      actions={<a className="btn btn-s" href="#/contact">Ask us something else<Icon name="arrow" /></a>}>
      {FAQ.map(([group, items]) => (
        <Sec key={group} id={`faq-${group.toLowerCase().replace(/\W+/g, '-')}`} title={`${group}|`} tight>
          <div className="faq">
            {items.map(([q, a]) => {
              const key = `${group}:${q}`
              const id = `fa-${key.replace(/\W+/g, '-')}`
              return (
                <div key={q} className="fq">
                  <button type="button" aria-expanded={open === key} aria-controls={id} onClick={() => setOpen(open === key ? '' : key)}>
                    <span>{q}</span><span className="pl" aria-hidden="true" />
                  </button>
                  <div className="fa" id={id} aria-hidden={open !== key}><div><p>{a}</p></div></div>
                </div>
              )
            })}
          </div>
        </Sec>
      ))}
      <CtaBand title="Still|wondering?" text="Write to us; a person reads every message." href="#/contact" label="Contact us" />
    </SitePage>
  )
}
