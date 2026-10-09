import Icon from '../lib/Icon'
import { Reveal } from '../lib/motion'
import { FOUNDER, PARTNERS, PRINCIPLES } from './content'
import { Cards, CtaBand, Sec, SitePage } from './parts'

// About us, Vision (principles) and For partners

export function About() {
  return (
    <SitePage crumb="About us" eyebrow="About us" title="Some voices|are worth keeping."
      lede="CHRONUS began with a simple worry: when someone we love is gone, so are the stories only they could tell, and the way they told them.">
      <Sec id="story" title="Why we|built it.">
        <div className="prose">
          <Reveal as="p">Photo albums keep faces. Recordings keep a few moments. But the way a grandmother explains fractions with mangoes, or how a father ends every phone call, usually disappears with them.</Reveal>
          <Reveal as="p">We wanted something that keeps a person’s own words and lets you talk with them, without pretending to be them, and without ever making up what they didn’t say. So every answer in CHRONUS comes from something they really said, shows where it came from, and says “I don’t know” when their words don’t cover a question.</Reveal>
          <Reveal as="p">It started as a research project on preserving personality from a person’s own words, and grew into the CHRONUS you see now.</Reveal>
        </div>
      </Sec>
      <Sec id="team" title="The|team." tight>
        <Reveal className="card founder">
          <span className="av av-lg" aria-hidden="true">{FOUNDER.name.split(' ').map(w => w[0]).join('')}</span>
          <div className="col gap8">
            <h3 className="h3">{FOUNDER.name}</h3>
            <span className="lab">{FOUNDER.role}</span>
            <p className="small">{FOUNDER.bio}</p>
            <div className="row wrap-row gap8">
              {FOUNDER.links.map(([label, href]) => <a key={label} className="btn btn-s btn-sm" href={href} target="_blank" rel="noopener noreferrer">{label}<Icon name="out" size={14} /></a>)}
            </div>
          </div>
        </Reveal>
      </Sec>
      <CtaBand title="Our principles|come first." text="Consent, honesty, and deletion that really deletes." href="#/vision" label="Read our principles" />
    </SitePage>
  )
}

export function Vision() {
  return (
    <SitePage crumb="Vision" eyebrow="Vision and principles" title="Keep their words.|Never invent them."
      lede="A model of a person carries a responsibility that ordinary software doesn’t. These are the rules CHRONUS is built on, and the ones we hold ourselves to.">
      <Sec id="principles">
        <ol className="principles">
          {PRINCIPLES.map(([title, text], i) => (
            <Reveal as="li" key={title} className="principle" delay={Math.min(i % 3, 2)}>
              <span className="step-n">{String(i + 1).padStart(2, '0')}</span>
              <div><h2 className="h3">{title}</h2><p className="small">{text}</p></div>
            </Reveal>
          ))}
        </ol>
      </Sec>
      <Sec id="where" title="Where we’re|going." tight>
        <div className="prose">
          <Reveal as="p">Today CHRONUS keeps a person’s words, personality and voice. Next come life chapters and style models that learn how someone talks. Further out, we follow the science of memory closely, and say plainly what is only research.</Reveal>
        </div>
        <div className="row wrap-row gap12" style={{ marginTop: 20 }}>
          <a className="btn btn-s" href="#/lab">Visit CHRONUS Lab<Icon name="arrow" /></a>
          <a className="btn btn-s" href="#/trust">Trust centre</a>
        </div>
      </Sec>
    </SitePage>
  )
}

export function Partners() {
  return (
    <SitePage crumb="For partners" eyebrow="For partners" title="Helping families|keep their stories."
      lede="We’d like to work with the people who already care for families at the most important moments."
      actions={<a className="btn btn-a" href="#/contact/partnership">Talk to us about a partnership<Icon name="arrow" /></a>}>
      <Sec id="who" title="Who we|work with.">
        <Cards rows={PARTNERS} cols={2} />
      </Sec>
      <Sec id="how" title="What a partnership|looks like." tight>
        <Cards rows={[
          ['Guided sessions', 'Our interviewers, or your trained staff, help people record their stories with consent.'],
          ['Family pricing', 'Partner discounts for the families you support.'],
          ['Care built in', 'Memorial mode, break reminders and help lines, designed with grief in mind.'],
        ]} />
      </Sec>
    </SitePage>
  )
}
