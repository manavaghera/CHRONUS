// Legal pages as OUTLINES: what each policy must cover, for a solicitor to
// write. Not legal text. Launch markets: UK, EU and India (and beyond).
// UK GDPR + Data Protection Act 2018 · EU GDPR · EU AI Act · India DPDP Act 2023

const GDPR = ['UK GDPR and Data Protection Act 2018', 'EU GDPR', 'India Digital Personal Data Protection Act 2023']

export const LEGAL = [
  {
    slug: 'terms', title: 'Terms of Service', group: 'Core',
    summary: 'The contract between CHRONUS and everyone who uses it.',
    laws: ['UK Consumer Rights Act 2015', 'EU consumer law (Consumer Rights Directive)', 'Indian Consumer Protection Act 2019'],
    sections: [
      ['Who we are', ['Company name, number, registered office (see Company information)', 'How to contact us']],
      ['Who can use CHRONUS', ['Minimum age 18', 'You must have the consent described in the Voice cloning and Memorial policies', 'One person per account; keep sign-in details secret']],
      ['What CHRONUS is, and is not', ['An AI model built from a person’s own words, not the person', 'Answers can be wrong; “in their spirit” answers are inferred', 'Not medical, legal, financial or grief counselling advice']],
      ['Your content', ['You keep ownership of what you upload', 'Licence you give us only to run the service for you', 'You confirm you have the right to upload it']],
      ['Payments, hosting and cancellation', ['One-time price per person, first year of hosting included', 'Yearly hosting fee after that; what happens if unpaid (archive, export)', 'Cancellation rights: see Refunds and cancellation']],
      ['Acceptable use and takedowns', ['Rules in the Acceptable Use Policy', 'How we handle reports and remove models', 'Suspending accounts that break the rules']],
      ['Liability', ['Limits of our liability, and what can’t be limited by law', 'No liability for decisions made from AI answers']],
      ['Ending the service', ['How you close your account and delete everything', 'What happens to models if CHRONUS closes: notice period and export']],
      ['Law and disputes', ['Governing law and courts', 'Consumer rights in the user’s own country that still apply', 'Changes to these terms and how we tell you']],
    ],
  },
  {
    slug: 'privacy', title: 'Privacy Policy', group: 'Core',
    summary: 'What personal data CHRONUS collects, why, and the rights everyone has.',
    laws: GDPR,
    sections: [
      ['Who is responsible', ['Controller identity and contact details', 'Data Protection Officer, if one is needed (biometric data at scale)', 'EU and UK representatives if established elsewhere']],
      ['Whose data', ['Account holders', 'The person being preserved (living, with consent; or deceased)', 'Other people mentioned in uploaded letters, interviews and recordings', 'Waitlist, contact and report form senders']],
      ['What data', ['Account and contact details', 'Uploaded documents, photos, recordings and interview answers', 'Voice recordings and voice models: biometric, special category data', 'Questions asked and answers given; feedback', 'Consent records']],
      ['Why, and the legal basis for each', ['Providing the service (contract)', 'Voice cloning and sensitive memories (explicit consent)', 'Safety, fraud and abuse prevention (legitimate interests)', 'Launch emails to the waitlist (consent)']],
      ['Who else receives it', ['Service providers (see Service providers page): AI language model, voice cloning, hosting', 'No selling of personal data', 'Authorities only when the law requires']],
      ['International transfers', ['Countries data goes to (e.g. United States)', 'Safeguards: adequacy decisions, standard contractual clauses, UK addendum']],
      ['How long we keep it', ['See Data retention', 'Deleting a model deletes its memories, files, voice, logs and feedback']],
      ['Rights', ['Access, correction, deletion, restriction, objection, portability', 'Withdrawing consent at any time', 'India: grievance officer, nominating someone to act after death or incapacity', 'Complaints to the ICO, an EU supervisory authority or the Data Protection Board of India']],
      ['Data about people who have died', ['UK and EU GDPR do not protect the dead, but they protect the living people in their memories', 'How families can ask for a memorial model to be removed']],
      ['Children', ['Not for under-18s; what happens if a child’s data is uploaded']],
      ['Security', ['Summary of protections; see Security']],
    ],
  },
  {
    slug: 'cookies', title: 'Cookie Policy', group: 'Core',
    summary: 'Which cookies and browser storage the site uses.',
    laws: ['UK Privacy and Electronic Communications Regulations (PECR)', 'EU ePrivacy Directive'],
    sections: [
      ['What we use today', ['A sign-in cookie, only when the server requires sign-in (strictly necessary)', 'Browser storage for your theme, language and chat history, saved because you chose them', 'No advertising or tracking cookies']],
      ['If analytics are added', ['A consent banner before any non-essential cookie is set', 'List of each cookie, its purpose and lifetime']],
      ['How to clear them', ['Browser settings; clearing chat history from the chat page']],
    ],
  },
  {
    slug: 'acceptable-use', title: 'Acceptable Use Policy', group: 'Core',
    summary: 'What nobody may do with CHRONUS.',
    laws: ['Terms of Service', 'UK Online Safety Act 2023 (if sharing features are added)', 'EU Digital Services Act (if applicable)'],
    sections: [
      ['Consent', ['No model of a living person without their consent', 'No memorial model without the family’s agreement', 'No voice clone without the speaker’s consent']],
      ['No deception', ['No impersonating anyone to deceive, defraud or harass', 'No presenting AI answers as real statements by the person', 'No public figures’ voices cloned (pretrained figures use labelled stand-in voices)']],
      ['No harm', ['No children’s data', 'No hateful, sexual, violent or illegal content', 'No attempts to break, overload or misuse the service']],
      ['What happens', ['Removal of content or models', 'Suspension or closure of accounts', 'Reporting to authorities where required']],
    ],
  },
  {
    slug: 'voice-consent', title: 'Voice cloning and consent', group: 'Your data',
    summary: 'How a person’s voice is cloned, and how their consent works.',
    laws: [...GDPR, 'EU AI Act (labelling synthetic audio)'],
    sections: [
      ['Consent first', ['Explicit consent from the speaker, or for someone who has died, their estate or family', 'Separate consent to processing by our voice provider', 'What we record about the consent (who, when, what was shown)']],
      ['How the voice is made', ['Recording length and quality needed', 'Provider used and where it processes data', 'Voice kept private to that one model']],
      ['Labelling', ['Spoken answers are AI-generated audio and labelled as such', 'Pretrained figures use a stand-in voice, never a clone']],
      ['Withdrawing consent', ['Remove the voice at any time', 'Deletion here and at the provider', 'What happens to audio already downloaded by users']],
    ],
  },
  {
    slug: 'memorial', title: 'Memorial and deceased persons policy', group: 'Your data',
    summary: 'Who may preserve someone who has died, and how disagreements are handled.',
    laws: ['UK and EU GDPR (protect living people mentioned)', 'India DPDP Act 2023 (nominee rights)'],
    sections: [
      ['Who may create a memorial model', ['Next of kin, or with the family’s agreement', 'What we ask creators to confirm']],
      ['Framing and care', ['Memorial mode: past tense, never claims to be alive or watching over anyone', 'Break reminders and help lines']],
      ['When families disagree', ['How another relative can object', 'How we review and decide; pausing a model during review']],
      ['Ending a memorial model', ['Who can ask for removal', 'Export before removal where appropriate']],
    ],
  },
  {
    slug: 'ai-transparency', title: 'AI transparency', group: 'Trust',
    summary: 'That CHRONUS is an AI, how it answers, and its limits.',
    laws: ['EU AI Act Article 50 (transparency for AI systems and synthetic content)', 'UK ICO guidance on AI and data protection'],
    sections: [
      ['You are talking to an AI', ['Stated on every chat, and in every model’s About panel']],
      ['How answers are made', ['Search of the person’s own memories, threshold for “I don’t know”', 'AI language model that rephrases and cites; verbatim quotes mode', '“In their spirit” answers: inferred, labelled', 'Style models: trained only on that person’s answers, used only after passing an exam']],
      ['Limits', ['Can be wrong or out of date', 'Knows only what was uploaded or answered', 'Not the person, and not a substitute for grief support']],
      ['Synthetic voice', ['All spoken answers are generated audio, labelled as such']],
    ],
  },
  {
    slug: 'refunds', title: 'Refunds and cancellation', group: 'Payments',
    summary: 'Cooling-off rights and refunds for one-time and hosting payments.',
    laws: ['UK Consumer Contracts Regulations 2013', 'EU Consumer Rights Directive', 'Indian Consumer Protection (E-Commerce) Rules 2020'],
    sections: [
      ['14-day cancellation', ['When it applies to digital services', 'Asking customers to agree that work starts at once, and the effect on refunds']],
      ['Refunds', ['Before a model is built; after it is built', 'Guided (Legacy) sessions already delivered']],
      ['Hosting fee', ['Renewal reminders before charging', 'Cancelling renewal; archive and export after']],
    ],
  },
  {
    slug: 'service-providers', title: 'Service providers (sub-processors)', group: 'Your data',
    summary: 'Companies that process data on CHRONUS’s behalf.',
    laws: GDPR,
    sections: [
      ['Current providers', ['AI language model provider: [OpenRouter], what is sent (question and evidence excerpts), region', 'Voice cloning: [Fish Audio], what is sent (voice recording, text to speak), region', 'Hosting: [to be decided]']],
      ['Safeguards', ['Data processing agreements with each', 'Transfer safeguards for each country']],
      ['Changes', ['How we announce a new provider before using it']],
    ],
  },
  {
    slug: 'data-retention', title: 'Data retention and deletion', group: 'Your data',
    summary: 'How long each kind of data is kept.',
    laws: GDPR,
    sections: [
      ['Models', ['Kept while the account and hosting are active', 'Archived (not deleted) if hosting lapses; for how long', 'Deleted in full on request: memories, files, voice, logs, feedback']],
      ['Logs', ['Question-and-answer logs and audit logs: retention period, then deleted automatically']],
      ['Forms', ['Waitlist: until launch or until you leave it', 'Contact messages: [period]', 'Reports: as long as needed to handle them, then [period]']],
      ['Backups', ['How long deleted data can remain in backups']],
    ],
  },
  {
    slug: 'accessibility', title: 'Accessibility statement', group: 'Trust',
    summary: 'How accessible the site is, and how to tell us when it isn’t.',
    laws: ['UK Equality Act 2010', 'European Accessibility Act', 'Indian Rights of Persons with Disabilities Act 2016'],
    sections: [
      ['Standard', ['Aim: WCAG 2.2 level AA']],
      ['What works', ['Keyboard navigation, screen reader labels, reduced motion, light and dark themes']],
      ['Known gaps', ['[List after an accessibility audit]']],
      ['Contact', ['How to report a barrier, and response time']],
    ],
  },
  {
    slug: 'security', title: 'Security and responsible disclosure', group: 'Trust',
    summary: 'How CHRONUS protects data, and how to report a vulnerability.',
    laws: ['UK GDPR and EU GDPR (security of processing, breach notification)', 'India DPDP Act 2023 (breach notification)'],
    sections: [
      ['Protections', ['Encryption in transit; encrypted backups', 'Owner-only files on the server; sessions that expire', 'Rate limits and cross-site protection']],
      ['Breaches', ['Notifying regulators and affected people within legal deadlines']],
      ['Reporting a vulnerability', ['Contact address and security.txt', 'Safe-harbour terms for good-faith research', 'What not to do (no accessing others’ data)']],
    ],
  },
  {
    slug: 'content', title: 'Content and copyright', group: 'Core',
    summary: 'Who owns what is uploaded, and the pretrained figures’ sources.',
    laws: ['UK Copyright, Designs and Patents Act 1988', 'EU copyright law', 'Indian Copyright Act 1957'],
    sections: [
      ['Your uploads', ['You keep your rights; our licence only to run the service', 'You confirm you may upload letters and recordings, including others’']],
      ['Pretrained figures', ['Built from public-domain texts and public records; sources listed on each model', 'Copyright complaints and how we respond']],
      ['Answers', ['Who owns AI-generated answers and quote cards']],
    ],
  },
  {
    slug: 'company', title: 'Company information', group: 'Core',
    summary: 'The legal details a company must show on its website.',
    laws: ['UK Companies Act 2006 and trading disclosure regulations', 'EU E-Commerce Directive', 'Indian IT Rules (grievance officer)'],
    sections: [
      ['Company', ['[Company name] Ltd, registered in [England and Wales], number [Company number]', 'Registered office: [address]']],
      ['Contact', ['General: [hello@yourdomain]', 'Privacy: [privacy@yourdomain]', 'India grievance officer: [name and contact]']],
      ['VAT', ['[VAT number, if registered]']],
    ],
  },
]

export const LEGAL_GROUPS = ['Core', 'Your data', 'Trust', 'Payments']
