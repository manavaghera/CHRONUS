"""
Style pipeline: build one person's training set, train a LoRA adapter on it,
examine it, and put it in use only if it passes (services/style.py).

    python -m lora.pipeline elon_musk             # train the next version, examine, promote if it passes
    python -m lora.pipeline elon_musk --dry-run   # build the dataset and report its size only
    python -m lora.pipeline <id> --auto           # what services/style.py starts in the background

1. Pairs: only their own words, as conversations. Interview and follow-up
   answers they gave themselves (question -> answer), and posts that answer
   another post (Elon's replies and quote tweets: that post -> his reply).
2. Each example looks exactly like a real request: the system prompt the AI
   voice gets (services/natural_mode.py), with their identity profile and
   evidence (their memories closest to the question, never the answer
   itself, nor its identity line), the question as the user turn, their real
   answer as the target. The first Elon adapter was trained on tweets after
   "Share a thought." and drifted off topic and looped (lora/train_lora.py,
   evaluation/results/lora_match.md); training on the shape of real use is
   the fix.
3. Exam: EXAM_SHARE of the pairs are held out. The plain model, the new
   version and the version in use (if any) answer them with the same prompt,
   greedily. Scored on how close each answer is to their real answer
   (cosine) and how often the grounding guard would keep it. The new version
   must gain MIN_GAIN cosine over the plain model, beat the version in use,
   and keep at least as many answers (within KEEP_TOLERANCE).
4. Every run is recorded in adapters/history.json; a pass updates
   adapters/current.json.
"""

from __future__ import annotations

import argparse
import gc
import json
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import pyarrow.dataset  # noqa: E402,F401  (pyarrow after torch crashes silently on Windows)
except ImportError:  # CI's light install has neither pyarrow nor torch: nothing to guard against
    pass

from config import config  # noqa: E402
from services import identity, style, wellbeing  # noqa: E402
from services import personas as ps  # noqa: E402
from services.mix_method import TRANSCRIPT_TYPES, clean_for_display, without_host_questions  # noqa: E402
from services.natural_mode import LOCAL_MAX_TOKENS, _evidence_line, build_system_prompt, strip_citations  # noqa: E402
from services.post_process import scrub  # noqa: E402
from services.profile import profile_context_block  # noqa: E402
from services.provenance import format_source_citation, grounding_score  # noqa: E402

EXAM_SHARE = 0.15
EXAM_MIN, EXAM_MAX = 8, 40
# Examples per run. On a 12 GB laptop GPU one ~1,100-token example takes a
# couple of seconds, so 800 is about half an hour: the first try, 1,500
# examples of ~1,500 tokens in batches of 16, was on course for five hours.
MAX_TRAIN = 800
EVIDENCE = 2            # memories in each training prompt
EVIDENCE_WORDS = 80     # per memory
ANSWER_WORDS = 120      # longer answers are cut at a sentence
# Tokens per example; a longer one is skipped, never truncated, because
# truncation cuts off the answer, the only part that is learned. Training
# prompts leave out the public-record facts (~400 tokens of family and
# wealth that say nothing about how they talk); exam prompts keep them,
# exactly as a real request has them.
MAX_LENGTH = 1536
MIN_GAIN = 0.01
KEEP_TOLERANCE = 0.05
SEED = 42


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _report(persona: dict, **fields) -> None:
    """Update adapters/run.json (read by services/style.py)."""
    path = style.folder(persona) / "run.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    run = style._read(path) or {"started": _now()}
    run.update(fields, updated=_now())
    path.write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")


def _clean_post(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text).replace("&amp;", "&")
    return re.sub(r"\s+", " ", text).strip()


def _cut(text: str, max_words: int) -> str:
    out, words = [], 0
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        n = len(sentence.split())
        if out and words + n > max_words:
            break
        out.append(sentence)
        words += n
    return " ".join(out) if words <= max_words * 1.5 else " ".join(" ".join(out).split()[:max_words])


def pairs_for(collection) -> list[dict]:
    """Their own conversations: [{question, answer, memory_id}], one per answer."""
    pairs = [{**p, "answer": clean_for_display(p["answer"])} for p in style.own_pairs(collection)]
    got = collection.get(where={"source_type": "tweet"}, include=["documents", "metadatas"])
    for doc, meta in zip(got["documents"], got["metadatas"]):
        context, answer = _clean_post(meta.get("context_text", "")), _clean_post(doc)
        if len(context.split()) >= 4 and len(answer.split()) >= 6:
            pairs.append({"question": context, "answer": answer, "memory_id": meta.get("memory_id", "")})
    seen, unique = set(), []
    for pair in pairs:
        key = pair["answer"].lower()
        if key not in seen:
            seen.add(key)
            unique.append({**pair, "answer": _cut(pair["answer"], ANSWER_WORDS)})
    return unique


def build_examples(persona: dict, pairs: list[dict], collection, embedder, with_facts: bool = True) -> list[dict]:
    """Each pair as a real request: system prompt, question, their answer.
    *with_facts*: include the public-record facts (exam: yes; training: no)."""
    who = identity.get(persona, collection, embedder)
    facts = profile_context_block(persona["id"]) if with_facts else ""
    notes = wellbeing.style_for(persona)
    vectors = embedder.encode([p["question"] for p in pairs], normalize_embeddings=True, batch_size=64)
    examples = []
    for start in range(0, len(pairs), 64):
        batch = pairs[start:start + 64]
        raw = collection.query(query_embeddings=vectors[start:start + 64].tolist(), n_results=EVIDENCE + 4,
                               include=["documents", "metadatas", "distances"])
        for pair, docs, metas, dists in zip(batch, raw["documents"], raw["metadatas"], raw["distances"]):
            evidence, texts = [], []
            for doc, meta, dist in zip(docs, metas, dists):
                if meta.get("memory_id") == pair["memory_id"] or pair["answer"][:60].lower() in doc.lower():
                    continue  # never show the model the answer it should give
                text = without_host_questions(doc) if meta.get("source_type") in TRANSCRIPT_TYPES else doc
                text = " ".join(clean_for_display(text).split()[:EVIDENCE_WORDS])
                citation = format_source_citation(meta, doc, dist)["citation"]
                evidence.append(_evidence_line(len(evidence) + 1, text, meta, citation))
                texts.append(text)
                if len(evidence) == EVIDENCE:
                    break
            # Its own identity line would hand the model the answer too
            leak = [line["id"] for line in who.get("lines", []) if line["memory_id"] == pair["memory_id"]]
            profile = "\n\n".join(b for b in (facts, identity.prompt_block({**who, "hidden": who.get("hidden", []) + leak})) if b)
            examples.append({
                "system": build_system_prompt(persona["name"], "\n\n".join(evidence), profile, notes),
                "user": pair["question"],
                "answer": pair["answer"],
                "memory_id": pair["memory_id"],
                "grounding": texts + [profile],
            })
    return examples


def split(examples: list[dict]) -> tuple[list[dict], list[dict]]:
    """(train, exam): the exam questions are never trained on."""
    rows = examples[:]
    random.Random(SEED).shuffle(rows)
    n_exam = max(EXAM_MIN, min(EXAM_MAX, round(len(rows) * EXAM_SHARE)))
    return rows[n_exam:n_exam + MAX_TRAIN], rows[:n_exam]


def train(rows: list[dict], out: Path) -> dict:
    """LoRA on config.LOCAL_BASE_MODEL; the loss covers their answer only."""
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer, DataCollatorForSeq2Seq, Trainer, TrainingArguments

    if not torch.cuda.is_available():
        raise RuntimeError("Training a style adapter needs a GPU")
    torch.manual_seed(SEED)
    tokenizer = AutoTokenizer.from_pretrained(config.LOCAL_BASE_MODEL)

    encoded = []
    for row in rows:
        messages = [{"role": "system", "content": row["system"]}, {"role": "user", "content": row["user"]}]
        prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=True)
        full = tokenizer.apply_chat_template(messages + [{"role": "assistant", "content": row["answer"]}], tokenize=True)
        if len(full) <= MAX_LENGTH:
            encoded.append({"input_ids": full, "attention_mask": [1] * len(full),
                            "labels": [-100] * len(prompt) + full[len(prompt):]})  # learn their words only
    print(f"{len(encoded):,} of {len(rows):,} examples fit in {MAX_LENGTH} tokens", flush=True)

    class Rows(torch.utils.data.Dataset):
        def __len__(self):
            return len(encoded)

        def __getitem__(self, i):
            return encoded[i]

    model = AutoModelForCausalLM.from_pretrained(config.LOCAL_BASE_MODEL, dtype=torch.bfloat16).to("cuda")
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]))
    # Long prompts: batch 1 x 16 accumulation stays inside a 12 GB laptop GPU
    # (spilling into shared memory makes every step many times slower)
    args = TrainingArguments(
        output_dir=str(out / "checkpoints"), per_device_train_batch_size=1, gradient_accumulation_steps=16,
        num_train_epochs=1, learning_rate=2e-4, lr_scheduler_type="cosine", warmup_ratio=0.03, logging_steps=5,
        eval_strategy="no", save_strategy="no", bf16=True, gradient_checkpointing=True, report_to=[],
        dataloader_num_workers=0, remove_unused_columns=False, seed=SEED)
    model.enable_input_require_grads()  # gradient checkpointing with a frozen base

    class AnswerOnly(Trainer):
        """Scores (logits) only where the answer is. Qwen's 152k-word output
        layer over a whole ~1,500-token prompt is over a gigabyte per example:
        it spilled a 12 GB laptop GPU into shared memory and stalled training.
        Batch size 1, so no padding: the answer is the last tokens."""

        def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
            labels = inputs.pop("labels")
            keep = int((labels != -100).sum(dim=1).max()) + 1
            out = model(**inputs, logits_to_keep=keep)
            # logits at the last `keep` positions predict the last keep-1 tokens: the answer
            logits = out.logits[:, :-1, :].float()
            target = labels[:, -(keep - 1):]
            flat = (logits.reshape(-1, logits.size(-1)), target.reshape(-1))
            if num_items_in_batch is not None:  # normalised over the whole accumulated batch
                loss = torch.nn.functional.cross_entropy(*flat, ignore_index=-100, reduction="sum") / num_items_in_batch
            else:
                loss = torch.nn.functional.cross_entropy(*flat, ignore_index=-100)
            return (loss, out) if return_outputs else loss

    started = time.time()
    trainer = AnswerOnly(model=model, args=args, train_dataset=Rows(),
                         data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True, label_pad_token_id=-100))
    result = trainer.train()
    model.save_pretrained(str(out))
    summary = {"base_model": config.LOCAL_BASE_MODEL, "examples": len(encoded), "train_loss": round(result.training_loss, 4),
               "minutes": round((time.time() - started) / 60, 1)}
    (out / "training_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    del trainer, model
    gc.collect()
    torch.cuda.empty_cache()
    return summary


def verdict(summary: dict) -> tuple[bool, str]:
    """Pass or fail, and why, from exam() scores."""
    base, new, cur = summary["base"], summary["candidate"], summary.get("current")
    if new["cosine"] < base["cosine"] + MIN_GAIN:
        return False, f"Sounds no more like them than the plain model ({new['cosine']} vs {base['cosine']})."
    if new["kept"] < base["kept"] - KEEP_TOLERANCE:
        return False, f"Less faithful to their words: kept {new['kept']:.0%} vs {base['kept']:.0%}."
    if cur and new["cosine"] < cur["cosine"]:
        return False, f"No better than the version in use ({new['cosine']} vs {cur['cosine']})."
    return True, f"Closer to their real answers ({new['cosine']} vs {base['cosine']}) and as faithful."


def exam(rows: list[dict], candidate: Path, current: Path | None, embedder) -> dict:
    """Plain model vs new version (vs current) on the held-out questions."""
    from services import local_llm

    variants = {"base": False, "candidate": str(candidate), **({"current": str(current)} if current else {})}
    scores = {name: {"cosine": [], "kept": []} for name in variants}
    samples = []
    for row in rows:
        messages = [{"role": "system", "content": row["system"]}, {"role": "user", "content": row["user"]}]
        real = embedder.encode([row["answer"]], normalize_embeddings=True)[0]
        answers = {}
        for name, adapter in variants.items():
            text, _ = local_llm.generate(messages, LOCAL_MAX_TOKENS, use_adapter=adapter, temperature=0.0)
            text = strip_citations(scrub(text)) or "(empty)"
            scores[name]["cosine"].append(float(embedder.encode([text], normalize_embeddings=True)[0] @ real))
            scores[name]["kept"].append(grounding_score(text, row["grounding"]) >= config.NATURAL_MIN_GROUNDING)
            answers[name] = text[:300]
        if len(samples) < 3:
            samples.append({"question": row["user"][:300], "real": row["answer"][:300], **answers})
    summary = {name: {"cosine": round(sum(s["cosine"]) / len(rows), 3), "kept": round(sum(s["kept"]) / len(rows), 3)}
               for name, s in scores.items()}
    passed, reason = verdict(summary)
    return {"questions": len(rows), "summary": summary, "passed": passed, "reason": reason, "samples": samples}


def next_version(persona: dict) -> int:
    found = [int(p.name[1:]) for p in style.folder(persona).glob("v*") if p.name[1:].isdigit()]
    return max(found, default=0) + 1


def run(persona_id: str, dry_run: bool = False, auto: bool = False) -> dict:
    import chromadb
    from sentence_transformers import SentenceTransformer

    persona = ps.load_persona(persona_id, any_owner=True)
    if persona is None:
        sys.exit(f"No model called '{persona_id}'")
    flags = style.settings(persona)
    if auto and (flags["frozen"] or not flags["learn_style"]):
        sys.exit("Style learning is off or the model is frozen")
    collection = ps.get_collection(chromadb.PersistentClient(path=config.CHROMA_PATH), persona)
    embedder = SentenceTransformer(config.EMBEDDING_MODEL)
    _report(persona, state="running", stage="dataset")
    pairs = pairs_for(collection)
    random.Random(SEED).shuffle(pairs)
    train_pairs, exam_pairs = split(pairs[:MAX_TRAIN + EXAM_MAX])  # only what one run can use
    train_rows = build_examples(persona, train_pairs, collection, embedder, with_facts=False)
    exam_rows = build_examples(persona, exam_pairs, collection, embedder)
    print(f"{persona['name']}: {len(train_rows):,} training examples, {len(exam_rows)} exam questions", flush=True)
    if dry_run:
        _report(persona, state="done", stage="dry run", message=f"{len(train_rows)} examples")
        return {"train": len(train_rows), "exam": len(exam_rows)}
    if len(exam_rows) < EXAM_MIN or len(train_rows) < style.MIN_PAIRS:
        _report(persona, state="failed", message="Not enough of their own answers to train on yet.")
        sys.exit("Not enough data")

    version = next_version(persona)
    out = style.folder(persona) / f"v{version}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "exam.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in exam_rows), encoding="utf-8")
    _report(persona, state="running", stage="training", version=version)
    summary = train(train_rows, out)
    _report(persona, state="running", stage="exam", version=version)
    current = style.current(persona)
    report = exam(exam_rows, out, style.folder(persona) / current["path"] if current else None, embedder)
    (out / "exam.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    entry = {"version": version, "trained_at": _now(), "examples": summary["examples"],
             "minutes": summary["minutes"], "own_words": sum(len(p["answer"].split()) for p in style.own_pairs(collection)),
             "exam": report["summary"], "passed": report["passed"], "reason": report["reason"]}
    history = style.history(persona) + [entry]
    (style.folder(persona) / "history.json").write_text(json.dumps(history, ensure_ascii=False, indent=1), encoding="utf-8")
    if report["passed"]:
        record = {"version": version, "path": f"v{version}", "promoted_at": _now(), "examples": summary["examples"],
                  "exam": report["summary"]}
        (style.folder(persona) / "current.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    _report(persona, state="done", stage="finished", version=version, passed=report["passed"], message=report["reason"])
    print(json.dumps({**entry, "samples": report["samples"]}, ensure_ascii=False, indent=1), flush=True)
    return entry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("persona")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--auto", action="store_true", help="started by services/style.py")
    args = parser.parse_args()
    try:
        run(args.persona, dry_run=args.dry_run, auto=args.auto)
    except SystemExit:
        raise
    except Exception as e:
        persona = ps.load_persona(args.persona, any_owner=True)
        if persona:
            _report(persona, state="failed", message=f"{type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    main()
