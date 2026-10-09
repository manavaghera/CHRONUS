import Icon from '../lib/Icon'
import { Reveal } from '../lib/motion'
import { LAB } from './content'
import { CtaBand, Sec, SitePage } from './parts'

// CHRONUS Lab: a roadmap teaser. Advertising rules (UK CAP Code, EU and
// Indian consumer law) forbid implying a product that may never exist, so
// every stage says plainly whether it is real, being tested, or research.

export default function Lab() {
  return (
    <SitePage crumb="CHRONUS Lab" eyebrow="CHRONUS Lab · research" title="What comes|after words?"
      lede="Today CHRONUS keeps a person’s words, personality and voice. Here is what we’re testing next, what we’re exploring, and the brain science we’re watching, with honest labels on all of it.">
      <Sec id="roadmap">
        <div className="lab-note card" role="note">
          <Icon name="brain" size={18} />
          <p className="small"><b>Research, not a product.</b> Only “Today” is part of CHRONUS. “Next” is being tested and may change. “Exploring” and “Horizon” are research areas, not features for sale or promised; much of the science may take decades, or never be possible.</p>
        </div>
        <ol className="lab-road">
          {LAB.map(({ stage, status, items }, i) => (
            <Reveal as="li" key={stage} className={`lab-stage s${i}`} delay={Math.min(i, 3)}>
              <div className="lab-stage-h"><span className="lab-dot" aria-hidden="true" /><h2 className="h3">{stage}</h2><span className="badge">{status}</span></div>
              <div className="lab-items">
                {items.map(([title, text]) => (
                  <div key={title} className="card lab-item">
                    <h3 className="h3">{title}</h3>
                    <p className="small">{text}</p>
                  </div>
                ))}
              </div>
            </Reveal>
          ))}
        </ol>
      </Sec>
      <Sec id="why" title="Why we|watch the brain." tight>
        <div className="prose">
          <Reveal as="p">Everything a person remembers lives in the connections between their neurons. Scientists can now map those connections for a fruit fly, and grow living neurons on chips that learn simple tasks. But nobody can yet read a single memory out of a brain, and a human brain is hundreds of thousands of times larger than a fly’s.</Reveal>
          <Reveal as="p">So for now, the most faithful way to keep someone’s memories is the one CHRONUS uses: their own words, told by them, with their consent. We’ll keep following the science, and we’ll tell you honestly if that ever changes.</Reveal>
        </div>
      </Sec>
      <CtaBand title="Preserve them|the way that works today." text="Their words, their personality, their voice." href="#/how-it-works" label="See how it works" />
    </SitePage>
  )
}
