import Icon from '../lib/Icon'
import { COMPANY } from './content'
import { LEGAL, LEGAL_GROUPS } from './policies'
import { SitePage } from './parts'

// Legal hub and policy pages. They are OUTLINES for a solicitor to write
// from, and say so at the top of every page.

function DraftBanner() {
  return (
    <div className="draft-banner" role="note">
      <b>Draft outline, not legal text.</b> This page lists what the policy must cover. A qualified solicitor will write
      and review the final text before CHRONUS launches. Company details in [brackets] are placeholders.
    </div>
  )
}

export default function Legal({ id }) {
  const policy = LEGAL.find(p => p.slug === id)
  if (id && !policy) return <Hub missing={id} />
  return policy ? <Policy policy={policy} /> : <Hub />
}

function Hub({ missing }) {
  return (
    <SitePage crumb="Legal" eyebrow="Legal" title="Policies,|in plain sight."
      lede="Outlines of every policy CHRONUS will publish, for the UK, the EU and India. Final texts come before launch." narrow>
      <section className="sec site-sec is-tight"><div className="wrap wrap-narrow col gap16">
        <DraftBanner />
        {missing && <div className="alert" role="alert">There’s no policy called “{missing}”. Here are all of them.</div>}
        {LEGAL_GROUPS.map(group => (
          <div key={group} className="card legal-group">
            <span className="lab">{group}</span>
            {LEGAL.filter(p => p.group === group).map(p => (
              <a key={p.slug} className="qlink" href={`#/legal/${p.slug}`}>
                <span className="col"><b>{p.title}</b><span className="note">{p.summary}</span></span><Icon name="arrow" size={14} />
              </a>
            ))}
          </div>
        ))}
        <a className="qlink" href="#/wellbeing">Wellbeing and support<Icon name="arrow" size={14} /></a>
        <a className="qlink" href="#/report">Report a model<Icon name="arrow" size={14} /></a>
      </div></section>
    </SitePage>
  )
}

function Policy({ policy }) {
  return (
    <SitePage crumb={policy.title} eyebrow="Legal · draft outline" title={`${policy.title}|`} lede={policy.summary} narrow>
      <section className="sec site-sec is-tight"><div className="wrap wrap-narrow col gap16">
        <DraftBanner />
        <div className="card legal-laws">
          <span className="lab">Laws this must meet</span>
          <ul>{policy.laws.map(law => <li key={law}>{law}</li>)}</ul>
        </div>
        <ol className="legal-sections">
          {policy.sections.map(([heading, points]) => (
            <li key={heading}>
              <h2 className="h3">{heading}</h2>
              <ul>{points.map(point => <li key={point}>{point}</li>)}</ul>
            </li>
          ))}
        </ol>
        <p className="note">Questions about this policy: {COMPANY.privacyEmail}. <a href="#/legal">All policies</a></p>
      </div></section>
    </SitePage>
  )
}
