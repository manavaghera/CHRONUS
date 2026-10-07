"""
Does the LoRA adapter make the clone answer more like Elon? Match test on
all 51 TED questions with that interview held out of memory (as in
evaluation/run_eval.py), comparing on this machine's GPU:

* Mix Method (verbatim quotes, no LLM)
* local base model (Qwen2.5-1.5B-Instruct) answering in his voice
* the same model with the LoRA adapter trained on his tweets and quotes

    python lora/eval_lora.py     -> evaluation/results/lora_match.json + .md

Both LLM variants get the same prompt and evidence and decode greedily
(deterministic). "raw" scores the model's own text; "shown" is what users
see after the grounding guard (invented answers fall back to Mix Method).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evaluation.run_eval import _cosine, _f1, _mean, srv  # noqa: E402  (loads pyarrow before torch)
from evaluation.ted_qa import SOURCE_IN_MEMORY, load_pairs  # noqa: E402
from services.post_process import scrub  # noqa: E402
import services.natural_mode as nm  # noqa: E402
from services import local_llm  # noqa: E402
from services.provenance import anchor_first, format_source_citation  # noqa: E402

RESULTS = ROOT / "evaluation" / "results"


def main() -> None:
    if not local_llm.has_adapter():
        sys.exit("No adapter yet: run python lora/train_lora.py first")
    srv.config.LLM_PROVIDER = "local"
    srv.config.LLM_TEMPERATURE = 0.0  # greedy: comparable, repeatable
    persona = srv.ps.load_persona("elon_musk")
    card = srv.load_mix_method_identity_card("elon_musk")
    profile = srv.profile_context_block("elon_musk")
    held_out = {"source_file": {"$ne": SOURCE_IN_MEMORY}}

    rows, examples = [], []
    for pair in load_pairs():
        mems = srv.retrieve(pair["question"], where=held_out)
        if mems is None:
            continue
        mems = anchor_first(mems)
        evidence = "\n\n".join(nm._evidence_line(i, d, m, format_source_citation(m, d, dist)["citation"])
                               for i, (_, d, m, dist) in enumerate(mems, start=1))
        prompt = nm.build_system_prompt("Elon Musk", evidence, profile, persona.get("style_notes"))
        row = {"id": pair["id"]}
        mix = srv.generate_mix_method_response(pair["question"], mems, card, "Elon Musk")["response"]
        row.update(mix_cos=_cosine(mix, pair["answer"]), mix_f1=_f1(mix, pair["answer"]))
        answers = {}
        for name, adapter in (("base", False), ("lora", True)):
            raw, _ = local_llm.generate([{"role": "system", "content": prompt}, {"role": "user", "content": pair["question"]}],
                                        nm.LOCAL_MAX_TOKENS, use_adapter=adapter, temperature=0.0)
            raw = scrub(raw)
            shown = nm.generate_natural_response(pair["question"], mems, card, profile_block=profile,
                                                 style_notes=persona.get("style_notes"), use_adapter=adapter)
            answers[name] = raw
            row.update({f"{name}_raw_cos": _cosine(raw, pair["answer"]), f"{name}_raw_f1": _f1(raw, pair["answer"]),
                        f"{name}_kept": float(shown["mode"] == "natural"),
                        f"{name}_shown_cos": _cosine(shown["response"], pair["answer"])})
        rows.append(row)
        if len(examples) < 4:
            examples.append({"question": pair["question"][-160:], "real": pair["answer"][:300], **answers})
        print(f"{pair['id']}: base {row['base_raw_cos']:.2f}  lora {row['lora_raw_cos']:.2f}  mix {row['mix_cos']:.2f}", flush=True)

    keys = ["mix_cos", "mix_f1"] + [f"{n}_{k}" for n in ("base", "lora") for k in ("raw_cos", "raw_f1", "kept", "shown_cos")]
    summary = {k: _mean(rows, k) for k in keys}
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "lora_match.json").write_text(json.dumps({"questions": len(rows), "summary": summary,
                                                         "examples": examples, "rows": rows}, indent=1), encoding="utf-8")
    md = [f"# LoRA match test ({len(rows)} TED questions, interview held out)", "",
          "| Answer | Cosine to real answer | Content-word F1 | Kept by grounding guard | Cosine of what users see |",
          "|---|---|---|---|---|",
          f"| Mix Method (verbatim) | {summary['mix_cos']} | {summary['mix_f1']} | n/a | {summary['mix_cos']} |"]
    for name, label in (("base", "Local base model"), ("lora", "Local model + Elon LoRA")):
        md.append(f"| {label} | {summary[f'{name}_raw_cos']} | {summary[f'{name}_raw_f1']} | "
                  f"{summary[f'{name}_kept']:.0%} | {summary[f'{name}_shown_cos']} |")
    md += ["", "## Examples", ""]
    for ex in examples:
        md += [f"**Q:** …{ex['question']}", "", f"- Real: {ex['real']}…", f"- Base: {ex['base']}", f"- LoRA: {ex['lora']}", ""]
    (RESULTS / "lora_match.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
