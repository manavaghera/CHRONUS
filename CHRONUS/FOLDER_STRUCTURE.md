# CHRONUS Folder Structure

This directory follows a data-pipeline layout (00→07), not the paper's layered architecture.

## Directory Map

```
00-Project/          # Project documentation (currently empty)
01-Raw-Data/         # Original source files (PDFs, transcripts, tweets)
02-Cleaned-Data/     # Processed and normalized data
03-Identity-Card/    # Persona personality profiles (legacy location)
04-Memory-Units/     # Chunked memory units (JSONL) before embedding
05-Prompts/          # Prompt documentation (reference only, not loaded at runtime)
06-Testing/          # Scripts: embedding, CLI chat, testing utilities
07-Voice/            # Voice synthesis (reference audio, output)
```

## Code Directories

```
services/            # Shared service modules (theme_classifier, mix_method, etc.)
data/                # Interview protocol definition
models/              # Per-persona files (identity_card, signature_phrases, interview_responses)
config.py            # Centralized configuration
api_server.py        # FastAPI server (main entry point)
merge_sources.py     # Data ingestion pipeline
```

## Mapping to Paper Architecture

| Folder | Paper Layer |
|--------|-------------|
| 01-Raw-Data + merge_sources.py | Layer 1: Input Data |
| 02-Cleaned-Data | Layer 2: Data Processing |
| 04-Memory-Units + 06-Testing/embed_elon.py | Layer 3: Memory Representation |
| services/retrieval (in api_server) | Layer 4: Retrieval |
| data/interview_protocol + models/*/interview_responses | Layer 5: Persona/Context |
| services/mix_method | Layer 6: Response Generation |
| services/voice_engine | Layer 7: Voice Synthesis |

## Data Flow

```
01-Raw-Data/ → merge_sources.py → 02-Cleaned-Data/ → 04-Memory-Units/
    → 06-Testing/embed_elon.py → chroma_db/
    → 06-Testing/embed_interview.py → chroma_db/ (interview responses)
    → api_server.py → Mix Method response → UI
```
