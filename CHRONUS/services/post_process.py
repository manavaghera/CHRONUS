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

# Assistant-style intros to strip. "Well", "So" and "Basically" are NOT here:
# they're how he actually starts sentences ("basically" appears 151 times in
# his cleaned transcripts), so stripping them removed his voice.
FILLER_INTROS = [
    r"^(?:Sure|Okay|Alright|Certainly|Absolutely),?\s+",
    r"^(?:You know|You see),?\s+",
    r"^That'?s a (?:great|good|interesting) question\.?\s*",
]

# A closing sentence that just sums up the answer is a strong AI tell.
SUMMARY_CLOSER = re.compile(r"(?:In summary|In short|Overall|All in all|To sum up|In conclusion)\b", re.IGNORECASE)


def scrub(text: str | None) -> str:
    """Remove AI-tells and filler. Apply in priority order."""
    out = (text or "").strip()

    # Drop a final wrap-up sentence ("Overall, ...") when there's an answer before it
    sentences = re.split(r"(?<=[.!?])\s+", out)
    if len(sentences) >= 2 and SUMMARY_CLOSER.match(sentences[-1]):
        out = " ".join(sentences[:-1])

    # Dashes are the most recognisable LLM tell; turn them into commas.
    out = re.sub(r"\s*[—–]\s*", ", ", out)
    out = re.sub(r"(?<=\w) - (?=\w)", ", ", out)  # spaced hyphen used as a dash
    out = re.sub(r",\s*([,.!?])", r"\1", out)
    # "Plus," opening a sentence
    out = re.sub(r"(?:^|(?<=[.!?] ))Plus,\s*", "And ", out)

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
