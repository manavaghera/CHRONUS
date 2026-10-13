<div align="center">

<img src="docs/readme/hero.svg" width="100%" alt="CHRONUS: a memory archive you can talk to. Every answer cites its source, and it says “I don't know” when the archive is silent.">

<br>

<img alt="Python 3.12" src="https://img.shields.io/badge/python-3.12-FF6436?style=for-the-badge&logo=python&logoColor=white&labelColor=1a0d08">
<img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-server-FF6436?style=for-the-badge&logo=fastapi&logoColor=white&labelColor=1a0d08">
<img alt="React 18" src="https://img.shields.io/badge/React-18-FF6436?style=for-the-badge&logo=react&logoColor=white&labelColor=1a0d08">
<img alt="ChromaDB" src="https://img.shields.io/badge/ChromaDB-memories-FF6436?style=for-the-badge&labelColor=1a0d08">
<img alt="PyTorch 2.14" src="https://img.shields.io/badge/PyTorch-2.14-FF6436?style=for-the-badge&logo=pytorch&logoColor=white&labelColor=1a0d08">
<img alt="584 tests" src="https://img.shields.io/badge/tests-584-FF6436?style=for-the-badge&labelColor=1a0d08">

### Talk to the people who shaped you, in their own words.

Every answer is built from what they really said or wrote and cites where it came from.<br>
When the archive has nothing on a question, CHRONUS says **“I don't know”** instead of making something up.

[**See it**](#see-it-in-action) · [**How it works**](#how-an-answer-is-made) · [**Features**](#what-you-can-do) · [**Responsible by design**](#responsible-by-design) · [**Under the hood**](#under-the-hood) · [**Design notes**](docs/DESIGN.md)

</div>

> [!NOTE]
> **This repository is a showcase.** CHRONUS's source code is private. This page explains what it does
> and how it's built. If you'd like a walkthrough or a look at the code (for example, as part of a job
> application), reach out through my GitHub profile: [**@manavaghera**](https://github.com/manavaghera).

<img src="docs/readme/divider.svg" width="100%" alt="">

## What is CHRONUS?

CHRONUS is a consent-first memory archive you can have a conversation with. Give it a person's
interviews, letters, journals, voice notes or chats, and it answers as them, quoting their own words,
showing every source, and staying honest about what it doesn't know.

It comes with **Elon Musk** (public interviews, about 10,000 tweets, two biographies) and **seven
public-domain figures**: Einstein, Marie Curie, Nikola Tesla, Gandhi, Lincoln, Marcus Aurelius and
Shakespeare. Families can build private models of people in their own lives, with consent, and share
them with each other.

<img src="docs/readme/chat.svg" width="100%" alt="A CHRONUS chat with Mahatma Gandhi: “What does non-violence mean to you?” is answered with a word-for-word quote from Freedom's Battle and its 3 sources, then a question the archive can't answer is met with “I don't have any documented information about that in my available records.”">

<img src="docs/readme/stats.svg" width="100%" alt="CHRONUS in numbers: 8 ready-made models, 16,000+ Elon memories each with a source, 97.5% of unanswerable questions get “I don't know” (75% of answerable ones are answered), 584 automated tests.">

## See it in action

<p align="center">
  <img src="docs/screenshots/chat.png" width="100%" alt="Chatting with Mahatma Gandhi in Quotes-only mode: the answer quotes Freedom's Battle, says high confidence, and the sources panel shows three cited passages, each in his own words with its match score and a View in context link.">
  <br><sub>A real answer: word-for-word quotes, high confidence, and every source one click away.</sub>
</p>

<table>
<tr>
<td width="50%"><img src="docs/screenshots/home.png" alt="The CHRONUS home page: “Preserve a person. Talk with them in their own words.”"><br><sub>The home page</sub></td>
<td width="50%"><img src="docs/screenshots/figures.png" alt="The pretrained models page, with a timeline of who was alive in a given year."><br><sub>Eight ready-made models, with a “who was alive in…” timeline</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/how-it-works.png" alt="How it works: six steps, consent comes first."><br><sub>How it works: consent comes first</sub></td>
<td><img src="docs/screenshots/try.png" alt="The try page: ask someone from history, no account needed."><br><sub>Try it without an account</sub></td>
</tr>
</table>

<details>
<summary><b>On a phone</b></summary>
<br>
<p align="center"><img src="docs/screenshots/phone-chat.png" width="320" alt="CHRONUS on a phone: Marie Curie answers with a quote from her book Pierre Curie, with its sources below."></p>
</details>

## How an answer is made

<img src="docs/readme/pipeline.svg" width="100%" alt="Question, then crisis check and translation, then memory search. If nothing is close enough the answer is “I don't know” with no AI call; otherwise the answer is quotes or an AI voice, with sources and confidence.">

1. **Crisis check first.** Crisis language makes the model step out of character and show helplines.
2. **Any language in.** Hindi and Gujarati (even typed in English letters) are understood, and the answer comes back in the same language.
3. **Find the memories.** Semantic search over everything the person said or wrote, with optional keyword search and re-ranking.
4. **Close enough?** Each model has its own calibrated threshold. Below it, the answer is “I don't know”, and no AI is called at all.
5. **Answer.** *Quotes only* uses their exact sentences. The *AI voice* rewrites their words with citations, and falls back to quotes if it isn't grounded in the evidence.
6. **Show the work.** Sources, a confidence that explains itself, and “view in context” for every quote.

<img src="docs/readme/divider.svg" width="100%" alt="">

## What you can do

<table>
<tr>
<td width="33%" valign="top"><h4>💬 Cited answers</h4>Every reply links to its sources, with “view in context” and a confidence that says why.</td>
<td width="33%" valign="top"><h4>🎚️ Quotes or AI voice</h4>Word-for-word quotes, or an AI voice that rewrites their words and falls back to quotes if it drifts.</td>
<td width="33%" valign="top"><h4>🕰️ Time travel</h4>Answer only from memories dated within the years you choose.</td>
</tr>
<tr>
<td valign="top"><h4>🌏 Hindi · Gujarati · Hinglish</h4>Ask in your language, even typed in English letters.</td>
<td valign="top"><h4>🎙️ Voice and calls</h4>Dictate, listen, or go hands-free on the call screen.</td>
<td valign="top"><h4>🎭 Roundtable</h4>Ask 2–4 models the same question and let them reply to each other.</td>
</tr>
<tr>
<td valign="top"><h4>🧬 Build a model</h4>Consent, then letters, journals, PDFs, voice notes, WhatsApp or email exports, and a 25-question interview with follow-ups.</td>
<td valign="top"><h4>📅 A question a day</h4>A gentle prompt, in the app or by email, that grows the archive one answer at a time.</td>
<td valign="top"><h4>⏳ Time capsules</h4>Write a message today; it's delivered on the date you pick.</td>
</tr>
<tr>
<td valign="top"><h4>📖 Life-story book</h4>Turn a model's memories into a book you can print or save as a PDF.</td>
<td valign="top"><h4>👪 Family sharing</h4>Viewer, contributor and owner roles, with one-time invite links.</td>
<td valign="top"><h4>📲 Installable app</h4>Add it to your phone's home screen. Nothing private is cached on the device.</td>
</tr>
<tr>
<td valign="top"><h4>📊 Insights</h4>What people asked, what the archive couldn't answer, and the interview question that would fill the gap.</td>
<td valign="top"><h4>🔐 Encrypted export</h4>Save a model as a password-protected file and import it on another CHRONUS install.</td>
<td valign="top"><h4>🚪 Try it first</h4>Anyone can talk to the public figures without an account.</td>
</tr>
</table>

## Responsible by design

> [!IMPORTANT]
> A model of a real person is a serious thing. CHRONUS is built so it can't quietly put words in anyone's mouth.

- **Consent before anything.** A model of a living person needs their consent. Memorial mode covers someone who has died.
- **Spoken voice consent.** Before a voice is cloned, the person reads a one-time code aloud. CHRONUS checks the words and that it's the same speaker as the sample, on its own server, before anything goes to the voice service.
- **Never a fake quote.** Every memory is labelled as their **own words**, **written by others** or **synthesized**. Someone else's text is never presented as their quote.
- **Honest limits.** Below each model's threshold it says “I don't know” without calling an AI.
- **Stand-in voices for public figures.** Clearly labelled, never a clone.
- **Wellbeing.** Crisis language steps out of character and shows helplines. Long sessions get a break reminder.
- **Family roles and a legacy contact.** Sharing is deny-by-default. Owners choose who keeps, freezes or deletes a model after they die.
- **Your data is yours.** Download everything, delete your account, and “delete” really deletes. Privacy requests follow India's DPDP Act.

<img src="docs/readme/divider.svg" width="100%" alt="">

## Under the hood

```mermaid
flowchart LR
  subgraph client["Browser or phone"]
    web["React + Vite website<br/>installable app"]
  end
  subgraph server["FastAPI server"]
    ans["Answering<br/>crisis check · translation · cache"]
    ret["Retrieval<br/>semantic · keyword · re-ranker"]
    speech["Speech<br/>speech-to-text · voice-consent check"]
    state[("SQLite<br/>accounts · sessions · invites")]
    sched["Scheduler<br/>time capsules · daily question"]
  end
  chroma[("ChromaDB<br/>one collection per model")]
  llm{{"AI voice<br/>cloud models or on-device Qwen 2.5"}}
  tts{{"Voices<br/>stand-ins · consented clones"}}
  web <--> ans
  web <--> speech
  ans --> ret --> chroma
  ans --> llm
  ans --> tts
  ans --- state
  sched --- state
  classDef hot fill:#FF6436,stroke:#CF3D10,color:#1d0a04
  classDef dim fill:#140c08,stroke:#FF6436,color:#FFF3EC
  class ans,ret hot
  class web,speech,state,sched,chroma,llm,tts dim
```

| Layer | Built with |
|---|---|
| Website and app | React 18, Vite, an installable web app, English · Hindi · Gujarati |
| Server | Python 3.12, FastAPI, SQLite |
| Memory search | Sentence-BERT (MiniLM), ChromaDB, BM25, a cross-encoder re-ranker |
| AI voice | OpenRouter, OpenAI or Ollama, or on-device Qwen 2.5 7B (4-bit) with LoRA style adapters |
| Speech and voice | faster-whisper, a speaker-verification model (ONNX), Kokoro, Fish Audio |
| Quality and operations | pytest, Vitest, Playwright, GitHub Actions, pip-audit, Docker, Caddy, Sentry |

**Quality:** 584 automated tests, a 115-question release check on real questions, a load test, and
CI that blocks on failing tests and known-vulnerable dependencies.

**Want the details?** [**docs/DESIGN.md**](docs/DESIGN.md) walks through the hard problems: never
inventing a quote, calibrating “I don't know”, verifying spoken consent, family roles, and an honest
experiment in learning someone's speaking style.

## Built by

<table>
<tr>
<td><a href="https://github.com/manavaghera"><img src="https://github.com/manavaghera.png" width="72" alt="Manav Aghera"></a></td>
<td><b>Manav Aghera</b><br>Computer Science &amp; Engineering, Parul University, Vadodara<br><a href="https://github.com/manavaghera">github.com/manavaghera</a></td>
</tr>
</table>

<img src="docs/readme/divider.svg" width="100%" alt="">

<div align="center">
<sub>© 2026 Manav Aghera. All rights reserved. This repository is for viewing only; see <a href="LICENSE">LICENSE</a>.</sub><br>
<sub>Built for the voices we don't want to lose.</sub>
</div>
