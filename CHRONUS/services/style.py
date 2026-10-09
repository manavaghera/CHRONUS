"""
Style layer: how a person talks, learned by a small LoRA adapter trained on
their own words (lora/pipeline.py), one per person, used by the local model
(config.LLM_PROVIDER = "local"; services/local_llm.py).

Versions live in the model's folder under adapters/v<N>/, and current.json
names the one in use. A version is used only after passing its exam: on
held-out questions it must sound more like them than the plain model without
being kept less often by the grounding guard. A failed version stays on
record (history.json) but is never used.

Auto-train (personal models only; the pretrained figures are trained from the
command line): when the creator turned "Learn their style" on, the model
isn't frozen, the local model is the AI voice, and there are at least
MIN_PAIRS question-and-answer pairs in their own words with RETRAIN_WORDS new
words since the last run, a background process trains the next version
(python -m lora.pipeline <id>). While it runs, adapters/run.json says how far
it got; nothing about it blocks chatting.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import config
from services import personas as ps
from services.provenance import FIRST_PERSON, voice_of

logger = logging.getLogger("chronus")
ROOT = Path(__file__).resolve().parent.parent
MIN_PAIRS = 40          # their own question-and-answer pairs before a first adapter
MIN_WORDS = 3000        # words in those answers
RETRAIN_WORDS = 2000    # new words of theirs before the next version
STALE_RUN = timedelta(hours=3)  # a run that stopped reporting is treated as dead


def _now() -> datetime:
    return datetime.now(timezone.utc)


def folder(persona: dict) -> Path:
    return ps._folder(persona) / "adapters"


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def current(persona: dict) -> dict | None:
    """The promoted version ({"version", "path", ...}), if its files exist."""
    record = _read(folder(persona) / "current.json")
    if not record or not (folder(persona) / record.get("path", "") / "adapter_config.json").exists():
        return None
    return record


def history(persona: dict) -> list[dict]:
    return _read(folder(persona) / "history.json") or []


def settings(persona: dict) -> dict:
    """The person-model switches (personal models are opt-in; see module docstring)."""
    pretrained = persona.get("kind") == "pretrained"
    return {
        "learn_style": bool(persona.get("learn_style", pretrained)),
        "allow_spirit": bool(persona.get("allow_spirit", pretrained)),
        "frozen": bool(persona.get("frozen", False)),
    }


def adapter_for(persona: dict) -> str | bool:
    """The style adapter folder for this persona's answers, or False."""
    if config.LLM_PROVIDER != "local" or not settings(persona)["learn_style"]:
        return False
    record = current(persona)
    return str(folder(persona) / record["path"]) if record else False


def run_state(persona: dict) -> dict | None:
    """The latest training run (adapters/run.json); a running one that stopped
    reporting for STALE_RUN is reported as failed."""
    run = _read(folder(persona) / "run.json")
    if run and run.get("state") == "running":
        updated = datetime.fromisoformat(run.get("updated", run.get("started")))
        if _now() - updated > STALE_RUN:
            run = {**run, "state": "failed", "message": "The training run stopped without finishing."}
    return run


def own_pairs(collection) -> list[dict]:
    """Interview and follow-up answers they gave themselves: [{question, answer, memory_id}]."""
    got = collection.get(where={"source_type": "interview_protocol"}, include=["documents", "metadatas"])
    pairs = []
    for doc, meta in zip(got["documents"], got["metadatas"]):
        if voice_of(meta) != FIRST_PERSON or " A: " not in doc:
            continue
        question = str(meta.get("question") or meta.get("parent_text") or doc.split(" A: ", 1)[0].split("Q: ", 1)[-1])
        pairs.append({"question": question.strip(), "answer": doc.split(" A: ", 1)[1].strip(),
                      "memory_id": meta.get("memory_id", "")})
    return pairs


def status(persona: dict, collection) -> dict:
    """Everything the model page shows about the style layer."""
    pairs = own_pairs(collection) if persona.get("kind") == "custom" else []
    words = sum(len(p["answer"].split()) for p in pairs)
    record = current(persona)
    last = history(persona)[-1] if history(persona) else None
    since = words - int(last.get("own_words", 0)) if last else words
    flags = settings(persona)
    if persona.get("kind") == "pretrained":
        reason = "Trained from the command line (python -m lora.pipeline)."
    elif flags["frozen"]:
        reason = "Frozen: no more training."
    elif not flags["learn_style"]:
        reason = "Turn on “Learn their style” to train it."
    elif len(pairs) < MIN_PAIRS or words < MIN_WORDS:
        reason = f"Needs {MIN_PAIRS} answers in their own words ({MIN_WORDS:,} words); has {len(pairs)} ({words:,})."
    elif last and since < RETRAIN_WORDS:
        reason = f"Retrains after {RETRAIN_WORDS:,} new words; {max(0, since):,} so far."
    elif config.LLM_PROVIDER != "local":
        reason = "Style adapters work with the on-device model (CHRONUS_LLM_PROVIDER=local)."
    else:
        reason = ""
    return {
        **flags,
        "in_use": bool(adapter_for(persona)),
        "current": record,
        "history": history(persona)[-5:],
        "run": run_state(persona),
        "pairs": len(pairs),
        "own_words": words,
        "min_pairs": MIN_PAIRS,
        "min_words": MIN_WORDS,
        "ready": persona.get("kind") == "custom" and not reason,
        "reason": reason,
    }


def maybe_auto_train(persona: dict, collection) -> bool:
    """Start the next training run in the background if everything allows it."""
    state = status(persona, collection)
    run = state["run"]
    if not state["ready"] or (run and run.get("state") == "running"):
        return False
    start(persona)
    return True


def auto_train_quietly(persona: dict, collection) -> None:
    """maybe_auto_train() after new words arrive; a failure to launch is logged,
    never raised, because the answer that triggered it was saved already."""
    try:
        if maybe_auto_train(persona, collection):
            logger.info(f"Style training started for {persona['id']}")
    except Exception as e:
        logger.error(f"Couldn't start style training for {persona['id']}: {e}")


def start(persona: dict) -> None:
    """Launch `python -m lora.pipeline <id>` as a low-priority background process."""
    out = folder(persona)
    out.mkdir(parents=True, exist_ok=True)
    stamp = _now().isoformat(timespec="seconds")
    (out / "run.json").write_text(json.dumps({"state": "running", "stage": "starting", "started": stamp,
                                              "updated": stamp}), encoding="utf-8")
    flags = 0
    if os.name == "nt":  # below-normal priority, no console window
        flags = subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW
    with (out / "run.log").open("w", encoding="utf-8") as log:
        subprocess.Popen([sys.executable, "-m", "lora.pipeline", persona["id"], "--auto"], cwd=str(ROOT),
                         stdout=log, stderr=subprocess.STDOUT, creationflags=flags,
                         start_new_session=os.name != "nt")
