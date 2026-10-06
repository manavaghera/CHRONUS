import { navigate } from '../router'
import useScrollReveal from './useScrollReveal'
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

const STEPS = [
  {
    num: '01', tag: 'CONSENT FIRST', title: 'Start with permission',
    desc: "Name the person and your relationship to them, and confirm you have their consent (or their estate's). The consent is recorded with the model. Nothing leaves your computer unless you turn the cloud AI voice on.",
    features: ['Consent statement saved with a timestamp', 'Private by default: models live on your machine', 'Delete everything, vectors and files, in one click'],
    Mock: ConsentMock,
  },
  {
    num: '02', tag: 'THEIR OWN WORDS', title: 'Add letters, journals and transcripts',
    desc: 'Upload what they wrote or said. Each file is split into short memories and embedded for search. Mark whether a file is in their own words or written about them, so a biography is never quoted as something they said.',
    features: ['.txt, .md, .pdf, .docx, .csv and .json, up to 10 MB each', 'Re-uploading a file replaces its old memories', 'Every memory keeps its source file and page'],
    Mock: UploadMock,
  },
  {
    num: '03', tag: 'GUIDED INTERVIEW', title: 'Fill the gaps with 25 questions',
    desc: 'A structured interview across six dimensions, from personality to how they talk, captures what documents miss. Answers can come from the person or from family and friends, and the model always says who answered.',
    features: ['6 dimensions: personality, memories, relationships, passions, values, voice', 'Answering again replaces the earlier answer', 'Built once there are at least 10 memories'],
    Mock: InterviewMock,
  },
  {
    num: '04', tag: 'TALK & VERIFY', title: 'Ask, check the source, listen',
    desc: "Answers are built from the closest memories, quoted or carefully tidied, with every source and its match strength one click away. If nothing in the archive fits, it says “I don't know” instead of guessing.",
    features: ['Verbatim quotes mode, or an AI voice grounded in the quotes', 'Listen in their consented voice (optional)', 'Low-confidence answers are labelled as such'],
    Mock: ChatMock,
  },
]

function Step({ step, index }) {
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
          <div className="train-step-tag">{step.tag}</div>
          <h3>{step.title}</h3>
          <p>{step.desc}</p>
          <ul className="train-step-features">
            {step.features.map(f => <li key={f}>{f}</li>)}
          </ul>
        </div>
        <div className="train-step-visual"><Mock /></div>
      </div>
    </div>
  )
}

export default function TrainYourModel() {
  const [hRef, hIn] = useScrollReveal()
  return (
    <section className="train-section" id="train">
      <div className="shell train-inner">
        <div ref={hRef} className={`train-header sr ${hIn ? 'in-view' : ''}`}>
          <div className="eyebrow eyebrow--dark">CREATE YOUR MODEL</div>
          <h2 className="train-h2">Preserve someone's words</h2>
          <p className="train-sub">Four steps, all in your browser, to a model that answers only from what they actually said.</p>
        </div>
        <div className="train-timeline">
          {STEPS.map((step, i) => <Step key={step.num} step={step} index={i} />)}
        </div>
        <div className="train-cta">
          <div>
            <h3>Ready when you are.</h3>
            <p>Start a model now, or try the voice sandbox to hear how a consented voice clone sounds first.</p>
          </div>
          <div className="train-cta-actions">
            <button className="pill-btn pill-btn--dark" onClick={() => navigate('/create')}><span className="pill-inner">Create a model</span></button>
            <button className="pill-btn pill-btn--outline" onClick={() => navigate('/clone-voice')}><span className="pill-inner">Open the voice sandbox</span></button>
          </div>
        </div>
      </div>
    </section>
  )
}
