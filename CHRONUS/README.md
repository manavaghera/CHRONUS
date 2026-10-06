# CHRONUS

A consent-first memory archive you can talk to. CHRONUS answers as a person
from their recorded words: interviews, letters, books and an optional guided
interview. Every answer cites its sources, and when the archive has nothing
on a question it says "I don't know" instead of inventing something.

It ships with Elon Musk (public interviews, about 10,000 tweets, two
biographies) and seven public-domain figures (Einstein, Curie, Tesla, Gandhi,
Lincoln, Marcus Aurelius, Shakespeare), and lets you build private models of
people in your own life, with their consent.

## How an answer is made

```
Question ──► crisis check ──► (other language? translate to English)
         ──► profile facts ("When were you born?") answered directly
         ──► retrieve memories      Sentence-BERT (MiniLM) + ChromaDB, per-model collection
               • distance threshold, calibrated per model when it's built:
                 nothing close enough → "I don't know" (no LLM call)
               • near-duplicate passages dropped; importance adds a small bounded bonus
               • optional: hybrid BM25 + semantic, cross-encoder rerank, year range
         ──► answer (short / normal / detailed)
               • Quotes only (Mix Method): the 1-3 sentences of each passage that answer
                 the question, speech fillers and transcript noise removed, framed by
                 whose words they are; closing phrases only ones the person really said
               • AI voice: an LLM rewrites the persona's own words, cites [n],
                 and is replaced by quotes if it isn't grounded in the evidence
         ──► sources, confidence and why, grounding score, logged for Insights
```

Repeated questions are answered from a cache for an hour (any change to a
model's memories clears it).

Every memory is labelled by voice: the person's **own words**, **written by
others** (a biography, a family member's interview answer) or **synthesized**
(generated or reviewed answers). Third-party text is never presented as a quote.

## Run it

```bash
cd CHRONUS
pip install -r requirements.txt          # Python 3.10+
python doctor.py                         # checks your setup and says what's missing
python 06-Testing/embed_elon.py          # once: builds Elon's memory collection (chroma_db/)
python figures/build_figures.py          # once: builds the seven public-domain figures

npm --prefix ../FRONTEND/chronus-app install
npm --prefix ../FRONTEND/chronus-app run build

python run_server.py                     # API + website on http://127.0.0.1:8001
# Windows: start_server.bat   ·   live-reloading website: npm --prefix ../FRONTEND/chronus-app run dev (port 3000)
```

Settings live in `config.py`; override them in `CHRONUS/.env` (see
[`.env.example`](.env.example)). The main ones:

| Variable | What it does |
|---|---|
| `OPENAI_API_KEY` | OpenRouter/OpenAI key for the AI voice. Without it, answers are verbatim quotes. |
| `CHRONUS_LLM_PROVIDER` | `openrouter` (default), `openai`, `ollama`, or `local` (on-device Qwen2.5 + Elon LoRA) |
| `FISH_API_KEY` | Cloned voices for custom models (Fish Audio, opt-in, with consent) |
| `CHRONUS_ACCESS_CODE` / `CHRONUS_USERS` | One shared passcode, or accounts (`asha:code1,ravi:code2`) where each person sees only their own models |
| `CHRONUS_RETRIEVAL_MODE` | `dense` (default) or `hybrid` (semantic + BM25) |
| `CHRONUS_LOG_RETENTION_DAYS` | Questions and feedback are deleted after this many days (default 90, `0` = keep) |
| `CHRONUS_ANSWER_CACHE` | `0` turns off the answer cache |

The server binds 127.0.0.1 and only answers to allowed host names, refuses
cross-site writes, and sends browser security headers (a content security
policy that allows only its own scripts, no framing, nosniff). Uploads are
checked against their real file type. Don't expose it to a network without
an access code.

## What you can do

- **Chat** with any model: AI voice or quotes only, short/normal/detailed
  answers, clickable citations, "view in context" for every source, answers
  streamed as they're written. Each answer says **why** it has its
  confidence (closest match vs the model's threshold, number of sources, how
  many in their own words), and **About this model** shows what it was built
  from, its date range and its consent record.
- **Time travel**: answer only from memories dated within chosen years.
- **Ask in Hindi, Gujarati and more**: translated in and out, with the English
  original and untranslated sources shown (needs the AI voice for that model).
- **Talk by voice**: dictate, or a hands-free conversation mode. Speech is
  transcribed locally with `faster-whisper` if installed, otherwise by the browser.
- **Listen**: custom models in their consented cloned voice; public figures in a
  clearly labelled stand-in voice (Kokoro), never a clone.
- **Roundtable**: ask 2-4 models the same question and let them reply to each other.
- **Create a model**: consent → upload letters/journals (.txt .md .pdf .docx
  .csv .json) or voice notes (transcribed locally when `faster-whisper` is
  installed) → 25-question interview with adaptive follow-ups → build.
  Uploads run in the background with a progress bar and skip passages the
  model already has. Memorial mode for someone who has died.
- **Memory browser**: search what a model knows; edit or delete memories and uploads.
- **Insights**: questions per day, grounding, refusal rate, knowledge gaps
  (what people asked that the archive couldn't answer, with the interview
  question that would fill it) and a **review queue** where approved answers
  become labelled memories.
- **Encrypted backup**: export a custom model as a password-protected
  `.chronus` file and import it on any CHRONUS install.
- **Wellbeing**: crisis language makes the model step out of character and
  show helplines; long sessions with personal models get a break reminder.
- **Delete means delete**: removing a model removes its vectors, files, cloud
  voice, Q&A log entries and feedback. "Delete my question history" on the
  Insights page removes your questions and feedback at any time.
- **Light and dark**: follows the system, or pick one in the header. Keyboard
  and screen-reader friendly (skip link, focus-trapped dialogs, new answers
  announced once).

## Layout

| Path | What's there |
|---|---|
| `api_server.py` | FastAPI app: `/chat`, `/chat/stream`, voice, interview; mounts the routers below and the website |
| `services/` | Retrieval helpers, Mix Method, natural mode, provenance, personas, memories, timeline, insights, roundtable, translation, speech, bundles, access control, wellbeing |
| `models/` | Pretrained personas (`persona.json`, profiles) |
| `personas/` | Your custom models (git-ignored: private data) |
| `01-Raw-Data/`, `02-Cleaned-Data/`, `merge_sources.py` | Source archives and the cleaning/merging pipeline |
| `04-Memory-Units/` | Elon's 16,631 chunked memories (pipeline output) |
| `06-Testing/` | Embedding and data-preparation scripts |
| `evaluation/` | `python -m evaluation.run_eval`: retrieval, match test, "I don't know" calibration |
| `figures/`, `lora/` | Public-domain figure builder; LoRA training for the local model |
| `../FRONTEND/chronus-app/` | React website (Vite) |

## Tests and CI

```bash
python -m pytest          # from CHRONUS/
ruff check .
npm --prefix ../FRONTEND/chronus-app run lint
npm --prefix ../FRONTEND/chronus-app test     # website unit tests (Vitest)
```

With `chroma_db/` and the embedding model present, everything runs. On a fresh
clone (and in CI) the tests use a throwaway database and a hash embedder, and
skip the tests marked `corpus` that need Elon's real collection.

`tests/test_browser_smoke.py` drives the built website in Chromium (every
page, chat → sources → source viewer, theme). It runs when the site is built
and Playwright is installed (`pip install playwright && python -m playwright
install chromium`), and is skipped otherwise.

GitHub Actions (`.github/workflows/ci.yml`) runs the backend tests and ruff,
the website's ESLint, unit tests and build, and the browser smoke test.

## Measuring retrieval

`python -m evaluation.run_eval` writes `evaluation/results/latest.md`. It
compares plain semantic search, the full pipeline, the pipeline without its
importance bias, hybrid retrieval and BM25. An earlier run ranked the full
pipeline below plain semantic search; the importance bonus is now bounded
(at most 0.08 of distance, `CHRONUS_IMPORTANCE_WEIGHT`), so re-run it to
check, and before changing `CHRONUS_IMPORTANCE_WEIGHT` or
`CHRONUS_RETRIEVAL_MODE` defaults.

Answer-quality data, rebuilt with:
- `python -m evaluation.verify_signatures`: keeps only the closing phrases
  Elon really said (`signature_phrases_verified` in his identity card).
- `python -m evaluation.build_word_fixes`: the transcript word repairs used
  when quoting (`services/data/word_fixes.json`; needs `wordfreq`).
