"""
Multilingual chat: ask in Hindi, Gujarati and other languages.

The archives are in English and so is the embedding model, so a question in
another language is translated to English, answered from memory as usual,
and the answer translated back. The original English answer and the
sources (verbatim, untranslated) are always returned too, and the reply is
labelled as an AI translation: a translated quote is no longer their exact
words.

Translation uses the configured LLM, so it follows the same privacy rule as
AI voice: a custom model must have cloud AI enabled unless the LLM runs on
this computer (LLM_PROVIDER "local" or "ollama").
"""

from __future__ import annotations

import re

from config import config

LANGUAGES = {
    "en": "English", "hi": "Hindi", "gu": "Gujarati", "mr": "Marathi", "bn": "Bengali", "ta": "Tamil",
    "te": "Telugu", "kn": "Kannada", "ml": "Malayalam", "pa": "Punjabi", "ur": "Urdu", "es": "Spanish",
    "fr": "French", "de": "German",
}

# Unicode script ranges -> language (Devanagari is shared by Hindi and
# Marathi; Hindi is the likelier default)
_SCRIPTS = [
    (r"[઀-૿]", "gu"), (r"[ऀ-ॿ]", "hi"), (r"[ঀ-৿]", "bn"), (r"[஀-௿]", "ta"),
    (r"[ఀ-౿]", "te"), (r"[ಀ-೿]", "kn"), (r"[ഀ-ൿ]", "ml"), (r"[਀-੿]", "pa"),
    (r"[؀-ۿ]", "ur"),
]


def detect(text: str) -> str:
    """Language code from the script used (Latin text counts as English)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "en"
    for pattern, code in _SCRIPTS:
        if len(re.findall(pattern, text)) >= max(2, len(letters) // 4):
            return code
    return "en"


def available(persona: dict) -> bool:
    """Can this persona's text go to the configured LLM?"""
    if config.LLM_PROVIDER in ("local", "ollama"):
        return True
    return bool(config.OPENAI_API_KEY) and bool(persona.get("allow_cloud_llm"))


def translate(text: str, target: str, source: str | None = None) -> str:
    """Translate with the configured LLM, keeping [n] citation markers."""
    from services.natural_mode import _call_llm

    src = LANGUAGES.get(source or "", "the original language")
    system = (f"You are a careful translator. Translate the user's text from {src} into {LANGUAGES[target]}. "
              "Keep the meaning, names and numbers exactly, keep markers like [1] where they are, and keep the "
              "speaker's plain spoken style. Reply with the translation only, no notes or quotes around it.")
    return _call_llm(system, text, []).strip().strip('"')
