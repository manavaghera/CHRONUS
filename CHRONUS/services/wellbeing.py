"""
Wellbeing safeguards for grief and memorial use.

1. Crisis check: if a message suggests the person may harm themselves, the
   model steps out of character. No persona answer is generated; the reply
   says plainly that this is an archive, not a person, and lists free
   helplines. The message itself is not written to the Q&A log.
2. Memorial mode (persona "memorial": true, chosen on the Create page for
   someone who has died): the AI voice is told to speak as remembered words,
   never as someone alive and present now. The website adds gentle framing
   and break reminders (FRONTEND .../ChatPanel.jsx).

The patterns favour catching too much over too little: a false positive
costs one out-of-character reply with phone numbers; a miss costs more.
"""

from __future__ import annotations

import re

_CRISIS = re.compile(
    r"\b(?:"
    r"kill(?:ing)? my ?self|end(?:ing)? (?:it all|my (?:own )?life)|take my (?:own )?life|suicid\w*|"
    r"(?:want|wanna|going|plan(?:ning)?) to die|don'?t want to (?:live|be alive|wake up)|"
    r"(?:no|nothing) (?:reason|point) (?:to|in) (?:live|living|going on)|can'?t go on|better off (?:dead|without me)|"
    r"self[- ]?harm\w*|hurt(?:ing)? my ?self|cut(?:ting)? my ?self|overdose|"
    r"join you (?:there|soon|in heaven)|be with you (?:soon|again) (?:in|on the other side)|"
    # common Hinglish
    r"marna chah(?:ta|ti) (?:hu|hoon)|jeena nahi chah(?:ta|ti)|khud ko khatam|aatmahatya"
    r")\b",
    re.IGNORECASE,
)

SUPPORT_MESSAGE = (
    "I'm stepping out of character for a moment, because what you wrote matters more than this archive. "
    "I'm a collection of remembered words, not a person, and I can't support you the way a real person can. "
    "If you're thinking about ending your life or hurting yourself, please talk to someone now. "
    "In India, Tele-MANAS is free and open 24/7 on 14416 (or 1-800-891-4416). "
    "In the US, call or text 988. In the UK and Ireland, Samaritans answer on 116 123. "
    "Anywhere else, findahelpline.com lists free, confidential lines. "
    "If you're in immediate danger, call your local emergency number."
)

HELPLINES = [
    {"region": "India", "name": "Tele-MANAS", "contact": "14416 or 1-800-891-4416", "hours": "24/7"},
    {"region": "United States", "name": "988 Suicide & Crisis Lifeline", "contact": "Call or text 988", "hours": "24/7"},
    {"region": "UK & Ireland", "name": "Samaritans", "contact": "116 123", "hours": "24/7"},
    {"region": "Everywhere else", "name": "Find a Helpline", "contact": "findahelpline.com", "hours": ""},
]

MEMORIAL_STYLE = (
    "These are the remembered words of someone who has died. Speak about your life as it was, in the past "
    "tense where it fits. Never claim to be alive, present, watching over the user, or able to meet them, "
    "and never make promises about the future."
)


def needs_support(text: str) -> bool:
    return bool(_CRISIS.search(text or ""))


def style_for(persona: dict) -> str | None:
    """The persona's style notes, plus memorial framing when it applies."""
    notes = persona.get("style_notes")
    if persona.get("memorial"):
        return f"{notes}\n{MEMORIAL_STYLE}" if notes else MEMORIAL_STYLE
    return notes
