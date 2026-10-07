import { navigate } from '../router'
import useScrollReveal from './useScrollReveal'
import { useT } from '../i18n'
import './train.css'

// The real "Create your model" flow (pages/CreatePage.jsx), each step shown
// with an illustrated mockup of its screen. The mockups are plain HTML, so
// they always render, and they only show what the product actually does.

const Check = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12l5 5L20 7" /></svg>
const Doc = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6M8 13h8M8 17h5" /></svg>

function ConsentMock() {
  return (
    <div className="mock mock-consent">
      <div className="mock-bar"><span /><span /><span /><em>Create a model</em></div>
      <div className="mock-field"><label>Name</label><div>Kamla Patel</div></div>
      <div className="mock-field"><label>Your relationship</label><div>Family ▾</div></div>
      <div className="mock-check is-on"><span><Check /></span>I am this person, or I have their permission (or their estate's) to build this model from their words.</div>
      <div className="mock-row">
        <div className="mock-toggle"><span />Cloud AI voice <b>off</b></div>
        <div className="mock-stamp">Consent recorded · 14:02</div>
      </div>
    </div>
  )
}

function UploadMock() {
  const files = [
    ['letters_to_ravi.docx', 'their words', 42],
    ['diary_1987.pdf', 'their words', 118],
    ['school_newsletter.txt', 'about them', 9],
  ]
  return (
    <div className="mock mock-upload">
      <div className="mock-bar"><span /><span /><span /><em>Documents</em></div>
      <div className="mock-drop">Drop files · .txt .md .pdf .docx .csv .json</div>
      <ul className="mock-files">
        {files.map(([name, who, n], i) => (
          <li key={name} style={{ animationDelay: `${i * 0.15}s` }}>
            <span className="mock-file-icon"><Doc /></span>
            <span className="mock-file-name">{name}</span>
            <span className={`mock-tag${who === 'about them' ? ' mock-tag--muted' : ''}`}>{who}</span>
            <span className="mock-count">{n} memories</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function InterviewMock() {
  const dims = [['Personality', 4, 4], ['Core memories', 3, 4], ['Relationships', 2, 4], ['Passions', 1, 4], ['Beliefs & values', 0, 4], ['Voice', 0, 5]]
  return (
    <div className="mock mock-interview">
      <div className="mock-bar"><span /><span /><span /><em>Interview · 10 of 25</em></div>
      <div className="mock-question">
        <span className="mock-qid">Q5</span>
        What experience or period in your life most fundamentally shaped who you are today?
        <div className="mock-answer">The monsoon of 1987, when the river flooded the village and we carried the goats up to the temple steps…</div>
        <div className="mock-origin">Answered by: <b>family</b></div>
      </div>
      <ul className="mock-dims">
        {dims.map(([d, done, total]) => (
          <li key={d}><span>{d}</span><i><b style={{ width: `${(done / total) * 100}%` }} /></i></li>
        ))}
      </ul>
    </div>
  )
}

function ChatMock() {
  return (
    <div className="mock mock-chat">
      <div className="mock-bar"><span /><span /><span /><em>Chat · Kamla Patel</em></div>
      <div className="mock-bubble mock-bubble--you">What was your favourite birthday?</div>
      <div className="mock-bubble mock-bubble--them">In my own words: “My favourite birthday was my eighteenth. My father bought me a blue Hero bicycle…”</div>
      <div className="mock-sources">
        <div><span className="mock-tag">own words</span>letters_to_ravi.docx<em>match 81%</em></div>
        <div><span className="mock-tag">own words</span>Interview · Q5<em>match 64%</em></div>
      </div>
      <div className="mock-listen">
        <span className="mock-play">▶</span>
        <span className="mock-wave">{Array.from({ length: 28 }, (_, i) => <i key={i} style={{ height: `${25 + Math.abs(Math.sin(i * 1.7)) * 75}%` }} />)}</span>
        <span className="mock-voice">consented voice</span>
      </div>
    </div>
  )
}

// Each step's words are in strings/home.js: s1.tag, s1.title, s1.desc, s1.f1 to s1.f3...
const STEPS = [
  { num: '01', key: 's1', Mock: ConsentMock },
  { num: '02', key: 's2', Mock: UploadMock },
  { num: '03', key: 's3', Mock: InterviewMock },
  { num: '04', key: 's4', Mock: ChatMock },
]

function Step({ step, index }) {
  const t = useT()
  const [ref, inView] = useScrollReveal(0.2)
  const { Mock } = step
  return (
    <div ref={ref} className={`train-step ${inView ? 'in-view' : ''}`} style={{ transitionDelay: `${index * 80}ms` }}>
      <div className="train-step-left">
        <div className="train-step-num">{step.num}</div>
        <div className="train-step-line" />
      </div>
      <div className={`train-step-card${index % 2 ? ' is-flipped' : ''}`}>
        <div className="train-step-text">
          <div className="train-step-tag">{t(`${step.key}.tag`)}</div>
          <h3>{t(`${step.key}.title`)}</h3>
          <p>{t(`${step.key}.desc`)}</p>
          <ul className="train-step-features">
            {[1, 2, 3].map(n => <li key={n}>{t(`${step.key}.f${n}`)}</li>)}
          </ul>
        </div>
        <div className="train-step-visual"><Mock /></div>
      </div>
    </div>
  )
}

export default function TrainYourModel() {
  const t = useT()
  const [hRef, hIn] = useScrollReveal()
  return (
    <section className="train-section" id="train">
      <div className="shell train-inner">
        <div ref={hRef} className={`train-header sr ${hIn ? 'in-view' : ''}`}>
          <div className="eyebrow eyebrow--dark">{t('create.eyebrow').toLocaleUpperCase()}</div>
          <h2 className="train-h2">{t('train.title')}</h2>
          <p className="train-sub">{t('train.sub')}</p>
        </div>
        <div className="train-timeline">
          {STEPS.map((step, i) => <Step key={step.num} step={step} index={i} />)}
        </div>
        <div className="train-cta">
          <div>
            <h3>{t('train.readyTitle')}</h3>
            <p>{t('train.readySub')}</p>
          </div>
          <div className="train-cta-actions">
            <button className="pill-btn pill-btn--dark" onClick={() => navigate('/create')}><span className="pill-inner">{t('common.createModel')}</span></button>
            <button className="pill-btn pill-btn--outline" onClick={() => navigate('/clone-voice')}><span className="pill-inner">{t('train.sandbox')}</span></button>
          </div>
        </div>
      </div>
    </section>
  )
}
