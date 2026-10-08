// Static copy the site shows before (or without) the server.
// Labels are English keys, translated where they are shown (i18n.jsx).
import { tx } from '../i18n'

// The guided interview's six dimensions (CHRONUS/data/interview_protocol.py).
// The Create page loads the live list from GET /interview/questions.
export const DIMENSIONS = [
  { key: 'personality', label: tx('Personality'), short: tx('Personality'), ids: ['Q1', 'Q2', 'Q3', 'Q4'],
    sample: tx('How would you describe your core personality in a few sentences?') },
  { key: 'core_memories', label: tx('Core memories'), short: tx('Memories'), ids: ['Q5', 'Q6', 'Q7', 'Q8'],
    sample: tx('What experience or period in your life most fundamentally shaped who you are today?') },
  { key: 'relationships', label: tx('Relationships'), short: tx('Relationships'), ids: ['Q9', 'Q10', 'Q11', 'Q12'],
    sample: tx('Who has been the most influential person in your life and why?') },
  { key: 'passions', label: tx('Passions'), short: tx('Passions'), ids: ['Q13', 'Q14', 'Q15', 'Q16'],
    sample: tx('What topic could you talk about for hours without getting bored?') },
  { key: 'beliefs_values', label: tx('Beliefs and values'), short: tx('Beliefs'), ids: ['Q17', 'Q18', 'Q19', 'Q20'],
    sample: tx('What principle or belief would you never compromise on, no matter the cost?') },
  { key: 'voice_communication', label: tx('Voice'), short: tx('Voice'), ids: ['Q21', 'Q22', 'Q23', 'Q24', 'Q25'],
    sample: tx('What words or phrases do you use frequently that feel distinctly “you”?') },
]

// Share of each dimension answered, from a persona's interview_answered ids
export function coverage(answered = []) {
  const set = new Set(answered)
  return DIMENSIONS.map(d => d.ids.filter(id => set.has(id)).length / d.ids.length)
}

// Backend relationship values (services/persona_routes.py PersonaCreate)
export const RELATIONSHIPS = [
  ['family', tx('Family')], ['friend', tx('Friend')], ['colleague', tx('Colleague')], ['self', tx('Myself')], ['other', tx('Other')],
]
export const relLabel = (v) => (RELATIONSHIPS.find(r => r[0] === v) || [v, tx('Someone')])[1]

// Who answered an interview question (InterviewAnswer.origin)
export const ORIGINS = [
  ['self', tx('They are answering')], ['family', tx('Family, about them')], ['friend', tx('A friend, about them')], ['colleague', tx('A colleague, about them')],
]

// Lifespans and fields for the pretrained figures' time scrubber
export const FIGURES = {
  marcus_aurelius: { b: 121, d: 180, years: tx('121–180 AD'), field: tx('Philosophy'), mono: 'MA' },
  william_shakespeare: { b: 1564, d: 1616, years: '1564–1616', field: tx('Literature'), mono: 'WS' },
  abraham_lincoln: { b: 1809, d: 1865, years: '1809–1865', field: tx('Politics'), mono: 'AL' },
  nikola_tesla: { b: 1856, d: 1943, years: '1856–1943', field: tx('Science'), mono: 'NT' },
  marie_curie: { b: 1867, d: 1934, years: '1867–1934', field: tx('Science'), mono: 'MC' },
  mahatma_gandhi: { b: 1869, d: 1948, years: '1869–1948', field: tx('Politics'), mono: 'MG' },
  albert_einstein: { b: 1879, d: 1955, years: '1879–1955', field: tx('Science'), mono: 'AE' },
  elon_musk: { b: 1971, d: 0, years: tx('Born 1971'), field: tx('Business'), mono: 'EM' },
}

export function initials(name = '') {
  const p = String(name).trim().split(/\s+/).filter(Boolean)
  return p.length ? (p[0][0] + (p.length > 1 ? p[p.length - 1][0] : '')).toUpperCase() : '+'
}
