import { navigate } from '../router'

const REPO = 'https://github.com/manavaghera/chronus'
// [label, target]: '#section' on the home page, '#/page', or an external URL
const COLUMNS = [
  ['Product', [['Live demo', '#demo'], ['How it works', '#train'], ['All models', '#/models'], ['Roadmap', '#roadmap']]],
  ['Trust', [['Ethics', '#ethics'], ['FAQ', '#faq'], ['Delete your data', '#/models'], ['Voice sandbox', '#/clone-voice']]],
  ['Research', [['Source code', REPO], ['Architecture', `${REPO}/blob/main/CHRONUS/README.md`], ['Evaluation', `${REPO}/blob/main/CHRONUS/evaluation/results/latest.md`], ['Roadmap doc', `${REPO}/blob/main/CHRONUS/ROADMAP.md`]]],
]

export default function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-inner"><div className="shell">
        <div className="footer-cta">
          <h2 className="footer-h2">
            <span className="line-clip"><span>Start the way it</span></span>
            <span className="line-clip"><span>should start.</span></span>
          </h2>
          <button className="pill-btn pill-btn--light pill-btn--with-arrow" onClick={() => navigate('/create')}>
            <span className="pill-inner">Get Started<span className="pill-badge pill-arrow-upright"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 17 17 7M8 7h9v9"/></svg></span></span>
          </button>
        </div>
        <div className="footer-columns">
          <div className="footer-col-brand">
            <div className="brand-row"><svg viewBox="0 0 48 48" fill="currentColor" width="1.25rem" height="1.25rem"><path d="M24 2c2.2 13.8 7.9 19.6 22 22-14.1 2.4-19.8 8.2-22 22-2.2-13.8-7.9-19.6-22-22 14.1-2.4 19.8-8.2 22-22Z"/></svg>CHRONUS</div>
            <p className="tagline">A consent-built memory archive. Every answer sourced. Every source named.</p>
          </div>
          {COLUMNS.map(([title, links]) => (
            <div key={title}>
              <div className="col-title">{title}</div>
              <div className="col-links">{links.map(([t, h]) => {
                const external = h.startsWith('http')
                return <a key={t} className="col-link anim-link" href={h} {...(external ? { target: '_blank', rel: 'noreferrer' } : {})}><span>{t}</span></a>
              })}</div>
            </div>
          ))}
        </div>
        <div className="footer-legal">
          <span>&copy; 2024–{new Date().getFullYear()} CHRONUS Research Project. Parul University.</span>
          <div className="footer-legal-links"><a className="legal-link anim-link" href="#ethics"><span>Privacy &amp; ethics</span></a><a className="legal-link anim-link" href={REPO} target="_blank" rel="noreferrer"><span>GitHub</span></a></div>
        </div>
      </div></div>
      <div className="footer-watermark">CHRONUS</div>
    </footer>
  )
}