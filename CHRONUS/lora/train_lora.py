"""
Train a LoRA adapter on Elon Musk's own words for the local natural-mode
model (config.LLM_PROVIDER = "local", services/local_llm.py).

    python lora/prepare_data.py
    python lora/train_lora.py      # ~10-20 min on an RTX 4080 laptop GPU

Base model: Qwen2.5-1.5B-Instruct (Apache-2.0). Only the LoRA weights are
trained; loss is computed on his text, not on the prompt.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Before torch: transformers' Trainer pulls in pyarrow (via datasets), and
# pyarrow loaded after torch crashes the process silently on Windows.
import pyarrow.dataset  # noqa: E402,F401
import torch  # noqa: E402
from peft import LoraConfig, get_peft_model  # noqa: E402
from transformers import (AutoModelForCausalLM, AutoTokenizer, DataCollatorForSeq2Seq,  # noqa: E402
                          Trainer, TrainingArguments)

from config import config  # noqa: E402

HERE = Path(__file__).resolve().parent
SYSTEM = "You are Elon Musk."
MAX_TOKENS = 256


class JsonlDataset(torch.utils.data.Dataset):
    def __init__(self, path: Path, tokenizer):
        self.rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        row = self.rows[i]
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": row["prompt"]}]
        prompt_ids = self.tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=True)
        full_ids = self.tokenizer.apply_chat_template(
            messages + [{"role": "assistant", "content": row["text"]}], tokenize=True)[:MAX_TOKENS]
        labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids):]  # learn his words only
        return {"input_ids": full_ids, "attention_mask": [1] * len(full_ids), "labels": labels[:len(full_ids)]}


def main() -> None:
    torch.manual_seed(42)
    tokenizer = AutoTokenizer.from_pretrained(config.LOCAL_BASE_MODEL)
    model = AutoModelForCausalLM.from_pretrained(config.LOCAL_BASE_MODEL, dtype=torch.bfloat16).to("cuda")
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    ))
    model.print_trainable_parameters()

    train = JsonlDataset(HERE / "data" / "train.jsonl", tokenizer)
    val = JsonlDataset(HERE / "data" / "val.jsonl", tokenizer)
    # Batch 8 x 2 accumulation (effective 16) and validation only before/after:
    # Qwen's 152k-token vocabulary makes the logits of a batch of 16 ~2.5 GB,
    # which pushed a 12 GB laptop GPU into shared memory (17 s/step vs ~1 s).
    args = TrainingArguments(
        output_dir=str(HERE / "checkpoints"), per_device_train_batch_size=8, gradient_accumulation_steps=2,
        per_device_eval_batch_size=8, num_train_epochs=1, learning_rate=2e-4, lr_scheduler_type="cosine",
        warmup_ratio=0.03, logging_steps=50, eval_strategy="no", save_strategy="no", bf16=True,
        report_to=[], dataloader_num_workers=0, remove_unused_columns=False, seed=42,
    )
    collator = DataCollatorForSeq2Seq(tokenizer, padding=True, label_pad_token_id=-100)
    trainer = Trainer(model=model, args=args, train_dataset=train, eval_dataset=val, data_collator=collator)

    start = time.time()
    before = trainer.evaluate()["eval_loss"]
    trainer.train()
    after = trainer.evaluate()["eval_loss"]

    out = Path(config.LOCAL_ADAPTER_PATH)
    model.save_pretrained(str(out))
    summary = {"base_model": config.LOCAL_BASE_MODEL, "train_examples": len(train), "val_examples": len(val),
               "epochs": 1, "val_loss_before": round(before, 4), "val_loss_after": round(after, 4),
               "minutes": round((time.time() - start) / 60, 1)}
    (out / "training_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
