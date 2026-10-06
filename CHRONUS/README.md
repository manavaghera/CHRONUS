# CHRONUS

A RAG-based AI system that simulates Elon Musk from his verified archive. Every response is grounded in real source material with explicit citations — no fabrication.

## Architecture

```
User Question
      ↓
[1] Embed query (all-MiniLM-L6-v2, 384-dim)
      ↓
[2] ChromaDB retrieves top-5 most relevant memory chunks
      ↓
[3] Build prompt:
    - Identity card (personality profile)
    - Few-shot examples (real Elon quotes)
    - Retrieved memories with source provenance
    - Strict anti-hallucination rules
      ↓
[4] Llama 3 8B (local, via Ollama) generates response
      ↓
[5] Post-processor scrubs AI-tells
      ↓
[6] Return text + source citations to user
```

## What's in here

| Component | Purpose |
|---|---|
| `01-Raw-Data/` | Source archives: 14 interview transcripts, books, tweets, OSINT |
| `02-Cleaned-Data/` | Cleaned, normalized text files |
| `04-Memory-Units/` | 13,133 chunked sentences for embedding |
| `03-Identity-Card/` | Auto-generated personality profile |
| `06-Testing/` | Chat pipeline, API server, few-shots, post-processor |
| `../FRONTEND/chronus-app/` | Website (React), served by `api_server.py` |
| `chroma_db/` | Persistent vector store |
| `merge_sources.py` | Data ingestion pipeline |
| `06-Testing/embed_elon.py` | Embedding pipeline (ChromaDB) |

## How to run

```bash
# 1. Install Python dependencies (from CHRONUS/)
pip install -r requirements.txt

# 2. Build the website once (React app in FRONTEND/chronus-app)
npm --prefix ../FRONTEND/chronus-app install
npm --prefix ../FRONTEND/chronus-app run build

# 3. Start the server: API + website on http://localhost:8001
python api_server.py

# Optional: live-reloading website while editing it, on http://localhost:3000
npm --prefix ../FRONTEND/chronus-app run dev

# Tests and evaluation
python -m pytest
python -m evaluation.run_eval
```

The AI voice uses OpenRouter by default (`OPENAI_API_KEY` in `.env`); set
`LLM_PROVIDER` in `config.py` to `"local"` to run everything on this machine.

**Listen button.** Famous models speak in a synthetic Kokoro stand-in voice
(local, labelled "not theirs"); they are never cloned. Custom models can use
their own consented voice through Fish Audio: add `FISH_API_KEY` to `.env`.

**Profile facts.** Questions like "When and where were you born?" are answered
from `models/<id>/profile.json` (Wikidata, public domain), labelled as public
record. Refresh with `python figures/fetch_profiles.py`; hand corrections live
in `figures/profile_overrides.json`.

## Try these questions

1. "Why did you buy Twitter?"
2. "Are you worried about AI?"
3. "What do you think about Mars?"
4. "How do you handle failure?"
5. "Why are you so focused on manufacturing?"
