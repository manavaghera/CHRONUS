# How CHRONUS is designed

CHRONUS answers as a real person, so the hard part isn't generating text. It's making sure every
answer is true to what they actually said. These notes cover the main problems and how they were
solved. They describe decisions, not code; the source is private.

---

## 1. Never put words in someone's mouth

**Problem.** A language model will happily invent a convincing quote.

**Approach.**
- Every answer is built from retrieved memories: what the person said or wrote.
- There are two answer modes. *Quotes only* uses their exact sentences. *AI voice* rewrites their
  words with citations, is checked against the evidence, and falls back to quotes when it isn't
  grounded.
- Every memory is labelled as their **own words**, **written by others** (a biography, a family
  member's answer) or **synthesized**. Text written about someone is never presented as their quote.
- Each model has its own calibrated "I don't know" threshold. When nothing in the archive is close
  enough, CHRONUS says so, and no AI model is called at all.

**Result.** On a 115-question release check with Elon Musk's archive, 97.5% of the questions it
can't answer get "I don't know", and 75% of the ones it can answer are answered. That's a deliberate
choice: an honest gap is better than a confident invention.

## 2. Finding the right memory

- Sentence embeddings (Sentence-BERT, MiniLM) in ChromaDB, one collection per person.
- Near-duplicate passages are dropped. An "importance" bonus is bounded so it can never outrank
  relevance.
- Optional hybrid search (BM25 + semantic) and a cross-encoder re-ranker. The re-ranker is never
  allowed to rank out the person's own words.
- **Time travel:** answer only from memories dated within chosen years.
- An evaluation harness measures retrieval and answer quality. It runs before any default changes,
  so improvements are measured, not guessed.

## 3. Real-world sources are messy

- **Interviews:** speakers are labelled, so an interviewer's words are never quoted as the guest's.
  Filler words and transcript errors are cleaned up, and closing phrases are only ones the person
  really used.
- **Uploads:** letters, journals, PDFs, Word files, voice notes (transcribed on the server), and
  WhatsApp or email exports, where only the chosen person's messages are kept. Uploads are checked
  against their real file type, and archives have size limits.
- **A guided interview:** 25 questions across six parts of who someone is, with follow-ups that dig
  into what the documents missed.

## 4. Consent you can verify

- Building a model of a living person needs their consent. Memorial mode covers someone who has died.
- **Spoken voice consent.** Before a voice is cloned, the person reads a one-time code aloud.
  Speech-to-text checks the words, and a speaker-verification model checks it's the same voice as
  the sample. This all happens on CHRONUS's own server before anything reaches the voice provider.
  For someone who has died, a family member reads an estate declaration.
- **Limits, stated honestly:** this can't detect a deepfake of the person reading the code.

## 5. Families, sharing, and what happens after

- **Roles:** viewer, contributor and owner, with one-time invite links. Every action declares the
  role it needs, and anything that doesn't is owner-only (deny by default).
- **Legacy contact:** owners choose who keeps, freezes or deletes a model after they die, with a
  30-day notice period.
- **Keeping the archive alive:** one question a day, time capsules delivered on a chosen date, and a
  life-story book you can print.

## 6. Privacy and wellbeing

- Crisis language is detected by meaning. The model steps out of character and shows helplines.
  Long sessions with personal models get a break reminder.
- "Delete" really deletes: vectors, files, the cloud voice, question logs. People can download
  everything they've added.
- Privacy requests get a reference number and an answer-by date (India's DPDP Act).
- Backups are encrypted. Analytics are cookieless daily counts. One-time link secrets are scrubbed
  from logs and error reports. The website runs under a strict content security policy.

## 7. Learning how someone talks: an honest experiment

CHRONUS can train a small LoRA adapter on an on-device model (Qwen 2.5 7B in 4 bits), using only
the person's own words, so the AI voice sounds more like them.

Each new version must pass an exam before it's used: on held-out questions it has to sound more like
the person without drifting from what they actually said. So far, the adapters sound much more like
the person (style score 0.88 → 0.95), but they drift in meaning: they answer from a nearby memory
instead of the question asked. So the exam keeps them switched off. The gate did exactly its job.

## 8. Running it for real

- **Load:** a queue, then a polite "busy, try again" past 16 answers at once, instead of timeouts.
- **Visibility:** a public status page and uptime alerts.
- **Hosting:** Docker with Caddy for automatic HTTPS. The installable app caches nothing private.
- **CI on every change:** tests (584), lint, a production build, the Docker image, a browser smoke
  test, and a dependency audit that blocks known vulnerabilities.
- **Languages:** questions in Hindi and Gujarati are understood, even when typed in English letters.

---

<sub>© 2026 Manav Aghera. All rights reserved. See <a href="../LICENSE">LICENSE</a>.</sub>
