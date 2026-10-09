import { useState } from 'react'
import Icon from '../lib/Icon'
import { Reveal } from '../lib/motion'
import { DISCOUNTS, FAQ, HOSTING, PLANS, RATES, approx, discountFor, fmt, totalFor } from './content'
import { CtaBand, Sec, SitePage } from './parts'

const usd = (n) => fmt(n, 'USD')

function Calculator() {
  const [plan, setPlan] = useState('voice')
  const [people, setPeople] = useState(3)
  const chosen = PLANS.find(p => p.id === plan)
  const total = totalFor(chosen.usd, people)
  const saved = chosen.usd * people - total
  const off = discountFor(people)
  return (
    <Reveal className="card calc">
      <div className="calc-in">
        <div className="col gap16">
          <span className="lab">Plan</span>
          <div className="seg" role="group" aria-label="Plan">
            {PLANS.map(p => <button key={p.id} type="button" aria-pressed={plan === p.id} onClick={() => setPlan(p.id)}>{p.name}</button>)}
          </div>
          <span className="lab">People to preserve</span>
          <div className="stepper">
            <button type="button" className="icbtn" aria-label="One fewer person" disabled={people <= 1} onClick={() => setPeople(n => n - 1)}>−</button>
            <output aria-live="polite"><b>{people}</b> {people === 1 ? 'person' : 'people'}</output>
            <button type="button" className="icbtn" aria-label="One more person" disabled={people >= 10} onClick={() => setPeople(n => n + 1)}>+</button>
          </div>
          <p className="note">{off ? `Every person after the first is ${off}% off.` : 'Add a second person to get 15% off them.'}</p>
        </div>
        <div className="calc-out" aria-live="polite">
          <span className="lab">Total, one time</span>
          <b className="calc-total">{usd(total)}</b>
          <span className="small">{approx(total)}</span>
          {saved > 0 && <span className="badge ok">You save {usd(saved)}</span>}
          <span className="note">Then £{HOSTING.gbp * people} a year to keep {people === 1 ? 'it' : 'them'} hosted, from year two.</span>
        </div>
      </div>
    </Reveal>
  )
}

export default function Pricing() {
  return (
    <SitePage crumb="Pricing" eyebrow="Pricing · not on sale yet" title="Pay once|for each person."
      lede="No subscription for something this personal. One price per person, the first year of hosting included, and a discount when you preserve more than one."
      actions={<><a className="btn btn-a" href="#/waitlist">Join the waitlist<Icon name="arrow" /></a><a className="btn btn-s" href="#/how-it-works">How it works</a></>}>
      <Sec>
        <div className="plans">
          {PLANS.map((p, i) => (
            <Reveal key={p.id} className={`card plan${p.featured ? ' is-featured' : ''}`} delay={i}>
              <div className="row-sb"><h2 className="h3">{p.name}</h2>{p.featured && <span className="badge ok">Most chosen</span>}</div>
              <p className="small">{p.line}</p>
              <div className="plan-price"><b>{usd(p.usd)}</b><span className="note">per person, one time</span></div>
              <span className="note">≈ {approx(p.usd)}</span>
              <ul className="plan-list">{p.features.map(f => <li key={f}><Icon name="check" size={15} />{f}</li>)}</ul>
              <a className={`btn ${p.featured ? 'btn-a' : 'btn-s'}`} href={`#/waitlist/${p.id}`}>Join the waitlist</a>
            </Reveal>
          ))}
        </div>
        <p className="note site-fine">Prices in US dollars. Local amounts are approximate, at {RATES.asOf} exchange rates; your bank’s rate may differ. Taxes may apply.</p>
      </Sec>

      <Sec id="family" title="Preserving a family?|Each extra person costs less." intro="The first person is full price. Everyone after them in the same order is discounted.">
        <div className="tiers">
          {DISCOUNTS.map(([from, off], i) => {
            const last = (DISCOUNTS[i + 1]?.[0] ?? 0) - 1
            const who = last < from ? `${from} or more people` : last === from ? `${from} people` : `${from}–${last} people`
            return (
              <Reveal key={from} className="card tier" delay={i}>
                <b>{off}% off</b>
                <span className="small">{who}</span>
                <span className="note">on everyone after the first</span>
              </Reveal>
            )
          })}
        </div>
        <Calculator />
      </Sec>

      <Sec id="hosting" title="Keeping them safe,|year after year." tight>
        <div className="site-cards c3">
          <Reveal className="card site-card"><h3 className="h3">First year included</h3><p className="small">Hosting, backups and updates for the first year come with every plan.</p></Reveal>
          <Reveal className="card site-card" delay={1}><h3 className="h3">Then £{HOSTING.gbp} a year</h3><p className="small">Per person, about {usd(Math.round(HOSTING.gbp / RATES.GBP))}. We remind you before any renewal.</p></Reveal>
          <Reveal className="card site-card" delay={2}><h3 className="h3">Never held hostage</h3><p className="small">Stop paying and the model is archived, not deleted. You can always download its encrypted backup.</p></Reveal>
        </div>
      </Sec>

      <Sec id="pricing-faq" title="Questions about|pricing." tight>
        <dl className="site-qa">
          {FAQ.find(([group]) => group === 'Pricing')[1].map(([q, a]) => <div key={q}><dt>{q}</dt><dd>{a}</dd></div>)}
        </dl>
      </Sec>
      <CtaBand title="Be first|when it opens." text="CHRONUS is not on sale yet. Join the waitlist and we’ll email you once, when it is." />
    </SitePage>
  )
}
