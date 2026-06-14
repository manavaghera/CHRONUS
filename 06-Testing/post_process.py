"""Scrub AI-tells from LLM output to make it sound more human."""

import re

AI_PHRASES = [
    r"\bdelve(?:s|d)?\b",
    r"\bleverag(?:e|es|ing)\b",
    r"\bIn conclusion,?\s*",
    r"\bIt'?s worth noting that\s*",
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
    r"\bAt the end of the day,?\s*",
    r"\bGreat question!?\s*",
    r"\(Note:.*?\)\s*",
    r"\(I'?ve tried to.*?\)\s*",
    r"\(Let me know.*?\)\s*",
    r"\(.*?in character as.*?\)\s*",
    r"\(.*?verbal signature.*?\)\s*",
    r"\(.*?mannerisms.*?\)\s*",
    r"Note:\s*I'?ve tried to.*?$",
    r"Let me know if you'?d like me to revise anything\.?\s*$",
    r"Hope this (?:helps|is helpful)\.?\s*$",
    r"Is there anything else.*?\??\s*$",
]

FILLER_INTROS = [
    r"^(?:Sure|Okay|Alright|Well),?\s+",
    r"^(?:So|Basically),?\s+",
    r"^(?:You know|You see),?\s+",
    r"^That'?s a (?:great|good|interesting) question\.?\s*",
]

def scrub(text: str) -> str:
    out = text.strip()
    for pat in FILLER_INTROS:
        out = re.sub(pat, "", out, count=1, flags=re.IGNORECASE)
    for pat in AI_PHRASES:
        out = re.sub(pat, "", out, flags=re.IGNORECASE)
    out = re.sub(r"\bHowever,\s*", "Look, ", out, flags=re.IGNORECASE)
    out = re.sub(r"\bTherefore,\s*", "So ", out, flags=re.IGNORECASE)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([.,!?])", r"\1", out)
    out = re.sub(r"^[.,!?;:\s]+", "", out)
    out = re.sub(r"\s*\([^)]*\)\s*$", "", out).strip()
    if out and not out[-1] in '.!?"\'':
        last = max(out.rfind('.'), out.rfind('!'), out.rfind('?'))
        if last > 20:
            out = out[:last + 1]
    if out:
        out = out[0].upper() + out[1:]
    return out.strip()
