"""
Local LLM for natural mode (config.LLM_PROVIDER = "local"): a small open
model on this machine's GPU. Nothing is sent to a cloud service, matching
the paper's local-first design.

Style adapters: each person can have their own LoRA adapter, trained on
their own words and promoted only after passing an exam (lora/pipeline.py,
services/style.py). They load on first use and the model switches between
them per request; a request without one gets the plain base model.

The model loads on first use (~3 GB of GPU memory) and is shared; a lock
serialises generation because the API serves requests from worker threads.
"""

from __future__ import annotations

import hashlib
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
    model.eval()
    _state.update(model=model, tokenizer=tokenizer, device=device, adapters={}, torch=torch)
    return _state


def _adapter_name(path: Path) -> str:
    return "a" + hashlib.md5(str(path.resolve()).encode("utf-8")).hexdigest()[:12]


def _activate(path: Path) -> bool:
    """Load the adapter at *path* (once) and make it the active one."""
    if not (path / "adapter_config.json").exists():
        return False
    name = _adapter_name(path)
    if name not in _state["adapters"]:
        model = _state["model"]
        if not _state["adapters"]:  # first adapter: wrap the base model
            from peft import PeftModel
            _state["model"] = PeftModel.from_pretrained(model, str(path), adapter_name=name)
        else:
            model.load_adapter(str(path), adapter_name=name)
        _state["adapters"][name] = str(path)
    _state["model"].set_adapter(name)
    return True


def has_adapter() -> bool:
    """The legacy single adapter (config.LOCAL_ADAPTER_PATH) exists."""
    return (Path(config.LOCAL_ADAPTER_PATH) / "adapter_config.json").exists()


def generate(messages: list[dict], max_new_tokens: int, use_adapter: bool | str = False,
             temperature: float = 0.7) -> tuple[str, bool]:
    """Chat completion on the local model. Returns (text, cut_off_by_length).

    *use_adapter*: a style adapter's folder; True means the legacy one
    (config.LOCAL_ADAPTER_PATH); False runs the plain base model.
    temperature 0 = deterministic (evaluation).
    """
    with _lock:
        s = _load()
        path = Path(config.LOCAL_ADAPTER_PATH) if use_adapter is True else Path(use_adapter) if use_adapter else None
        active = path is not None and _activate(path)
        model, tokenizer, torch = s["model"], s["tokenizer"], s["torch"]
        ids = tokenizer.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt").to(s["device"])
        adapter_off = model.disable_adapter() if s["adapters"] and not active else nullcontext()
        sampling = {"do_sample": True, "temperature": temperature, "top_p": 0.9} if temperature > 0 else {"do_sample": False}
        with torch.no_grad(), adapter_off:
            # repetition_penalty: the tweet-trained adapter fell into loops
            # ("Because it's the most important thing." x10) under greedy decoding
            out = model.generate(ids, attention_mask=torch.ones_like(ids), max_new_tokens=max_new_tokens,
                                 pad_token_id=tokenizer.eos_token_id, repetition_penalty=1.15, **sampling)
        new_tokens = out[0, ids.shape[1]:]
        text = tokenizer.decode(new_tokens, skip_special_tokens=True)
        return text, len(new_tokens) >= max_new_tokens
