import { useEffect, useState } from 'react'
import { navigate } from '../router'
import { Emblem } from './Emblems'

// Hero preview of what an answer looks like. Every answer below is a
// verbatim passage from the public-domain text the model is built from
// (CHRONUS/figures/data), and the last one is the real "I don't know"
// reply, so the preview shows nothing the product wouldn't.
const EXAMPLES = [
  {
    id: 'marcus_aurelius', name: 'Marcus Aurelius',
    q: 'How do I find peace when life gets busy?',
    a: 'At what time soever thou wilt, it is in thy power to retire into thyself, and to be at rest, and free from all businesses.',
    source: 'Meditations', voice: 'own words', confidence: 'high',
  },
  {
    id: 'abraham_lincoln', name: 'Abraham Lincoln',
    q: 'What were the soldiers at Gettysburg fighting for?',
    a: '...that this nation, under God, shall have a new birth of freedom; and that government of the people, by the people, and for the people, shall not perish from the earth.',
    source: 'Speeches and Letters', voice: 'own words', confidence: 'high',
  },
  {
    id: 'marie_curie', name: 'Marie Curie',
    q: 'When did you discover radium?',
    a: 'We announced the existence of polonium in July, 1898, and of radium in December of the same year.',
    source: 'Pierre Curie (her biography of him)', voice: 'own words', confidence: 'high',
  },
  {
    id: 'albert_einstein', name: 'Albert Einstein',
    q: "What's your favourite pizza topping?",
    a: "I don't have any documented information about that in my available records.",
    source: null, voice: null, confidence: 'low',
  },
]

const TYPE_MS = 22
const HOLD_MS = 4200

export default function AnswerPreview() {
  const [index, setIndex] = useState(0)
  const [typed, setTyped] = useState(0)
  const example = EXAMPLES[index]
  const done = typed >= example.a.length

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { setTyped(example.a.length); return }
    if (!done) {
      const id = setTimeout(() => setTyped(n => Math.min(example.a.length, n + 2)), TYPE_MS)
      return () => clearTimeout(id)
    }
    const id = setTimeout(() => { setIndex(i => (i + 1) % EXAMPLES.length); setTyped(0) }, HOLD_MS)
    return () => clearTimeout(id)
  }, [typed, done, example])

  const pick = (i) => { setIndex(i); setTyped(0) }

  return (
    <div className="answer-preview">
      <div className="ap-head">
        <span className="ap-avatar"><Emblem id={example.id} /></span>
        <div className="ap-who">
          <strong>{example.name}</strong>
          <span>chronus-model:{example.id}</span>
        </div>
        <span className="ap-live"><span />Example</span>
      </div>

      <div className="ap-body" aria-live="off">
        <div className="ap-q">{example.q}</div>
        <div className={`ap-a${example.source ? '' : ' ap-a--fallback'}`}>
          {example.source && <span className="ap-quote-mark" aria-hidden="true">“</span>}
          {example.a.slice(0, typed)}
          {!done && <span className="ap-caret" aria-hidden="true" />}
        </div>
        <div className={`ap-meta${done ? ' is-shown' : ''}`}>
          {example.source ? (
            <>
              <span className="ap-chip ap-chip--source">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z" /><path d="M4 19.5V21h16" /></svg>
                {example.source}
              </span>
              <span className="ap-chip ap-chip--voice">{example.voice}</span>
              <span className="ap-chip">verbatim</span>
            </>
          ) : (
            <span className="ap-chip ap-chip--honest">No source found, so it says so</span>
          )}
          <span className={`ap-confidence ap-confidence--${example.confidence}`}>{example.confidence} confidence</span>
        </div>
      </div>

      <div className="ap-foot">
        <div className="ap-dots" role="tablist" aria-label="Examples">
          {EXAMPLES.map((e, i) => (
            <button key={e.id} role="tab" aria-selected={i === index} aria-label={e.name} className={i === index ? 'is-active' : ''} onClick={() => pick(i)} />
          ))}
        </div>
        <button className="ap-open" onClick={() => navigate(`/chat/${example.id}`)}>Ask {example.name.split(' ')[0]} yourself →</button>
      </div>
    </div>
  )
}
