"""
Local LLM for natural mode (config.LLM_PROVIDER = "local"): a small open
model on this machine's GPU, with the LoRA adapter trained on Elon's own
words (lora/train_lora.py) applied for his persona. Nothing is sent to a
cloud service, matching the paper's local-first design.

The model loads on first use (~3 GB of GPU memory) and is shared; a lock
serialises generation because the API serves requests from worker threads.
"""

from __future__ import annotations

import threading
from contextlib import nullcontext
from pathlib import Path

from config import config

_lock = threading.Lock()
_state: dict = {}


def _load() -> dict:
    if _state:
        return _state
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(config.LOCAL_BASE_MODEL)
    model = AutoModelForCausalLM.from_pretrained(
        config.LOCAL_BASE_MODEL, dtype=torch.bfloat16 if device == "cuda" else torch.float32,
    ).to(device)
    adapter = Path(config.LOCAL_ADAPTER_PATH)
    has_adapter = (adapter / "adapter_config.json").exists()
    if has_adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, str(adapter))
    model.eval()
    _state.update(model=model, tokenizer=tokenizer, device=device, has_adapter=has_adapter, torch=torch)
    return _state


def has_adapter() -> bool:
    return (Path(config.LOCAL_ADAPTER_PATH) / "adapter_config.json").exists()


def generate(messages: list[dict], max_new_tokens: int, use_adapter: bool = False,
             temperature: float = 0.7) -> tuple[str, bool]:
    """Chat completion on the local model. Returns (text, cut_off_by_length).

    use_adapter: apply the persona's LoRA adapter (if trained); otherwise the
    plain base model answers. temperature 0 = deterministic (evaluation).
    """
    with _lock:
        s = _load()
        model, tokenizer, torch = s["model"], s["tokenizer"], s["torch"]
        ids = tokenizer.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt").to(s["device"])
        adapter_off = model.disable_adapter() if s["has_adapter"] and not use_adapter else nullcontext()
        sampling = {"do_sample": True, "temperature": temperature, "top_p": 0.9} if temperature > 0 else {"do_sample": False}
        with torch.no_grad(), adapter_off:
            # repetition_penalty: the tweet-trained adapter fell into loops
            # ("Because it's the most important thing." x10) under greedy decoding
            out = model.generate(ids, attention_mask=torch.ones_like(ids), max_new_tokens=max_new_tokens,
                                 pad_token_id=tokenizer.eos_token_id, repetition_penalty=1.15, **sampling)
        new_tokens = out[0, ids.shape[1]:]
        text = tokenizer.decode(new_tokens, skip_special_tokens=True)
        return text, len(new_tokens) >= max_new_tokens
