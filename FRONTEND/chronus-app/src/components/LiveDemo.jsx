import ChatPanel from './ChatPanel'
import { navigate } from '../router'
import { useT } from '../i18n'

export const ELON = { id: 'elon_musk', name: 'Elon Musk', standInVoice: true }
// Questions stay in English, like the archive they search
export const ELON_QUICK = ['Why Mars?', 'Why did you buy Twitter?', 'How do you handle failure?', 'Is AI dangerous?', 'Tell me about your childhood']
// Whose words each source is: "his words", "about him" (strings/chat.js elonVoices.*)
export const ELON_VOICES = 'elonVoices'

const ARROW = <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 17 17 7M8 7h9v9"/></svg>

export default function LiveDemo() {
  const t = useT()
  return (
    <section className="demo-section" id="demo" style={{ position: 'relative', zIndex: 10 }}>
      <div className="shell demo-inner">
        <div className="sr in-view" style={{ marginBottom: '1rem' }}><div className="eyebrow eyebrow--accent">{t('nav.demo')}</div></div>
        <div className="demo-wrapper">
          <div className="demo-text-col sr in-view">
            <h2>{t('demo.title')}</h2>
            <p className="demo-desc">{t('demo.desc')}</p>
            <div className="demo-model-select"><span/>chronus-model:{ELON.id}</div>
            <div className="demo-cta-row">
              <button className="pill-btn pill-btn--accent pill-btn--with-arrow" onClick={() => navigate('/create')}>
                <span className="pill-inner">{t('common.createOwn')}<span className="pill-badge pill-arrow-upright">{ARROW}</span></span>
              </button>
              <button className="pill-btn pill-btn--outline" onClick={() => navigate('/models')}>
                <span className="pill-inner">{t('common.allModels')}</span>
              </button>
            </div>
          </div>
          <div className="demo-chat-col">
            <ChatPanel persona={ELON} greeting={t('chat.greet.elon')} quick={ELON_QUICK} voiceGroup={ELON_VOICES} />
          </div>
        </div>
        <p className="demo-disclaimer">{t('demo.disclaimer')}</p>
      </div>
    </section>
  )
}
