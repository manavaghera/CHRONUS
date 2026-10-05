# CHRONUS — Week-by-Week Implementation Roadmap

> **Project:** CHRONUS DB — A RAG-based AI system that simulates Elon Musk from his verified archive.
> **Current State:** Initial commit (5e1e6f7). Core pipeline built and partially tested (4/6 Phase 6 tests passing). Collection live at 16,345 memory units. 5 known issues documented in `TEST_RESULTS.md`.
> **Architecture:** 7-layer paper model → data-pipeline folder layout (00→07).
> **Key stack:** ChromaDB (cosine), Sentence-BERT all-MiniLM-L6-v2, FastAPI, OpenRouter/Ollama (llama3:8b), XTTS-v2 voice.

---

## Completed Work (Already Delivered)

| Area | Status | Key Files |
|---|---|---|
| Data ingestion & cleaning | ✅ Done | `merge_sources.py`, `01-Raw-Data/`, `02-Cleaned-Data/`, `04-Memory-Units/` |
| Embedding pipeline | ✅ Done | `06-Testing/embed_elon.py` (non-destructive, idempotent) |
| ChromaDB vector store | ✅ Done | `chroma_db/` — 16,345 vectors |
| Identity card | ✅ Done | `models/elon_musk/identity_card.json` (130-line structured profile) |
| Interview protocol | ✅ Done | `data/interview_protocol.py` (25 Qs, 6 dimensions) |
| Interview responses | ✅ Done | `models/elon_musk/interview_responses.json` (Q1–Q25, high confidence) |
| Theme classifier | ✅ Done | `services/theme_classifier.py` (7 themes, 7/7 correct) |
| Mix Method generator | ✅ Done | `services/mix_method.py` (3-part deterministic pipeline) |
| API server | ✅ Done | `api_server.py` (FastAPI, `/chat`, `/health`, `/speak`, `/interview/*`) |
| CLI chat | ✅ Done | `06-Testing/chat_elon.py` |
| Web UI | ✅ Done | `ui/index.html` |
| Uncertainty fallback | ✅ Implemented | `api_server.py retrieve()` + `/chat` (BUG 2 & BUG 3 fixes) |
| Post-processor | ✅ Done | `06-Testing/post_process.py` (AI-tell scrubber) |
| Few-shot examples | ✅ Done | `06-Testing/elon_few_shot.py` (7 real-style examples) |
| Personal data KB | ✅ Done | `05-Prompts/personal_data_kb.md`, `harvest_personal_data.py` |
| Voice engine skeleton | ✅ Done | `voice_engine.py` (XTTS-v2, lazy singleton) |
| Test suite | ✅ Done | `06-Testing/_phase6_tests.py` (4/6 PASS) |
| Auto-training | ⚠️ Intentionally disabled | Memory poisoning fix (BUG 1) — `add_to_memory()` kept but commented out |

## Known Issues (From TEST_RESULTS.md)

| # | Issue | Impact |
|---|---|---|
| 1 | `DISTANCE_THRESHOLD = 1.1` still too permissive — uncertainty fallback unreachable for pizza query (matches at dist 0.625–0.686) | Fallback only fires for truly random gibberish |
| 2 | Chunk quality degrades — raw transcript noise (censor artifacts, broken punctuation) leaks into Mix Method Part 2 | Semi-coherent quotes on off-topic queries |
| 3 | `format_source_citation()` omits the `distance` field | Clients can't see provenance match strength |
| 4 | `requirements.txt` incomplete | `pyarrow`, `pydantic`, `uvicorn[standard]` not explicitly pinned |
| 5 | `_phase6_tests.py` not wired to CI | No automated regression on commit |
| 6 | Two identity card locations (`03-Identity-Card/` and `models/elon_musk/`) — one per path is dead | Confusion, redundant maintenance |

---

## Weeks 1–12: Forward-Looking Implementation Plan

### Week 1 — Infrastructure Hardening & Dependency Audit

**Goal:** Make the project reproducible and CI-ready.

| Day | Task | Files | Details |
|-----|------|-------|---------|
| Mon | Audit `requirements.txt` | `requirements.txt` | Cross-reference against all imports across `.py` files. Ensure `pyarrow`, `pydantic`, `uvicorn[standard]`, `chromadb`, `sentence-transformers`, `requests`, `fastapi`, `pyyaml` are pinned with `>=` constraints. Pin exact versions tested against (Python 3.12). |
| Tue | Create `requirements-dev.txt` | `requirements-dev.txt` (new) | Add `pytest`, `pytest-timeout`, `pytest-cov`, `httpx` (for API testing without running a live server). |
| Wed | Set up virtualenv lockfile | `requirements-freeze.txt` (new) | Freeze exact versions from the working `venv/` so CI reproduces the same environment. |
| Thu | Add `pyproject.toml` | `pyproject.toml` (new) | Replace ad-hoc `sys.path` hacks with proper package metadata. Define CHRONUS package root. |
| Fri | Fix import hygiene | All `.py` files | Remove `sys.path.insert(0, ...)` hacks where possible. Replace with `pyproject.toml` package config or a `conftest.py` at root. |
| Sat-Sun | Write a `Makefile` / `run_tests.bat` | `Makefile` + `run_tests.bat` (new) | Convenience targets: `make test`, `make embed`, `make server`, `make cli`. |

**Deliverable:** A fully pinned, reproducible environment. CI can install deps in one step.

### Week 2 — Test Infrastructure & Regression Suite

**Goal:** Convert the ad-hoc `_phase6_tests.py` into a proper pytest suite with CI pipeline.

| Day | Task | Files | Details |
|-----|------|-------|---------|
| Mon | Scaffold pytest structure | `tests/` (new) | Create `tests/conftest.py`, `tests/test_theme.py`, `tests/test_mix_method.py`, `tests/test_api.py`, `tests/test_retrieval.py`. |
| Tue | Port theme classifier tests | `tests/test_theme.py` | Convert the 7-theme classification checks from `_phase6_tests.py` (6.3) into parametrized pytest tests. Run without needing a live server. |
| Wed | Port Mix Method unit tests | `tests/test_mix_method.py` | Use the `__main__` demo block in `mix_method.py` as seed for isolated unit tests — feed mock memories/identity card, assert 3-part structure, confidence labels, source count. |
| Thu | Port retrieval logic tests | `tests/test_retrieval.py` | Test `retrieve()` filter-first logic (BUG 8 fix): given mock distances, verify threshold filtering → importance re-ranking → top-n selection, and that returning `None` when all exceed threshold. |
| Fri | API integration tests | `tests/test_api.py` | Tests for `/health`, `/stats`, `/chat` (natural + mix_method modes), `/interview/complete`, `/basic_info` patterns. Use `httpx.AsyncClient` + `pytest-asyncio` or start server fixture. |
| Sat | Phase 6 regression tests | `tests/test_regression.py` (new) | Port the 6.1–6.6 checks from `_phase6_tests.py` into proper assertions. Mark 6.2 (pizza fallback) as `xfail` until chunk quality is fixed. |
| Sun | GitHub Actions CI | `.github/workflows/ci.yml` (new) | On push/PR: install deps, run `pytest`, report results. Trigger on every commit to `main`. |

**Deliverable:** `pytest` suite that runs in <2 min and a GitHub Actions badge.

### Week 3 — Chunk Quality Pipeline (Fix Known Issue #2)

**Goal:** Clean transcript noise so Mix Method Part 2 doesn't surface garbage.

| Day | Task | Files | Details |
|-----|------|-------|---------|
| Mon | Analyze noise patterns | `04-Memory-Units/elon_musk_memory_units.jsonl` | Sample 100 short chunks. Catalog noise types: `[ ___ ]` censor artifacts, `uh`/`um` runs, broken punctuation, speaker labels, truncated words. |
| Tue | Write chunk pre-filter | `06-Testing/chunk_filter.py` (new) | A `clean_chunk(text)` function that: strips censor artifacts, removes excessive fillers, fixes sentence boundaries, drops chunks < `MIN_CHUNK_CHARS` (50). |
| Wed | Integrate into `merge_sources.py` | `merge_sources.py` | Add a `clean_transcript_text()` step in `process_all_sources()` before chunking. Apply to interview/talk-show sources specifically. |
| Thu | Add quality metadata | `merge_sources.py` | Tag each chunk with `quality_score` (0–1) based on: transcript noise density, sentence completeness, word count. |
| Fri | Re-run merge pipeline | `04-Memory-Units/` | Run `merge_sources.py` → output to a new JSONL. Compare chunk counts and sample quality. Don't overwrite yet. |
| Sat | Re-embed with quality filter | `06-Testing/embed_elon.py` | Add `quality_score >= 0.4` filter in `embed_all()`. Re-upsert only clean chunks. |
| Sun | Validate | `06-Testing/chroma_smoke_test.py` | Re-run smoke test. Verify Mix Method responses for off-topic queries are cleaner. |

**Deliverable:** Cleaner memory units with quality scoring. Mix Method Part 2 output visibly improved.

### Week 4 — Threshold Calibration & Fallback Reachability (Fix #1)

**Goal:** Make the uncertainty fallback actually reachable for out-of-domain queries.

| Day | Task | Files | Details |
|-----|------|-------|---------|
| Mon | Build retrieval diagnostics tool | `06-Testing/_diag_retrieval.py` (new) | For a given query, print raw distances of top-20 candidates, which pass `DISTANCE_THRESHOLD`, and the adjusted ranking. |
| Tue | Run diagnostics on 20 test queries | `_diag_retrieval.py` | Include high-confidence (SpaceX mission), medium (AI risk), low (pizza, quantum computing). Log to `retrieval_audit.jsonl`. |
| Wed | Analyze distribution | `retrieval_audit.jsonl` | Compute CDF of best-match distances per query type. Find the natural knee. |
| Thu | Calibrate threshold | `config.py` | Set `DISTANCE_THRESHOLD` so 95% of covered-domain queries pass, 80% of out-of-domain queries fail. Consider per-theme dynamic threshold. |
| Fri | Add minimum-quality gate | `api_server.py` `retrieve()` | After threshold filter, also filter out chunks with `quality_score < 0.4` (from Week 3). |
| Sat | Re-run Phase 6 tests | `_phase6_tests.py` | Verify 6.1 still passes, 6.2 now triggers fallback (pizza), 6.6 still passes. Update `TEST_RESULTS.md`. |
| Sun | Update confidence boundaries | `services/mix_method.py` | Align `_HIGH_CONFIDENCE_CEIL` / `_MEDIUM_CONFIDENCE_CEIL` with the calibrated threshold. |

**Deliverable:** Uncertainty fallback fires for genuinely out-of-domain queries. `TEST_RESULTS.md` updated.

### Week 5 — Source Provenance Enrichment (Fix #3) & Identity Card Consolidation (Fix #6)

**Goal:** Rich citations and eliminate the duplicate identity card problem.

| Day | Task | Files | Details |
|-----|------|-------|---------|
| Mon | Add distance to citations | `api_server.py` `format_source_citation()` | Add `distance` (raw) and `adjusted_distance` to the returned dict. Also add `memory_id` for traceability. |
| Tue | Add distance to Mix Method sources | `services/mix_method.py` `assemble_response()` | Ensure Mix Method source list also includes distance fields. |
| Wed | Consolidate identity cards | `03-Identity-Card/elon_musk.json` | Migrate `03-Identity-Card/elon_musk.json` → symlink or remove. Update `load_identity_card()` to read from `models/`. |
| Thu | Update identity card generation scripts | `06-Testing/generate_identity_card.py` + `_v2.py` | Update output path to `models/elon_musk/identity_card.json`. Remove v1/v2 duplication. |
| Fri | Add importance_score to Mix Method citation | `services/mix_method.py` | Display importance in source dict for debugging. |
| Sat | UI: display distances | `ui/index.html` | Add a "match strength" indicator (badge color: green <0.5, yellow <1.0, red >1.0) on each source. |
| Sun | E2E verification | Manual | Ask "What is the goal of SpaceX?" via both UI and `/chat?mode=mix_method`. Verify 3 sources each with distance, importance, and citation. |

**Deliverable:** Every source includes `distance`, `importance_score`, and a human-readable citation. No duplicate identity card files.

### Week 6 — API Modernization & OpenRouter Integration

**Goal:** Make the "natural" LLM path production-ready with OpenRouter and graceful degradation.

| Day | Task | Files | Details |
|-----|------|-------|---------|
| Mon | Test OpenRouter connectivity | `config.py`, `.env` | Verify the `OPENAI_API_KEY` in `.env` works against `https://openrouter.ai/api/v1`. Test a small completion via `python -c "..."`. |
| Tue | Refactor `generate_natural_response()` | `api_server.py` | Clean up the partial truncation in `personality_notes` building. Ensure the LLM system prompt includes the identity card's `top_beliefs` as bullet points, not inline. |
| Wed | Add token budgeting | `api_server.py` | Estimate token count of evidence_texts + prompt. If over 70% of context window, trim memories from the bottom. Prevents truncation of the actual question. |
| Thu | Add streaming option (optional) | `api_server.py` | Add `stream: bool` to `ChatRequest`. If True and provider supports it, stream SSE chunks to the UI for a chat-like feel. |
| Fri | Add request logging | `api_server.py` | Log every `/chat` request: query (first 120 chars), mode, response time, token count, confidence, fallback flag. Write to `06-Testing/chat_access.log`. |
| Sat | Add rate limiting | `api_server.py` | Simple in-memory rate limiter: 10 requests/min per IP for `/chat`, 30/min for `/health`. Protects against accidental loops. |
| Sun | Test both modes end-to-end | `_test_natural.py` | Compare `/chat` (natural) vs `/chat?mode=mix_method` for 5 queries. Ensure natural mode degrades to mix_method when OpenRouter returns an error. |

**Deliverable:** The `/chat` endpoint works reliably with both OpenRouter (primary) and local Ollama (fallback). Auto-training remains disabled. Rate-limited and logged.

### Week 7 — Interview Protocol Completion & Structured Data Pipeline

**Goal:** Wire up the full interview-augmentation loop — feed interview responses into the vector store at scale and test them as retrievable memories.

| Day | Task | Files | Details |
|-----|------|-------|---------|
| Mon | Audit current interview embedding | `06-Testing/embed_interview.py` | Verify it's idempotent (uses `upsert`). Check that the 25 responses are already embedded (TEST_RESULTS shows 2 interview sources in test 6.6). |
| Tue | Create interview ingestion CLI | `06-Testing/embed_interview.py` | Add a `--all` flag that reads `models/elon_musk/interview_responses.json` and embeds all 25 Q&As in one pass. Add progress bar and per-question logging. |
| Wed | Add interview metadata enrichment | `services/interview_embedder.py` | Add `sub_dimension` and a `verified_quote` flag (for high-confidence answers) to metadata. This lets the retriever weight verified interview content higher. |
| Thu | Test interview-driven retrieval | `_phase6_tests.py` | Add Test 6.7: ask "How would you describe your core personality?" and verify the response cites interview_protocol sources with Q1's content. |
| Fri | Add multi-persona scaffolding | `data/interview_protocol.py` | Refactor to accept a `person` parameter. Currently hardcoded to `elon_musk`. Prepare for adding Steve Jobs, Peter Thiel, etc. |
| Sat | Create interview answer validation | `06-Testing/validate_interview_responses.py` | Cross-check each interview response against actual source transcripts. Flag any answer whose claims can't be verified in `01-Raw-Data/`. |
| Sun | Document interview pipeline | `05-Prompts/interview_pipeline.md` (new) | Document the flow: protocol → LLM-generated responses → human review → embedding → retrieval. |

**Deliverable:** Full interview-augmentation pipeline. All 25 Q&As embedded as high-importance memories. Multi-persona ready.

### Week 8 — Voice Integration & Media Pipeline

**Goal:** Make the XTTS-v2 voice engine fully functional and accessible via API.

| Day | Task | Files | Details |
|-----|------|-------|---------|
| Mon | Check XTTS availability | `voice_engine.py` | Verify `TTS` package (Coqui) is in venv. Check if reference WAV exists at `07-Voice/reference_elon.wav`. If not, source a clean 30–60s Elon speaking sample (public speech, royalty-free). |
| Tue | Fix the `07-Voice` directory | Create `07-Voice/` | Referenced in config but doesn't exist yet. Create with `reference_elon.wav` and an `output/` subdirectory. |
| Wed | Integrate voice into `/speak` | `api_server.py` | The `/speak` endpoint exists but isn't wired to the voice engine. Connect `SpeakRequest` → `get_voice_engine()` → `synthesize()`. Return the output path. |
| Thu | Add text-to-speech to Mix Method | `services/mix_method.py` | Add optional `synthesize_voice=True` param. When enabled, call voice engine on assembled response, include audio path in output dict. |
| Fri | Test end-to-end voice | Manual | `POST /speak` with a Mix Method response. Listen to output. Adjust XTTS parameters (speed, temperature) to match Elon's cadence. |
| Sat | Add voice status endpoint | `api_server.py` | `/voice/status` already exists (line 840). Verify it correctly reports ready/not-loaded. Add model name and reference audio path. |
| Sun | Document voice workflow | `07-Voice/README.md` (new) | Document how to regenerate the reference speaker, retrain if needed, and the expected audio format (16kHz WAV, 30–60s, clear speech). |

**Deliverable:** `POST /speak` returns a playable WAV file. Voice is optional (falls back to text-only if XTTS/torch not available).

### Week 9 — UI Polish & Feature Parity

**Goal:** The web UI (`ui/index.html`) is a static HTML/CSS/JS file. Make it fully functional and polished.

| Day | Task | Files | Details |
|-----|------|-------|---------|
| Mon | Review current UI | `ui/index.html` | Read the full file (only saw first 50 lines). Catalog what's wired and what's not. |
| Tue | Connect sources display | `ui/index.html` | The `/chat` response includes `sources[]`. Wire the UI to render each source with: citation, distance badge, quote preview toggle. |
| Wed | Add mode toggle | `ui/index.html` | Add a dropdown or toggle to choose "Natural" vs "Mix Method" vs "Auto". Send `mode` field in the POST body. |
| Thu | Add confidence + fallback indicators | `ui/index.html` | Colored badge: green (high), yellow (medium), red (low/fallback). If `fallback=true`, display special message with icon. |
| Fri | Add voice playback | `ui/index.html` | When response includes audio path, render an `<audio>` player. Call `POST /speak` in the background after receiving a text response. |
| Sat | Add loading states | `ui/index.html` | Show typing indicator while request is in flight. Disable input during request. |
| Sun | Add dark/light theme toggle | `ui/index.html` | Currently dark-only. Add a theme toggle that switches CSS variables. Default to system preference. |

**Deliverable:** Fully functional web UI with source display, mode toggle, confidence badges, voice playback, and loading states.

### Week 10 — Documentation & User Guide

**Goal:** Write comprehensive documentation so anyone can set up and run CHRONUS from scratch.

| Day | Task | Files | Details |
|-----|------|-------|---------|
| Mon | Write main README | `README.md` | Rewrite. Cover: what CHRONUS is, architecture diagram (7 layers → folder mapping), prerequisites, step-by-step setup, example Q&A. |
| Tue | Architecture deep-dive | `docs/ARCHITECTURE.md` (new) | The 7-layer paper model in detail. Data flow through retrieval → classification → Mix Method. Code map showing every file and its role. |
| Wed | Configuration reference | `docs/CONFIGURATION.md` (new) | Every field in `config.py` documented with purpose, default, and tuning guidance. Include `DISTANCE_THRESHOLD` calibration guide. |
| Thu | API reference | `docs/API.md` (new) | OpenAPI spec for every endpoint. Include `ChatRequest`/`ChatResponse` schema, curl examples, response examples. |
| Fri | Development guide | `CONTRIBUTING.md` (new) | How to run tests, add a new persona, add a new theme, embed new data, contribute interview questions. Code style conventions. |
| Sat | Data pipeline guide | `docs/DATA_PIPELINE.md` (new) | End-to-end: raw sources → cleaning → chunking → importance scoring → embedding → ChromaDB. How to add new source types. |
| Sun | Quick-start cheat sheet | `docs/CHEATSHEET.md` (new) | Single-page reference: common commands, key files, constants, troubleshooting table. |

**Deliverable:** Complete documentation set. New contributor can spin up CHRONUS in 10 minutes.

### Week 11 — Multi-Persona Expansion Scaffold

**Goal:** Prepare the architecture for adding additional personas beyond Elon Musk.

| Day | Task | Files | Details |
|-----|------|-------|---------|
| Mon | Refactor persona loading | `api_server.py` | Replace hardcoded `load_mix_method_identity_card("elon_musk")` with `load_persona(person="elon_musk")`. Make persona a query parameter on `/chat`. |
| Tue | Generalize theme classifier | `services/theme_classifier.py` | Add a `theme_set` parameter so each persona can define its own themes. Keep Elon themes as default. |
| Wed | Generalize Mix Method | `services/mix_method.py` | Make `_THEME_SIGNATURE_AFFINITY` and `_DEFAULT_SIGNATURES` loadable per-persona from `models/<person>/signature_phrases.txt`. |
| Thu | Add persona metadata file | `models/elon_musk/persona.json` (new) | Store: name, description, language, embedding model override, theme set name, default signature phrases path. |
| Fri | Add multi-persona test | `tests/test_multi_persona.py` | Test that requesting persona="steve_jobs" gracefully degrades. |
| Sat | Document persona scaffolding | `docs/PERSONAS.md` (new) | Step-by-step: to add a new persona, create `models/<person>/`, populate identity card, signature phrases, interview responses, theme set, embed data. |
| Sun | Stub sample persona | `models/steve_jobs/` (skeleton) | Create the directory with placeholder files. Don't populate — just prove the scaffolding works. |

**Deliverable:** Architecture supports multiple personas. Adding a new one is a documented 5-step process.

### Week 12 — Integration Testing & Release Preparation

**Goal:** Full system validation, performance benchmarking, and a clean release tag.

| Day | Task | Files | Details |
|-----|------|-------|---------|
| Mon | Write integration test | `tests/test_integration.py` | End-to-end: embed fresh data → start server → POST 10 diverse queries → verify response structure, sources, confidence. |
| Tue | Performance benchmark | `tests/test_bench.py` | Time: ingestion, single query (retrieve + Mix Method), single query (natural mode). Log to `benchmarks/`. |
| Wed | Memory leak check | `api_server.py` | Verify SentenceTransformer + ChromaDB client aren't recreated per-request. Verify voice engine singleton doesn't leak. |
| Thu | Security audit | `api_server.py`, `config.py` | Confirm `HOST = "127.0.0.1"`. Confirm `.env` is in `.gitignore`. Confirm no API keys in committed code. Run `bandit` if available. |
| Fri | Update TEST_RESULTS.md | `TEST_RESULTS.md` | Document the final test run. Update known issues. |
| Sat | Create release tag | git | `git tag v1.0.0 -m "CHRONUS v1.0"`. Push tag to GitHub. |
| Sun | Write project retrospective | `00-Project/retrospective.md` (new) | 2-page summary: what worked, what was hard, lessons learned, what to build next. |

**Deliverable:** CHRONUS tagged as `v1.0.0`. All tests green (or clearly documented `xfail`). Performance benchmarks recorded.

---

## Quick Reference: How to Run

```bash
# Setup (Week 1 deliverables)
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt

# Data pipeline (Week 3)
python merge_sources.py              # rebuild 04-Memory-Units/
python 06-Testing/embed_elon.py      # upsert into chroma_db/
python 06-Testing/embed_interview.py --all  # embed 25 interview Q&As

# Test (Week 2)
pytest tests/ -v

# Run server (Week 6)
python api_server.py
# Server: http://127.0.0.1:8001 | Docs: http://127.0.0.1:8001/docs

# Chat (Week 9)
# UI:  cd ui && python -m http.server 8080  → http://localhost:8080
# CLI: python chat_cli.py "Why did you buy Twitter?"
# API: curl -X POST http://127.0.0.1:8001/chat \
#   -H "Content-Type: application/json" \
#   -d '{"query":"What is the goal of SpaceX?","mode":"mix_method"}'
```

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ Done | Completed in initial commit |
| 🔄 In progress | Started but needs work |
| ⚠️ Known issue | Documented problem, not yet fixed |
| 🆕 New | Not yet created |








