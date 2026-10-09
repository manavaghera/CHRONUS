import Icon from '../lib/Icon'
import { Reveal } from '../lib/motion'
import { Cards, CtaBand, Sec, SitePage } from './parts'

const STEPS = [
  ['Consent', 'They agree to be preserved, or, for someone who has died, their family does. The record stays with the model and can be changed later.'],
  ['Their words', 'Letters, journals, emails, photos of handwritten pages and voice notes. Each is labelled: their own words, or written about them.'],
  ['The interview', '25 questions across six parts of who they are, with follow-ups that dig into what the documents miss. Best answered in their own words.'],
  ['Their voice', 'Optional, and only with consent: a short recording becomes a private cloned voice. Removing it deletes it everywhere.'],
  ['Build', 'Their memories are indexed by meaning, an identity profile is drawn from their own sentences, and the “I don’t know” line is set for this archive.'],
  ['Talk', 'Ask anything, by typing or aloud. Every answer shows where it came from.'],
]

const LAYERS = [
  ['Memories: what they said', 'Every piece of their words, searchable by meaning. Only memories close enough to a question are ever used.'],
  ['Identity: who they are', 'What they believe, how they are, the people who matter, what they love: lines from their own sentences, each linked to its source.'],
  ['Style: how they talk', 'A small style model that learns their way of speaking from their answers, used only after it passes an exam.'],
  ['Voice: how they sound', 'Their consented voice clone reads answers aloud. Pretrained figures use a labelled stand-in voice instead.'],
]

const ANSWERS = [
  ['From their words', 'A close memory covers the question. The answer uses their own phrases and cites every source.', 'is-own'],
  ['In their spirit', 'They never talked about it, but their values do. Clearly labelled as inferred, and only if you allow it.', 'is-spirit'],
  ['I don’t know', 'Nothing in their archive is close enough. No AI is even asked, so nothing is made up.', 'is-idk'],
]

export default function HowItWorks() {
  return (
    <SitePage crumb="How it works" eyebrow="How it works" title="From their words|to a conversation."
      lede="CHRONUS learns how one person thinks, speaks and remembers from what they said and wrote, with their consent, and never makes up what they didn’t."
      actions={<><a className="btn btn-a" href="#/waitlist">Join the waitlist<Icon name="arrow" /></a><a className="btn btn-s" href="#/pretrained">Try a pretrained model</a></>}>
      <Sec id="steps" title="Six steps.|Consent comes first.">
        <ol className="steps">
          {STEPS.map(([title, text], i) => (
            <Reveal as="li" key={title} className="card step" delay={Math.min(i % 3, 2)}>
              <span className="step-n">{String(i + 1).padStart(2, '0')}</span>
              <h3 className="h3">{title}</h3>
              <p className="small">{text}</p>
            </Reveal>
          ))}
        </ol>
      </Sec>
      <Sec id="layers" title="Four layers|make one person." intro="Each layer covers what the others can’t.">
        <Cards rows={LAYERS} cols={2} />
      </Sec>
      <Sec id="answers" title="Three kinds of answer,|always labelled." intro="You always know where an answer came from.">
        <div className="answers">
          {ANSWERS.map(([title, text, cls], i) => (
            <Reveal key={title} className={`card answer ${cls}`} delay={i}>
              <h3 className="h3">{title}</h3>
              <p className="small">{text}</p>
            </Reveal>
          ))}
        </div>
      </Sec>
      <Sec id="safety" title="Built to be|gentle." tight>
        <Cards rows={[
          ['Crisis check', 'Every question is checked for crisis language first; if it is there, the model steps out of character and shows help lines.', '#/wellbeing'],
          ['Memorial mode', 'For someone who has died: gentler framing, past tense, and break reminders in long conversations.', '#/legal/memorial'],
          ['Delete means delete', 'Remove a model and its memories, files, voice, logs and feedback all go with it.', '#/trust'],
        ]} />
      </Sec>
      <CtaBand title="Start with someone|you love." text="CHRONUS opens soon. Join the waitlist and we’ll tell you when." />
    </SitePage>
  )
}
