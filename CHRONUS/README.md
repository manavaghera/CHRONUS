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
               • distance threshold: nothing close enough → "I don't know" (no LLM call)
               • optional: hybrid BM25 + semantic, cross-encoder rerank, year range
         ──► answer
               • Quotes only (Mix Method): verbatim passages, framed by whose words they are
               • AI voice: an LLM rewrites the persona's own words, cites [n],
                 and is replaced by quotes if it isn't grounded in the evidence
         ──► sources, confidence, grounding score, logged for Insights
```

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

The server binds 127.0.0.1 and only answers to allowed host names. Don't
expose it to a network without an access code.

## What you can do

- **Chat** with any model: AI voice or quotes only, clickable citations, "view
  in context" for every source, answers streamed as they're written.
- **Time travel**: answer only from memories dated within chosen years.
- **Ask in Hindi, Gujarati and more**: translated in and out, with the English
  original and untranslated sources shown (needs the AI voice for that model).
- **Talk by voice**: dictate, or a hands-free conversation mode. Speech is
  transcribed locally with `faster-whisper` if installed, otherwise by the browser.
- **Listen**: custom models in their consented cloned voice; public figures in a
  clearly labelled stand-in voice (Kokoro), never a clone.
- **Roundtable**: ask 2-4 models the same question and let them reply to each other.
- **Create a model**: consent → upload letters/journals (.txt .md .pdf .docx
  .csv .json) → 25-question interview with adaptive follow-ups → build.
  Memorial mode for someone who has died.
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
  voice, Q&A log entries and feedback.

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
```

With `chroma_db/` and the embedding model present, everything runs. On a fresh
clone (and in CI) the tests use a throwaway database and a hash embedder, and
skip the tests marked `corpus` that need Elon's real collection. GitHub Actions
(`.github/workflows/ci.yml`) runs the backend tests, ruff, ESLint and the website build.

## Measuring retrieval

`python -m evaluation.run_eval` writes `evaluation/results/latest.md`. It now
compares plain semantic search, the full pipeline, the pipeline without its
importance bias, hybrid retrieval and BM25. The last run ranked the full
pipeline below plain semantic search, so run it before changing
`CHRONUS_IMPORTANCE_WEIGHT` or `CHRONUS_RETRIEVAL_MODE` defaults.
