import useScrollReveal from './useScrollReveal'

const steps = [
  {
    num: '01',
    label: 'Step One',
    tag: 'DATA INGESTION',
    title: 'Upload Everything You Know',
    desc: 'Feed CHRONUS the full breadth of a person\'s knowledge — voice recordings, journals, research papers, emails, transcripts, handwritten notes, and more. The richer and more varied the input, the more nuanced and accurate the resulting intelligence.',
    features: [
      'Audio & video recordings in any format',
      'PDFs, DOCX, TXT, and Markdown files',
      'Structured data: notes, Q&A logs, annotations',
      'Up to 10 GB on Pro — unlimited on Enterprise',
    ],
    images: [
      { gradient: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)', icon: 'mountains' },
      { gradient: 'linear-gradient(135deg, #ff6b6b 0%, #ee5a24 50%, #f39c12 100%)', icon: 'cubes' },
    ],
  },
  {
    num: '02',
    label: 'Step Two',
    tag: 'SEMANTIC ENGINE',
    title: 'Process & Structure Your Knowledge',
    desc: 'CHRONUS parses every piece of content, extracting meaning, building a semantic knowledge graph, and mapping the unique way this mind connects ideas. It doesn\'t just index words — it understands the reasoning patterns behind them.',
    features: [
      'Automatic entity & concept extraction',
      'Cross-document relationship mapping',
      'Temporal context & memory sequencing',
      'Contradiction detection & resolution',
    ],
    images: [
      { gradient: 'linear-gradient(135deg, #0c0c1d 0%, #1a1a3e 50%, #2d2d5e 100%)', icon: 'chart' },
      { gradient: 'linear-gradient(135deg, #1e3c72 0%, #2a5298 50%, #3a7bd5 100%)', icon: 'code' },
    ],
  },
  {
    num: '03',
    label: 'Step Three',
    tag: 'MODEL TRAINING',
    title: 'Build the Personal Intelligence Model',
    desc: 'Using the processed knowledge graph, CHRONUS fine-tunes a dedicated model that reflects this specific mind — not a generic language model, but one that reasons, prioritizes, and responds the way this person actually would. Training completes in hours, not weeks.',
    features: [
      'Private fine-tuning on isolated infrastructure',
      'Iterative refinement with feedback loops',
      'Personality & reasoning style calibration',
      'Real-time training progress dashboard',
    ],
    images: [
      { gradient: 'linear-gradient(135deg, #0d1117 0%, #161b22 50%, #21262d 100%)', icon: 'brain' },
      { gradient: 'linear-gradient(135deg, #2d1b4e 0%, #4a2c7a 50%, #6b3fa0 100%)', icon: 'network' },
    ],
  },
  {
    num: '04',
    label: 'Step Four',
    tag: 'DEPLOYMENT',
    title: 'Chat, Query & Hear Your Model',
    desc: 'Your intelligence is live. Ask it anything — in text or voice. Receive answers grounded in its actual knowledge, in the tone and manner of the real person. Embed it in your products via API, share it selectively, or keep it entirely private.',
    features: [
      'Text & voice response modes',
      'REST API with full SDK support',
      'Granular sharing & access controls',
      'Continuous improvement from interactions',
    ],
    images: [
      { gradient: 'linear-gradient(135deg, #1a1a2e 0%, #2d2d44 50%, #3d3d5c 100%)', icon: 'chat' },
      { gradient: 'linear-gradient(135deg, #2c3e50 0%, #34495e 50%, #4a6785 100%)', icon: 'wave' },
    ],
  },
]

function ImagePlaceholder({ gradient, icon }) {
  return (
    <div className="train-step-image" style={{ background: gradient }}>
      <svg viewBox="0 0 100 60" fill="none" xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" opacity="0.3">
        {icon === 'mountains' && (
          <>
            <path d="M0 50 L25 20 L50 45 L75 15 L100 50 Z" fill="rgba(255,255,255,0.2)" />
            <path d="M0 55 L30 30 L60 50 L90 25 L100 55 Z" fill="rgba(255,255,255,0.15)" />
          </>
        )}
        {icon === 'cubes' && (
          <>
            <rect x="20" y="20" width="25" height="25" rx="3" fill="rgba(255,100,100,0.4)" />
            <rect x="55" y="15" width="30" height="30" rx="3" fill="rgba(255,200,50,0.3)" />
            <circle cx="70" cy="45" r="12" fill="rgba(0,200,100,0.3)" />
          </>
        )}
        {icon === 'chart' && (
          <>
            <rect x="15" y="35" width="12" height="20" fill="rgba(0,150,255,0.4)" />
            <rect x="32" y="25" width="12" height="30" fill="rgba(0,200,150,0.4)" />
            <rect x="49" y="15" width="12" height="40" fill="rgba(0,255,200,0.4)" />
            <rect x="66" y="20" width="12" height="35" fill="rgba(100,200,255,0.4)" />
            <path d="M15 30 L35 20 L55 10 L75 15" stroke="rgba(255,255,255,0.5)" strokeWidth="2" fill="none" />
          </>
        )}
        {icon === 'code' && (
          <>
            <text x="15" y="25" fill="rgba(0,200,150,0.5)" fontSize="8" fontFamily="monospace">{'{'}</text>
            <text x="25" y="35" fill="rgba(0,150,255,0.5)" fontSize="8" fontFamily="monospace">data:</text>
            <text x="25" y="45" fill="rgba(255,200,100,0.5)" fontSize="8" fontFamily="monospace">process()</text>
            <text x="70" y="25" fill="rgba(0,200,150,0.5)" fontSize="8" fontFamily="monospace">{'}'}</text>
          </>
        )}
        {icon === 'brain' && (
          <>
            <circle cx="50" cy="30" r="20" fill="rgba(150,100,200,0.3)" />
            <path d="M35 30 Q50 10 65 30 Q50 50 35 30" fill="rgba(200,150,255,0.2)" />
            <circle cx="40" cy="25" r="4" fill="rgba(255,200,100,0.4)" />
            <circle cx="60" cy="25" r="4" fill="rgba(100,255,200,0.4)" />
            <circle cx="50" cy="35" r="4" fill="rgba(100,200,255,0.4)" />
          </>
        )}
        {icon === 'network' && (
          <>
            <circle cx="50" cy="30" r="8" fill="rgba(100,200,255,0.4)" />
            <circle cx="25" cy="20" r="5" fill="rgba(255,150,100,0.4)" />
            <circle cx="75" cy="20" r="5" fill="rgba(150,255,150,0.4)" />
            <circle cx="30" cy="45" r="5" fill="rgba(255,200,100,0.4)" />
            <circle cx="70" cy="45" r="5" fill="rgba(200,150,255,0.4)" />
            <line x1="50" y1="30" x2="25" y2="20" stroke="rgba(255,255,255,0.3)" strokeWidth="1" />
            <line x1="50" y1="30" x2="75" y2="20" stroke="rgba(255,255,255,0.3)" strokeWidth="1" />
            <line x1="50" y1="30" x2="30" y2="45" stroke="rgba(255,255,255,0.3)" strokeWidth="1" />
            <line x1="50" y1="30" x2="70" y2="45" stroke="rgba(255,255,255,0.3)" strokeWidth="1" />
          </>
        )}
        {icon === 'chat' && (
          <>
            <rect x="15" y="15" width="35" height="25" rx="5" fill="rgba(100,200,255,0.3)" />
            <rect x="50" y="20" width="35" height="25" rx="5" fill="rgba(150,255,200,0.3)" />
            <path d="M25 45 L25 55 L35 45" fill="rgba(100,200,255,0.3)" />
          </>
        )}
        {icon === 'wave' && (
          <>
            <path d="M0 30 Q25 10 50 30 Q75 50 100 30" stroke="rgba(100,200,255,0.4)" strokeWidth="3" fill="none" />
            <path d="M0 35 Q25 15 50 35 Q75 55 100 35" stroke="rgba(150,255,200,0.3)" strokeWidth="2" fill="none" />
            <path d="M0 40 Q25 20 50 40 Q75 60 100 40" stroke="rgba(200,150,255,0.2)" strokeWidth="2" fill="none" />
          </>
        )}
      </svg>
    </div>
  )
}

function Step({ step, index }) {
  const [ref, inView] = useScrollReveal(0.2)

  return (
    <div ref={ref} className={`train-step ${inView ? 'in-view' : ''}`} style={{ transitionDelay: `${index * 100}ms` }}>
      <div className="train-step-left">
        <div className="train-step-num">{step.num}</div>
        <div className="train-step-label">{step.label}</div>
        <div className="train-step-line" />
      </div>
      <div className="train-step-card">
        <div className="train-step-tag">{step.tag}</div>
        <h3>{step.title}</h3>
        <p>{step.desc}</p>
        <ul className="train-step-features">
          {step.features.map((f, i) => (
            <li key={i}>{f}</li>
          ))}
        </ul>
        <div className="train-step-images">
          {step.images.map((img, i) => (
            <ImagePlaceholder key={i} gradient={img.gradient} icon={img.icon} />
          ))}
        </div>
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
          <div className="eyebrow eyebrow--dark">TRAIN YOUR MODEL</div>
          <h2 className="train-h2">Build your own intelligence</h2>
          <p className="train-sub">Four steps to create a personal AI that thinks, speaks, and reasons exactly like you.</p>
        </div>
        <div className="train-timeline">
          {steps.map((step, i) => (
            <Step key={i} step={step} index={i} />
          ))}
        </div>
      </div>
    </section>
  )
}