import { useState } from 'react'
import { api } from '../api'
import { PLANS } from './content'
import { Check, Done, Field, SitePage, Trap, useSend } from './parts'

// Waitlist, contact and report-a-model forms (services/site_forms.py).
// Each says what happens to the details, right where they are asked for.

const PRIVACY = <>We keep these details only on our own server, never sell them, and delete them on request. See the <a href="#/legal/privacy">privacy outline</a>.</>

export function Waitlist({ id }) {
  const [form, setForm] = useState({ email: '', name: '', plan: PLANS.some(p => p.id === id) ? id : 'unsure', people: 1, country: '', agree: false, website: '' })
  const set = (key) => (value) => setForm(f => ({ ...f, [key]: value }))
  const { busy, error, done, submit } = useSend((values) => api.siteWaitlist(values))
  return (
    <SitePage crumb="Waitlist" eyebrow="Not on sale yet" title="Join the|waitlist."
      lede="We’ll email you once, when CHRONUS opens. Nothing else." narrow>
      <section className="sec site-sec is-tight"><div className="wrap wrap-narrow">
        {done ? (
          <Done title={done.already ? 'You’re already on the list.' : 'You’re on the list.'}>
            <p className="small">We’ll write to {form.email.trim()} when CHRONUS opens. Want to leave the list? Write to us from the <a href="#/contact">contact page</a>.</p>
          </Done>
        ) : (
          <form className="card site-form" onSubmit={e => submit(e, { ...form, people: Number(form.people) || 1 })}>
            <Field id="wl-email" label="Email" type="email" required autoComplete="email" value={form.email} onChange={e => set('email')(e.target.value)} />
            <Field id="wl-name" label="Your name (optional)" autoComplete="name" maxLength={80} value={form.name} onChange={e => set('name')(e.target.value)} />
            <div className="site-form-row">
              <Field id="wl-plan" label="Plan you’re thinking about" as="select" value={form.plan} onChange={e => set('plan')(e.target.value)}>
                {PLANS.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}<option value="unsure">Not sure yet</option>
              </Field>
              <Field id="wl-people" label="How many people?" type="number" min={1} max={50} value={form.people} onChange={e => set('people')(e.target.value)} />
            </div>
            <Field id="wl-country" label="Country (optional)" autoComplete="country-name" maxLength={60} value={form.country} onChange={e => set('country')(e.target.value)} />
            <Check id="wl-agree" checked={form.agree} onChange={set('agree')}>Email me when CHRONUS opens.</Check>
            <Trap value={form.website} onChange={set('website')} />
            <p className="note">{PRIVACY}</p>
            {error && <div className="alert" role="alert">{error}</div>}
            <button className="btn btn-a" disabled={busy || !form.agree}>{busy ? 'Joining…' : 'Join the waitlist'}</button>
          </form>
        )}
      </div></section>
    </SitePage>
  )
}

const TOPICS = [['general', 'A question'], ['partnership', 'Partnership'], ['press', 'Press'], ['support', 'Help with CHRONUS'], ['privacy', 'My data or privacy']]

export function Contact({ id }) {
  const [form, setForm] = useState({ name: '', email: '', topic: TOPICS.some(([k]) => k === id) ? id : 'general', message: '', agree: false, website: '' })
  const set = (key) => (value) => setForm(f => ({ ...f, [key]: value }))
  const { busy, error, done, submit } = useSend((values) => api.siteContact(values))
  return (
    <SitePage crumb="Contact" eyebrow="Contact" title="Write|to us."
      lede="Questions, partnerships, press, or anything about your data. A person reads every message." narrow>
      <section className="sec site-sec is-tight"><div className="wrap wrap-narrow">
        {done ? (
          <Done title="Thank you, your message is with us."><p className="small">We’ll reply to {form.email.trim()}.</p></Done>
        ) : (
          <form className="card site-form" onSubmit={e => submit(e, form)}>
            <div className="site-form-row">
              <Field id="ct-name" label="Name" required autoComplete="name" maxLength={80} value={form.name} onChange={e => set('name')(e.target.value)} />
              <Field id="ct-email" label="Email" type="email" required autoComplete="email" value={form.email} onChange={e => set('email')(e.target.value)} />
            </div>
            <Field id="ct-topic" label="About" as="select" value={form.topic} onChange={e => set('topic')(e.target.value)}>
              {TOPICS.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </Field>
            <Field id="ct-message" label="Message" as="textarea" required minLength={10} maxLength={4000} rows={6} value={form.message} onChange={e => set('message')(e.target.value)} />
            <Check id="ct-agree" checked={form.agree} onChange={set('agree')}>Use these details to reply to me.</Check>
            <Trap value={form.website} onChange={set('website')} />
            <p className="note">{PRIVACY}</p>
            {error && <div className="alert" role="alert">{error}</div>}
            <button className="btn btn-a" disabled={busy || !form.agree}>{busy ? 'Sending…' : 'Send'}</button>
          </form>
        )}
      </div></section>
    </SitePage>
  )
}

const RELATIONSHIPS = [['me', 'It’s a model of me'], ['family', 'A family member'], ['representative', 'Their representative or lawyer'], ['other', 'Someone else']]
const REASONS = [['no_consent', 'Made without their consent'], ['deceased_no_agreement', 'Someone who died, made without the family’s agreement'],
  ['impersonation', 'Used to impersonate or deceive'], ['harmful', 'Harmful or abusive content'], ['other', 'Something else']]

export function Report() {
  const [form, setForm] = useState({ name: '', email: '', model: '', relationship: 'me', reason: 'no_consent', details: '', truthful: false, website: '' })
  const set = (key) => (value) => setForm(f => ({ ...f, [key]: value }))
  const { busy, error, done, submit } = useSend((values) => api.siteReport(values))
  return (
    <SitePage crumb="Report a model" eyebrow="Trust and safety" title="Report|a model."
      lede="If a model of you, or of someone you represent, was made without consent, or is being used to deceive or harm, tell us. We review every report."
      narrow>
      <section className="sec site-sec is-tight"><div className="wrap wrap-narrow">
        {done ? (
          <Done title="Your report is with us.">
            <p className="small">Your reference is <b>{done.reference}</b>. We’ll write to {form.email.trim()} as we review it, and may pause the model while we do.</p>
          </Done>
        ) : (
          <form className="card site-form" onSubmit={e => submit(e, form)}>
            <div className="site-form-row">
              <Field id="rp-name" label="Your name" required autoComplete="name" maxLength={80} value={form.name} onChange={e => set('name')(e.target.value)} />
              <Field id="rp-email" label="Your email" type="email" required autoComplete="email" value={form.email} onChange={e => set('email')(e.target.value)} />
            </div>
            <Field id="rp-model" label="Which model?" hint="Its name, or a link to it" required minLength={2} maxLength={300} value={form.model} onChange={e => set('model')(e.target.value)} />
            <div className="site-form-row">
              <Field id="rp-rel" label="Who is it a model of?" as="select" value={form.relationship} onChange={e => set('relationship')(e.target.value)}>
                {RELATIONSHIPS.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
              </Field>
              <Field id="rp-reason" label="What’s wrong?" as="select" value={form.reason} onChange={e => set('reason')(e.target.value)}>
                {REASONS.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
              </Field>
            </div>
            <Field id="rp-details" label="Tell us more" as="textarea" required minLength={10} maxLength={4000} rows={6} value={form.details} onChange={e => set('details')(e.target.value)} />
            <Check id="rp-true" checked={form.truthful} onChange={set('truthful')}>What I’ve written is true to the best of my knowledge.</Check>
            <Trap value={form.website} onChange={set('website')} />
            <p className="note">{PRIVACY}</p>
            {error && <div className="alert" role="alert">{error}</div>}
            <button className="btn btn-a" disabled={busy || !form.truthful}>{busy ? 'Sending…' : 'Send the report'}</button>
          </form>
        )}
      </div></section>
    </SitePage>
  )
}
