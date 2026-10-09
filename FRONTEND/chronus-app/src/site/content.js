// The company website's content in one place: prices, principles, FAQ, the
// Lab roadmap, team and company details. English only for now. [Square
// brackets] mark details to fill in before launch.

export const COMPANY = {
  name: '[Yet to decided :)] Ltd',
  number: '[NA]',
  registeredIn: '[India]',
  office: '[WFH]',
  email: '[Not yet',
  privacyEmail: '[Noy Yet]',
}

export const FOUNDER = {
  name: 'Manav Aghera',
  role: 'Founder',
  bio: '[Computer Science student deeply intrigued by AI/ML, continuously exploring frontier domains such as Grief Tech, Deep Tech, AGI, Superintelligence, and emerging computational paradigms.]',
  links: [['LinkedIn', 'https://www.linkedin.com/in/manav-aghera/'], ['X', 'https://x.com/aghera_manav']],
}

// ---- Pricing ----
// One-time per person; same price everywhere, shown in USD with approximate
// local amounts. Rates: ECB reference rates, March 2026. Update before launch.
export const RATES = { asOf: 'March 2026', GBP: 0.749, EUR: 0.866, INR: 92.3 }
export const PLANS = [
  {
    id: 'words', name: 'Words', usd: 549,
    line: 'Their memories and personality, in their own words.',
    features: ['Upload letters, journals, photos of pages and voice notes', '25-question guided interview with follow-ups',
      'Identity profile from their own sentences', 'Chat in verbatim quotes or the AI voice, every answer cited',
      'Time travel, memory browser and insights', 'Encrypted backup you can download any time'],
  },
  {
    id: 'voice', name: 'Voice', usd: 799, featured: true,
    line: 'Everything in Words, and they answer in their own voice.',
    features: ['Everything in Words', 'Their cloned voice, made with their consent', 'Hands-free conversation: ask aloud, hear them answer',
      '“In their spirit” answers, clearly labelled, if you allow them', 'Style learning from their answers, once there are enough'],
  },
  {
    id: 'legacy', name: 'Legacy (guided)', usd: 1499,
    line: 'We help you capture a whole life, with a person beside you.',
    features: ['Everything in Voice', 'A guided interview session with a CHRONUS interviewer', 'Help gathering and labelling letters, photos and recordings',
      'Life chapters: childhood, family, work, beliefs, advice', 'Priority support for the family'],
  },
]
// Every person after the first in one order gets this discount
export const DISCOUNTS = [[2, 15], [3, 20], [5, 25]] // [from this many people, % off each extra person]
export const HOSTING = { gbp: 19, freeYears: 1 }

export const fmt = (amount, currency) => new Intl.NumberFormat({ INR: 'en-IN', USD: 'en-US' }[currency] || 'en-GB',
  { style: 'currency', currency, maximumFractionDigits: 0 }).format(amount)
export const approx = (usd) => ['GBP', 'EUR', 'INR'].map(c => fmt(Math.round(usd * RATES[c]), c)).join(' · ')

/** % off for each person after the first, when buying for *people* */
export function discountFor(people) {
  return DISCOUNTS.reduce((pct, [from, off]) => (people >= from ? off : pct), 0)
}
/** Total in USD for *people* on one plan: the first full price, the rest discounted */
export function totalFor(usd, people) {
  if (people < 1) return 0
  return Math.round(usd + (people - 1) * usd * (1 - discountFor(people) / 100))
}

// ---- Principles (Vision page, and the Trust centre) ----
export const PRINCIPLES = [
  ['Consent first', 'Nothing starts without their yes, or, for someone who has died, the family’s agreement. The record stays with the model, and consent can be paused, renewed or withdrawn.'],
  ['Never invent', 'Every answer comes from something they said or wrote, with the source attached. When nothing covers a question, it says “I don’t know”.'],
  ['Their words, labelled', 'Their own words, words written about them and inferred answers are always told apart. Only their own words are ever quoted as theirs.'],
  ['Delete means delete', 'Remove a model and its memories, files, cloned voice, logs and feedback all go with it.'],
  ['Private by design', 'Each family’s archive is theirs. No selling data, no training general AI on anyone’s memories.'],
  ['Gentle with grief', 'Memorial mode, break reminders in long conversations, and help lines when someone is struggling. A model is a keepsake, not a replacement for people.'],
  ['Honest about the future', 'We say plainly what the technology can and can’t do today, and what is only research.'],
]

// ---- CHRONUS Lab: research, not products ----
export const LAB = [
  { stage: 'Today', status: 'In CHRONUS now', items: [
    ['Their words, personality and voice', 'Memories searched by meaning, an identity profile from their own sentences, and a consented voice clone.'],
    ['Answers that never invent', 'Every answer cites its sources; with nothing to go on, it says “I don’t know”.'],
  ] },
  { stage: 'Next', status: 'Being tested', items: [
    ['Style models', 'A small neural network per person that learns how they talk, used only after it passes an exam against their real answers.'],
    ['Life chapters', 'Guided recording sessions that capture a whole life, chapter by chapter.'],
  ] },
  { stage: 'Exploring', status: 'Research, not a product', items: [
    ['Video memories', 'Faces, gestures and expressions from family videos, with consent.'],
    ['Richer personality maps', 'How someone reasons, not only what they said, learned from far more conversation.'],
  ] },
  { stage: 'Horizon', status: 'Watching the science', items: [
    ['Brain mapping', 'Scientists have mapped every connection of a fruit fly’s brain (FlyWire, 2024) and run it in a simulated body (Eon Systems, 2026). A human brain has about 600,000 times more neurons.'],
    ['Biological computers', 'Living human neurons grown on chips (Cortical Labs CL1) can learn simple tasks, but they start blank: they hold no one’s memories.'],
    ['Reading memories', 'No one can yet read a memory from a brain. A $100,000 prize for decoding one from a preserved brain map is still unclaimed.'],
  ] },
]

// ---- FAQ page ----
export const FAQ = [
  ['The product', [
    ['Is it really them?', 'No, and it never pretends to be. It is a model built only from what they said, wrote and answered. It shows where each answer came from, and says “I don’t know” when their words don’t cover something.'],
    ['What do I need to preserve someone?', 'Their consent, some of their words (letters, journals, notes, photos of handwritten pages, voice notes) and answers to a 25-question interview. You can keep adding memories later.'],
    ['Can I preserve someone who has died?', 'Yes, in memorial mode, with the family’s agreement. Answers use gentler framing, and long sessions get a break reminder.'],
    ['Which languages does it speak?', 'You can ask in Hindi, Gujarati and other languages, and with the AI voice on, hear the answer in that language with the English original shown. The website itself is in English.'],
  ]],
  ['Pricing', [
    ['Is it a subscription?', 'No. You pay once per person. The first year of hosting is included; after that it is £19 per person per year.'],
    ['What happens if I stop paying for hosting?', 'The model is archived, not deleted, and you can still download its encrypted backup.'],
    ['Is there a discount for a family?', 'Yes: the second person is 15% off, 3 to 4 people 20% off each, and 5 or more 25% off each.'],
    ['When can I buy?', 'CHRONUS is not on sale yet. Join the waitlist and we will tell you when it is.'],
  ]],
  ['Privacy and safety', [
    ['Who can see a model?', 'Only the account that made it. Sharing a model with family members you invite is planned.'],
    ['How is their voice cloned?', 'With consent, a short recording becomes a private voice. Removing it deletes it everywhere, including at our voice provider.'],
    ['What if someone made a model of me without asking?', 'Report it on the Report a model page. We review every report and take models down that were made without consent.'],
    ['Do you use our memories to train AI?', 'No general AI is trained on anyone’s memories. A style model, if you turn it on, is trained only for that one person and stays with their model.'],
  ]],
]

// ---- Trust centre ----
export const TRUST = [
  ['How an answer is made', 'Your question is matched against their memories by meaning. Only memories close enough are used, and every answer cites them.', '#/how-it-works'],
  ['Three kinds of answer', '“From their words” cites real memories. “In their spirit” is inferred and labelled so. “I don’t know” when nothing covers it.', '#/how-it-works'],
  ['Consent and voice', 'Consent is recorded with the model. Voice cloning needs separate consent and can be removed at any time.', '#/legal/voice-consent'],
  ['Crisis support', 'Every message is checked for crisis language first. If it is there, the model steps out of character and shows help lines.', '#/wellbeing'],
  ['Your data', 'Download everything, delete everything, see every consent decision. Nothing is sold.', '#/legal/privacy'],
  ['Report a model', 'Made without consent, impersonating someone, or causing harm? Tell us and we will act.', '#/report'],
]

export const PARTNERS = [
  ['Hospices and palliative care', 'Help patients leave their stories and voice for the people they love, while they can still tell them.'],
  ['Care homes', 'Capture residents’ life stories with their families, as an activity that brings generations together.'],
  ['Grief counsellors', 'A carefully framed keepsake, with break reminders and help lines built in.'],
  ['Funeral and memorial services', 'A memorial that families can talk to, made with the family’s agreement.'],
]
