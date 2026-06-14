"""
Post-process LLM output to remove AI-tells and make it sound more human.
"""

import re

# Phrases the model loves but Elon would never say
AI_PHRASES = [
    r"\bdelve(?:s|d)?\b",
    r"\bleverag(?:e|es|ing)\b",
    r"\bIn conclusion,?\s*",
    r"\bIt'?s worth noting that\s*",
    r"\bIt is worth noting that\s*",
    r"\bmoreover,?\s*",
    r"\bfurthermore,?\s*",
    r"\badditionally,?\s*",
    r"\bnevertheless,?\s*",
    r"\bnavigate the\b",
    r"\blandscape of\b",
    r"\btapestry of\b",
    r"\bparadigm shift\b",
    r"\bcutting-?edge\b",
    r"\bgame-?changer\b",
    r"\bholistic\b",
    r"\bsynerg(?:y|ies)\b",
    r"\bin today'?s world,?\s*",
    r"\bin this day and age,?\s*",
    r"\bas we can see,?\s*",
    r"\bGreat question!?\s*",
    r"\bI hope this helps.?\s*",
    r"\bLet me know if you have (?:any )?more questions\.?\s*",
    r"\bAt the end of the day,?\s*",
    r"\bWhen all is said and done,?\s*",
    r"\bThat'?s a (?:great|fantastic|wonderful) question!?\s*",

    # Kill meta-commentary and parentheticals after the response
    r"\(Note:.*?\)\s*",
    r"\(I'?ve tried to.*?\)\s*",
    r"\(I tried to.*?\)\s*",
    r"\(Let me know.*?\)\s*",
    r"\(.*?in character as.*?\)\s*",
    r"\(.*?keeping in mind.*?\)\s*",
    r"\(.*?personality traits.*?\)\s*",
    r"\(.*?verbal signature.*?\)\s*",
    r"\(.*?mannerisms.*?\)\s*",
    r"\(.*?Let me know.*?\)\s*",
    r"Note:\s*I'?ve tried to.*?$",
    r"Note:\s*I tried to.*?$",
    r"Let me know if you'?d like me to revise anything\.?\s*$",
    r"Let me know if you (?:want|need) (?:anything else|more)\.?\s*$",
    r"Hope this (?:helps|is helpful)\.?\s*$",
    r"Is there anything else (?:you'?d like|you want|you would like)\??\s*$",
]

# Filler hedges
HEDGE_PHRASES = [
    r"\bperhaps maybe\b",
    r"\bpossibly probably\b",
    r"\bsomewhat perhaps\b",
]

# Filler intros to strip
FILLER_INTROS = [
    r"^(?:Sure|Okay|Alright|Well),?\s+",
    r"^(?:So|Basically),?\s+",
    r"^(?:You know|You see),?\s+",
    r"^That'?s a (?:great|good|interesting) question\.?\s*",
]


def scrub(text: str) -> str:
    """Remove AI-tells and filler. Apply in priority order."""
    out = text.strip()

    # Strip hedge stacks
    for pat in HEDGE_PHRASES:
        out = re.sub(pat, "", out, flags=re.IGNORECASE)

    # Strip filler intros at the start
    for pat in FILLER_INTROS:
        out = re.sub(pat, "", out, count=1, flags=re.IGNORECASE)

    # Strip AI-tells (case insensitive, but preserve the rest)
    for pat in AI_PHRASES:
        out = re.sub(pat, "", out, flags=re.IGNORECASE)

    # Collapse multiple spaces and fix orphaned punctuation
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([.,!?])", r"\1", out)
    out = re.sub(r"^[.,!?;:\s]+", "", out)

    # Replace overly-formal connectives with Elon's actual ones
    out = re.sub(r"\bHowever,\s*", "Look, ", out, flags=re.IGNORECASE)
    out = re.sub(r"\bTherefore,\s*", "So ", out, flags=re.IGNORECASE)

    # Strip trailing parenthetical postscripts
    out = re.sub(r"\s*\([^)]*\)\s*$", "", out).strip()

    # If that leaves trailing junk, hard cut at the last sentence-ending punctuation
    if out and out[-1] not in '.!?"\'':
        last = max(out.rfind('.'), out.rfind('!'), out.rfind('?'))
        if last > 20:
            out = out[:last + 1]

    # Capitalize first letter of what remains
    if out:
        out = out[0].upper() + out[1:]

    return out.strip()


def sentence_cap(text: str) -> str:
    """Ensure no run-on paragraphs - add a tiny break at sentence boundaries if missing."""
    # If response is one long sentence (>40 words), it might need splitting
    return text
