import ChatPanel from './ChatPanel'
import { navigate } from '../router'

export const ELON = { id: 'elon_musk', name: 'Elon Musk' }
export const ELON_GREETING = "Hi, I'm a CHRONUS model of Elon Musk, built from his public interviews, tweets and biographies. Every answer is grounded in those sources, and you can check them under each reply.\n\nAsk me anything."
export const ELON_QUICK = ['Why Mars?', 'Why did you buy Twitter?', 'How do you handle failure?', 'Is AI dangerous?', 'Tell me about your childhood']
export const ELON_VOICES = { first_person: 'his words', third_party: 'about him', synthesized: 'synthesized' }

const ARROW = <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 17 17 7M8 7h9v9"/></svg>

export default function LiveDemo() {
  return (
    <section className="demo-section" id="demo" style={{ position: 'relative', zIndex: 10 }}>
      <div className="shell demo-inner">
        <div className="sr in-view" style={{ marginBottom: '1rem' }}><div className="eyebrow eyebrow--accent">Live Demo</div></div>
        <div className="demo-wrapper">
          <div className="demo-text-col sr in-view">
            <h2>Talk to a CHRONUS model</h2>
            <p className="demo-desc">See how a preserved intelligence responds to questions with depth, nuance, and voice. Every answer is traced back to something real.</p>
            <div className="demo-model-select"><span/>chronus-model:{ELON.id}</div>
            <div className="demo-cta-row">
              <button className="pill-btn pill-btn--accent pill-btn--with-arrow" onClick={() => navigate('/create')}>
                <span className="pill-inner">Create your own model<span className="pill-badge pill-arrow-upright">{ARROW}</span></span>
              </button>
              <button className="pill-btn pill-btn--outline" onClick={() => navigate('/models')}>
                <span className="pill-inner">All models</span>
              </button>
            </div>
          </div>
          <div className="demo-chat-col">
            <ChatPanel persona={ELON} greeting={ELON_GREETING} quick={ELON_QUICK} voiceLabels={ELON_VOICES} />
          </div>
        </div>
        <p className="demo-disclaimer">Live connection to the CHRONUS backend. This is an AI simulation built from Elon Musk's public interviews, tweets and biographies. It is not the real person and is not affiliated with him.</p>
      </div>
    </section>
  )
}
