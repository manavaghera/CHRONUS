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
| `ui/` | Web-based chat interface |
| `chroma_db/` | Persistent vector store |
| `merge_sources.py` | Data ingestion pipeline |
| `06-Testing/embed_elon.py` | Embedding pipeline (ChromaDB) |

## How to run

```bash
# 1. Install Ollama and pull the model
ollama pull llama3:8b-instruct-q4_0

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Start the LLM server
ollama serve

# 4. (In a new terminal) Start the API
python 06-Testing/api_server.py

# 5. (In a new terminal) Start the UI
cd ui && python -m http.server 8080
# Open http://localhost:8080
```

## Try these questions

1. "Why did you buy Twitter?"
2. "Are you worried about AI?"
3. "What do you think about Mars?"
4. "How do you handle failure?"
5. "Why are you so focused on manufacturing?"
