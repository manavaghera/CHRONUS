# CHRONUS Uncertainty Fallback (Documentation)

> **Reference documentation only.** The fallback behavior described here is
> **hardcoded** in `CHRONUS/api_server.py` (`retrieve()` + `POST /chat`).
> This file documents when it fires and what the exact message is.

## When it fires

The uncertainty fallback is the **true no-evidence path** (BUG 3 FIX):

1. `retrieve(query, n)` fetches `n * 4` candidates from ChromaDB.
2. **FILTER FIRST (BUG 8 FIX):** keep only memories whose *raw cosine
   distance* passes the threshold — `dist <= DISTANCE_THRESHOLD` (`1.45`
   from `config.DISTANCE_THRESHOLD`).
3. Survivors are re-ranked by *adjusted* distance
   (`dist - importance_score * IMPORTANCE_WEIGHT`, `0.15` from config) and
   the top-n are returned.
4. If **zero** memories passed the threshold, `retrieve()` returns `None`.

When `retrieve()` returns `None`, `/chat` responds **without calling the
LLM at all** — no prompt, no generation, no chance of hallucination.

## The exact fallback response

```
I don't have any documented information about that in my available records.
```

Returned as a `ChatResponse` with:

```json
{
  "answer": "I don't have any documented information about that in my available records.",
  "sources": [],
  "faithfulness": 0.0,
  "auto_trained": false,
  "confidence": "low",
  "fallback": true
}
```

## Why not just prompt the LLM to say "I don't know"?

An instruction inside the prompt ("never fabricate") still hands the model
retrieved text as context. If retrieval returned garbage (all memories above
the distance threshold), the model can still hallucinate plausible-sounding
answers. Bypassing generation entirely guarantees zero fabricated claims.

## Related behavior

- **Auto-training is disabled** (BUG 1 FIX, memory poisoning): LLM answers
  are never written back into ChromaDB.
- The in-prompt instruction `"Honestly, I haven't publicly talked about
  that."` (in `system_base.md`) remains as a second line of defense for the
  case where memories exist but don't cover the specific question.
