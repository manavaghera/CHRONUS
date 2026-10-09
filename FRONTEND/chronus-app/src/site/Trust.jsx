import Icon from '../lib/Icon'
import { Reveal } from '../lib/motion'
import { PRINCIPLES, TRUST } from './content'
import { LEGAL } from './policies'
import { Cards, Sec, SitePage } from './parts'

// Trust centre, and Wellbeing and support

export function Trust() {
  return (
    <SitePage crumb="Trust centre" eyebrow="Trust centre" title="What it does,|and what it never will."
      lede="How answers are made, how consent works, what happens to your data, and how to tell us when something is wrong."
      actions={<><a className="btn btn-a" href="#/report">Report a model<Icon name="arrow" /></a><a className="btn btn-s" href="#/legal">Legal outlines</a></>}>
      <Sec id="how">
        <Cards rows={TRUST} />
      </Sec>
      <Sec id="promises" title="Our|promises." tight>
        <ul className="promises">
          {PRINCIPLES.slice(0, 4).map(([title, text]) => <Reveal as="li" key={title}><b>{title}.</b> {text}</Reveal>)}
        </ul>
        <a className="linkbtn" href="#/vision">All our principles</a>
      </Sec>
      <Sec id="policies" title="Policies|in progress." intro="These are outlines of what each policy will cover. A solicitor will write the final text before launch." tight>
        <div className="legal-list">
          {LEGAL.map(p => <a key={p.slug} className="qlink" href={`#/legal/${p.slug}`}>{p.title}<Icon name="arrow" size={14} /></a>)}
        </div>
      </Sec>
    </SitePage>
  )
}

// The same help lines the chat shows when someone is struggling (services/wellbeing.py)
const HELPLINES = [
  ['UK and Ireland', 'Samaritans', '116 123', '24/7'],
  ['India', 'Tele-MANAS', '14416 or 1-800-891-4416', '24/7'],
  ['United States', '988 Suicide & Crisis Lifeline', 'Call or text 988', '24/7'],
  ['Everywhere else', 'Find a Helpline', 'findahelpline.com', ''],
]

export function Wellbeing() {
  return (
    <SitePage crumb="Wellbeing" eyebrow="Wellbeing and support" title="If you’re struggling,|talk to a person."
      lede="A model of someone you’ve lost can bring comfort, and it can also bring grief closer. It is a keepsake, not a replacement for the people around you, or for professional help.">
      <Sec id="now" title="If you need someone|right now." tight>
        <div className="helplines-grid">
          {HELPLINES.map(([region, name, contact, hours]) => (
            <Reveal key={region} className="card site-card">
              <span className="lab">{region}</span>
              <h3 className="h3">{name}</h3>
              <p className="helpline-num">{contact}</p>
              {hours && <span className="note">{hours}</span>}
            </Reveal>
          ))}
        </div>
        <p className="note site-fine">In an emergency, call your local emergency number.</p>
      </Sec>
      <Sec id="care" title="How CHRONUS|tries to help." tight>
        <Cards rows={[
          ['A crisis check on every message', 'If a message suggests someone is in danger, the model steps out of character and shows these help lines instead of answering.'],
          ['Break reminders', 'Long conversations with a personal model get a gentle reminder to rest, or to share a memory with someone who knew them too.'],
          ['Memorial framing', 'A model of someone who has died speaks about their life in the past tense, and never claims to be alive or watching over you.'],
        ]} />
      </Sec>
    </SitePage>
  )
}
