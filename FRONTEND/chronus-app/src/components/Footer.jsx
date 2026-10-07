import { navigate } from '../router'
import { useT } from '../i18n'

const REPO = 'https://github.com/manavaghera/chronus'
// [label key (strings/home.js), target]: '#section' on the home page, '#/page', or an external URL
const COLUMNS = [
  ['footer.product', [['nav.demo', '#demo'], ['nav.howItWorks', '#train'], ['common.allModels', '#/models'], ['nav.roadmap', '#roadmap']]],
  ['nav.trust', [['footer.ethics', '#ethics'], ['faq.eyebrow', '#faq'], ['footer.deleteData', '#/models'], ['nav.voiceSandbox', '#/clone-voice']]],
  ['footer.research', [['footer.code', REPO], ['footer.architecture', `${REPO}/blob/main/CHRONUS/README.md`], ['footer.evaluation', `${REPO}/blob/main/CHRONUS/evaluation/results/latest.md`], ['footer.roadmapDoc', `${REPO}/blob/main/CHRONUS/ROADMAP.md`]]],
]

export default function Footer() {
  const t = useT()
  return (
    <footer className="site-footer">
      <div className="footer-inner"><div className="shell">
        <div className="footer-cta">
          <h2 className="footer-h2">
            <span className="line-clip"><span>{t('footer.line1')}</span></span>
            <span className="line-clip"><span>{t('footer.line2')}</span></span>
          </h2>
          <button className="pill-btn pill-btn--light pill-btn--with-arrow" onClick={() => navigate('/create')}>
            <span className="pill-inner">{t('nav.getStarted')}<span className="pill-badge pill-arrow-upright"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 17 17 7M8 7h9v9"/></svg></span></span>
          </button>
        </div>
        <div className="footer-columns">
          <div className="footer-col-brand">
            <div className="brand-row"><svg viewBox="0 0 48 48" fill="currentColor" width="1.25rem" height="1.25rem"><path d="M24 2c2.2 13.8 7.9 19.6 22 22-14.1 2.4-19.8 8.2-22 22-2.2-13.8-7.9-19.6-22-22 14.1-2.4 19.8-8.2 22-22Z"/></svg>CHRONUS</div>
            <p className="tagline">{t('footer.tagline')}</p>
          </div>
          {COLUMNS.map(([title, links]) => (
            <div key={title}>
              <div className="col-title">{t(title)}</div>
              <div className="col-links">{links.map(([label, h]) => {
                const external = h.startsWith('http')
                return <a key={label} className="col-link anim-link" href={h} {...(external ? { target: '_blank', rel: 'noreferrer' } : {})}><span>{t(label)}</span></a>
              })}</div>
            </div>
          ))}
        </div>
        <div className="footer-legal">
          <span>&copy; 2024–{new Date().getFullYear()} {t('footer.copyright')}</span>
          <div className="footer-legal-links"><a className="legal-link anim-link" href="#ethics"><span>{t('footer.privacy')}</span></a><a className="legal-link anim-link" href={REPO} target="_blank" rel="noreferrer"><span>GitHub</span></a></div>
        </div>
      </div></div>
      <div className="footer-watermark">CHRONUS</div>
    </footer>
  )
}