"""
Who is speaking, in interview transcripts that don't say (used by rebuild_elon.py).

Nine of Elon's eleven transcripts name no speakers, so the interviewer's
questions and remarks were kept as his memories. A language model labels
each sentence E (Elon Musk) or O (anyone else). The labels are cached in
data/speaker_labels.json, so a rebuild needs no model and gives the same
memories every time.

    python speaker_labels.py --validate   # accuracy on TED and Don Lemon, whose transcripts name their speakers
    python speaker_labels.py              # label the others (resumes where it stopped)
    ... --local                           # with the local Ollama model instead

Uses config.OPENAI_* (OpenRouter's free models allow 50 requests a day,
BATCH sentences each), or with --local config.LLM_MODEL on this computer.
rebuild_elon.py only uses labels from a model whose --validate run passed
(TRUSTED): llama3 8B (--local) scored 65% on TED in Oct 2026, no better
than calling every line Elon's, so its labels are never used. Accuracy is measured, not assumed: the
memories it keeps are marked speaker_inferred, and the website says so.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

import requests

import elon_sources as es

LABELS_PATH = Path(__file__).resolve().parent / "data" / "speaker_labels.json"
BATCH = 250
CONTEXT = 6  # labelled sentences from the previous batch, shown for continuity
LABELLED = ("TED Tesla fract.txt", "Don Lemon.txt")  # transcripts that name their speakers
LOCAL_BATCH = 60  # --local: llama3 8B reads only 8K tokens at a time
# A model's labels are used only if, on both validation transcripts, this share of
# the lines it calls Elon's really are his, and it is right this often overall
TRUSTED = {"kept_that_are_elon": 0.9, "accuracy": 0.85}
_local = False  # --local: Ollama (config.LLM_MODEL) instead of OpenRouter

PROMPT = """This is part of a transcript of an interview or event with Elon Musk. Its speakers are not named.
For each numbered line, say who speaks it: E = Elon Musk, O = anyone else (host, interviewer, audience, other guests).
Use the conversation: questions, introductions and reactions to Elon are usually O; long first-person answers about
Tesla, SpaceX, X, Neuralink, xAI, his companies, family or views are usually E. If a line mixes both, pick who says most of it.
Reply with exactly one line per number and nothing else, like:
1 O
2 E
"""


def fingerprint(sentences: list[dict]) -> str:
    return hashlib.sha256("\n".join(s["text"] for s in sentences).encode("utf-8")).hexdigest()[:16]


def load() -> dict:
    return json.loads(LABELS_PATH.read_text(encoding="utf-8")) if LABELS_PATH.exists() else {}


def labels_for(name: str, sentences: list[dict]) -> list[str | None] | None:
    """The cached E/O labels for this exact transcript text, or None."""
    entry = load().get(name)
    if not entry or entry.get("fingerprint") != fingerprint(sentences):
        return None
    return [c if c in "EO" else None for c in entry["labels"]]


def trusted_labels(name: str, sentences: list[dict]) -> list[str | None] | None:
    """labels_for, but only from a model that passed --validate (rebuild_elon.py)."""
    labels = labels_for(name, sentences)
    if labels is None:
        return None
    data = load()
    report = data.get(f"validation:{data[name]['model']}") or {}
    passed = len(report) == len(LABELLED) and all(
        all(r.get(k, 0) >= v for k, v in TRUSTED.items()) for r in report.values())
    return labels if passed else None


def model_name() -> str:
    from config import config

    return config.LLM_MODEL if _local else config.OPENAI_MODEL


def _ask(lines: list[str], context: list[tuple[str, str]]) -> list[str | None]:
    from config import config

    before = "".join(f"(earlier, {who}) {text}\n" for text, who in context)
    numbered = "".join(f"{i} {text}\n" for i, text in enumerate(lines, 1))
    payload = {
        "model": config.OPENAI_MODEL,
        "models": [config.OPENAI_MODEL, *config.OPENAI_FALLBACK_MODELS],
        "messages": [{"role": "system", "content": PROMPT},
                     {"role": "user", "content": (f"Just before this part:\n{before}\n" if before else "") + numbered}],
        "temperature": 0, "max_tokens": 8 * len(lines) + 200, "reasoning": {"enabled": False},
    }
    if _local:
        response = requests.post(f"{config.OLLAMA_URL}/api/chat", timeout=900, json={
            "model": config.LLM_MODEL, "messages": payload["messages"], "stream": False,
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": payload["max_tokens"]}})
        response.raise_for_status()
        return _parse(response.json()["message"].get("content") or "", len(lines))
    headers = {"Authorization": f"Bearer {config.OPENAI_API_KEY}", "X-Title": "CHRONUS"}
    for attempt in range(4):
        response = requests.post(f"{config.OPENAI_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=180)
        if response.status_code == 429 and attempt < 3:
            time.sleep(20 * (attempt + 1))
            continue
        response.raise_for_status()
        break
    return _parse(response.json()["choices"][0]["message"].get("content") or "", len(lines))


def _parse(reply: str, count: int) -> list[str | None]:
    out: list[str | None] = [None] * count
    for number, who in re.findall(r"(?m)^\s*(\d+)\s*[.:)-]?\s*([EO])\b", reply):
        if 1 <= int(number) <= count:
            out[int(number) - 1] = who
    return out


def label(sentences: list[dict], done: list[str | None] | None = None, on_batch=None) -> list[str | None]:
    """E/O for every sentence; batches already labelled in *done* are kept."""
    labels = list(done) if done else [None] * len(sentences)
    batch = LOCAL_BATCH if _local else BATCH
    for start in range(0, len(sentences), batch):
        end = min(start + batch, len(sentences))
        if all(labels[start:end]):
            continue
        context = [(sentences[i]["text"], labels[i]) for i in range(max(0, start - CONTEXT), start) if labels[i]]
        got = _ask([s["text"] for s in sentences[start:end]], context)
        labels[start:end] = [new or old for new, old in zip(got, labels[start:end])]
        if on_batch:
            on_batch(labels)
        if not _local:
            time.sleep(4)  # free models: 20 requests a minute
    return labels


def _save(name: str, sentences: list[dict], labels: list[str | None]) -> None:
    data = load()
    data[name] = {"fingerprint": fingerprint(sentences), "model": model_name(),
                  "labels": "".join(c or "?" for c in labels)}
    LABELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LABELS_PATH.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def validate() -> dict:
    """Label the transcripts that name their speakers, without the names, and compare."""
    report = {}
    for name in LABELLED:
        sentences, _ = es.read_transcript(es.RAW_INTERVIEWS / name)
        truth = ["E" if s["speaker"] == "Elon Musk" else "O" for s in sentences]
        key = f"validate:{model_name()}:{name}"
        got = label(sentences, labels_for(key, sentences), on_batch=lambda labels, k=key, s=sentences: _save(k, s, labels))
        pairs = [(g, t) for g, t in zip(got, truth) if g]
        kept = [t for g, t in pairs if g == "E"]
        elon = [g for g, t in pairs if t == "E"]
        report[name] = {
            "sentences": len(sentences), "labelled": len(pairs),
            "accuracy": round(sum(g == t for g, t in pairs) / max(1, len(pairs)), 3),
            # of the sentences it would keep as Elon's, how many really are
            "kept_that_are_elon": round(sum(t == "E" for t in kept) / max(1, len(kept)), 3),
            # of Elon's sentences, how many it keeps
            "elon_kept": round(sum(g == "E" for g in elon) / max(1, len(elon)), 3),
        }
    if all(r["labelled"] >= 0.95 * r["sentences"] for r in report.values()):
        data = load()
        data[f"validation:{model_name()}"] = report  # what trusted_labels checks
        LABELS_PATH.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--validate", action="store_true", help="measure accuracy on the transcripts that name speakers")
    parser.add_argument("--local", action="store_true", help="use the local Ollama model (config.LLM_MODEL) instead of OpenRouter")
    args = parser.parse_args()
    global _local
    _local = args.local
    if args.validate:
        print(json.dumps(validate(), indent=2))
        return
    sources = es.sources()
    for path in sorted(es.RAW_INTERVIEWS.glob("*.txt")):
        if path.name not in sources:
            continue
        sentences, labelled = es.read_transcript(path)
        if labelled:
            continue
        done = labels_for(path.name, sentences)
        if done and all(done):
            print(f"{path.name}: already labelled")
            continue
        print(f"{path.name}: {len(sentences)} sentences", flush=True)
        labels = label(sentences, done, on_batch=lambda labels, n=path.name, s=sentences: _save(n, s, labels))
        print(f"  Elon {labels.count('E')}, others {labels.count('O')}, unlabelled {labels.count(None)}", flush=True)


if __name__ == "__main__":
    main()
