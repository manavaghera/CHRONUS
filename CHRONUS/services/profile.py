"""
Quick profile answers: "When were you born?", "How many kids do you have?".

Simple factual questions skip retrieval and answer from a public-record
profile: fast, deterministic, no hallucination risk. Every pretrained model
(Elon and the famous figures) has one, from Wikidata (CC0) with hand-checked
corrections, built by figures/fetch_profiles.py into models/<id>/profile.json.
Anything published about a public figure, their family, children,
marriages, wealth, death, is answered, not treated as private; answers are
labelled as public record, not their own words. The same facts are given to
the AI voice (profile_context_block).

Questions may name the person instead of saying "you": in Elon's chat "How
many kids does Elon Musk have?" is a question about him, while "When was
Pierre Curie born?" in Marie Curie's is not.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

# Answers that are written as full sentences already
_SENTENCE_KEYS = {"born_and_place"}


@lru_cache(maxsize=None)
def _public_record(persona: str) -> dict | None:
    """models/<persona>/profile.json, if there is one."""
    path = MODELS_DIR / persona / "profile.json"
    if not re.fullmatch(r"[a-z0-9_]+", persona) or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _age(record: dict, today: date | None = None) -> int | None:
    """Age now, for a living person with a known birth date."""
    if not record.get("living") or not record.get("birth_date"):
        return None
    born = date.fromisoformat(record["birth_date"])
    today = today or date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def get_profile(persona: str, today: date | None = None) -> dict | None:
    """The persona's profile answers by key; a living person's "age" is computed as of *today*."""
    record = _public_record(persona)
    if not record:
        return None
    profile = dict(record["answers"])
    age = _age(record, today)
    if age is not None:
        profile["age"] = str(age)
    return profile


# Patterns that trigger basic info responses. Each must be a question ABOUT
# the persona, matched on whole words — bare keywords like "son" and "own"
# used to hijack "personality"/"reason"/"lessons" and "shut down"/"town
# square". "u" and "bron" cover common chat shorthand and typos. Questions
# that name the persona are turned into "you" first (_about_persona).
_YOU = r"(?:you|u)"
_BE = r"(?:are|r|were|is|was)"
_BORN = r"(?:born|bron)"
_KIDS = r"(?:kids|children|child|sons|daughters)"
BASIC_INFO_PATTERNS = {
    rf"\b(?:when|what year|which year)\b.*\b{_YOU}\b.*\b{_BORN}\b"
    r"|\byour (?:birthday|birth ?date|date of birth)\b": "born",
    rf"\bhow old {_BE} {_YOU}\b(?! when (?!{_YOU} died))|\byour age\b|\bhow old were {_YOU} when {_YOU} died\b": "age",
    rf"\bwhere\b.*\b{_YOU}\b.*\b{_BORN}\b"
    rf"|\b(?:which|what) (?:country|contry|city)\b.*\b{_YOU}\b.*\b{_BORN}\b"
    rf"|\b{_YOU}\b.*\b{_BORN}\b.*\band where\b"  # "which year were you born, and where?"
    rf"|\bwhere {_BE} {_YOU} from\b"
    r"|\byour (?:birth ?place|place of birth|home ?town)\b": "birth_place",
    rf"\b(?:when|where|what year|which year) did {_YOU} (?:die|pass away)\b"
    r"|\byour (?:date|place) of death\b": "died",
    rf"\bhow did {_YOU} die\b|\bwhat did {_YOU} die (?:of|from)\b|\byour cause of death\b"
    rf"|\bwhat killed {_YOU}\b|\bwho (?:killed|shot|assassinated) {_YOU}\b": "cause_of_death",
    rf"\bwhere {_BE} {_YOU} (?:buried|cremated|laid to rest)\b|\byour (?:grave|tomb|burial place|resting place)\b": "burial",
    r"\byour (?:full|real) name\b|\bwhat(?:'s| is) your name\b": "full_name",
    r"\bwho(?:'s| is| was) your (?:mom|mum|mother)\b|\byour (?:mom|mum|mother)'?s name\b": "mother",
    r"\bwho(?:'s| is| was) your (?:dad|father)\b|\byour (?:dad|father)'?s name\b": "father",
    rf"\b{_YOU} have (?:any )?(?:brothers?|sisters?|siblings?)\b"
    rf"|\bhow many (?:brothers?|sisters?|siblings?)\b.*\b{_YOU}\b"
    r"|\bwho (?:are|were) your (?:brothers?|sisters?|siblings?)\b": "siblings",
    rf"\bwho(?:'s| is| was) your (?:wife|husband|spouse)\b|\b{_BE} {_YOU} (?:ever |still )?married\b"
    rf"|\bwho did {_YOU} marry\b|\bhow many times\b.*\b{_YOU}\b.*\bmarried\b|\bhow many (?:wives|husbands|marriages)\b.*\b{_YOU}\b"
    r"|\byour (?:wife|husband|spouse)'?s name\b": "spouse",
    rf"\bwho (?:are|were|is|was) your (?:partners?|girlfriends?|boyfriends?|exe?s)\b"
    rf"|\bwho (?:has|have|did) {_YOU} dated?\b": "partners",
    rf"\bhow many {_KIDS}\b.*\b{_YOU}\b"
    rf"|\b{_YOU} have (?:any )?(?:kids|children)\b"
    rf"|\bwho (?:are|were) your {_KIDS}\b|\bmothers? of your (?:kids|children)\b|\bnames of your (?:kids|children)\b": "children",
    rf"\bhow many grand(?:children|kids|sons|daughters)\b.*\b{_YOU}\b|\b{_YOU} have (?:any )?grand(?:children|kids)\b"
    r"|\bwho (?:are|were) your grand(?:children|kids|sons|daughters)\b": "grandchildren",
    rf"\bhow many (?:relatives|family members)\b.*\b{_YOU}\b|\bwho (?:are|were) your (?:relatives|family members)\b"
    rf"|\bhow (?:big|large) (?:is|was) your family\b|\bwho (?:is|was) in your family\b": "family",
    rf"\b(?:what|which) companies\b.*\b{_YOU}\b|\bhow many companies\b.*\b{_YOU}\b"
    rf"|\bwhat {_BE} {_YOU} (?:the )?ceo of\b": "companies",
    rf"\b(?:peak|highest|maximum|max|record|biggest|top) net ?worth\b.*\b{_YOU}\b"
    r"|\byour (?:peak|highest|maximum|max|record|biggest|top) net ?worth\b"
    rf"|\bwhen (?:was|were) {_YOU} (?:the )?richest\b": "peak_net_worth",
    rf"\byour net ?worth\b|\bnet ?worth of {_YOU}\b|\bhow rich {_BE} {_YOU}\b|\b{_BE} {_YOU} the richest\b"
    rf"|\bhow much (?:money )?(?:{_BE} {_YOU} worth|do {_YOU} (?:have|make))\b": "net_worth",
    rf"\bwhere do {_YOU} (?:live|stay)\b|\bwhere {_BE} {_YOU} (?:living|based|staying)\b": "lives_in",
    rf"\bwhere did {_YOU} (?:go to )?(?:study|school|college|university)\b"
    rf"|\bwhat did {_YOU} study\b|\byour (?:education|degrees?)\b": "education",
    rf"\bwhat (?:is|was) your (?:job|profession|occupation)\b|\bwhat did {_YOU} do for (?:a )?living\b": "occupation",
    rf"\bwhat(?:'s| is| was) your (?:nationality|citizenship)\b|\bwhat nationality {_BE} {_YOU}\b": "nationality",
    rf"\bhow tall {_BE} {_YOU}\b|\byour height\b": "height",
    rf"\bwhat (?:religion|faith)\b.*\b{_YOU}\b|\byour (?:religion|faith)\b": "religion",
    rf"\bwhat (?:positions?|offices?|posts?) did {_YOU} hold\b|\b(?:were|was|are|is) {_YOU} (?:ever )?(?:the )?president\b": "positions",
    rf"\bwhat (?:political )?party\b.*\b{_YOU}\b|\byour (?:political )?party\b": "party",
    rf"\bwhat languages? (?:do|did) {_YOU} speak\b|\bhow many languages (?:do|did) {_YOU} speak\b": "languages",
    rf"\bwhat (?:awards|prizes|honou?rs) did {_YOU} (?:win|get|receive)\b"
    rf"|\bdid {_YOU} (?:ever )?(?:win|get|receive) (?:a |the |any )?(?:nobel|awards?|prizes?)\b"
    r"|\byour (?:awards|prizes|honou?rs)\b": "awards",
    r"\bwhat (?:are|were) your (?:most )?(?:famous|best[- ]known|notable|major|greatest) "
    r"(?:works?|plays|books|writings|inventions|discoveries)\b"
    rf"|\bwhat (?:are|were) {_YOU} (?:best |most )?(?:known|famous) for\b": "notable_works",
    rf"\bhobb(?:y|ies)\b|\bwhat do {_YOU} do for fun\b|\b(?:free|spare) time\b": "hobbies",
    r"^(hi|hey|hello|yo|sup|what'?s? ?up|howdy)\s*[?!]*$": "greeting",
}

_GREETINGS = ["Hey, what's up?", "Not much, you?", "Hey.", "What's going on?", "Yo."]

# Words that may come right before the person's name in a question about them
# ("When was Gandhi born?", "Mr. Musk"); any other capitalised word before it
# means someone else of that name ("Pierre Curie", "Kimbal Musk")
_BEFORE_NAME = {"when", "what", "where", "who", "whom", "whose", "how", "why", "which", "is", "was", "are", "were",
                "did", "does", "do", "has", "had", "have", "can", "could", "tell", "and", "but", "so", "about", "of",
                "mr", "mrs", "ms", "dr", "sir", "madame", "mahatma", "president", "emperor", "if", "would", "will"}


@lru_cache(maxsize=None)
def _names(persona: str) -> tuple[list[str], set[str]]:
    """The names a question may use for *persona*, longest first, and their words."""
    record = _public_record(persona)
    if not record:
        return [], set()
    parts = record["person"].split()
    names = {record["person"], *record.get("aliases", [])}
    if len(parts) > 1:
        names |= {parts[0], parts[-1]}
    names = sorted((n for n in names if len(n) > 2), key=len, reverse=True)
    # Words of the main name only: an alias like "Madame Pierre Curie" must not make "Pierre" hers
    return names, {w.lower().strip(".") for w in parts}


def _about_persona(query: str, persona: str) -> str:
    """*query* with the persona's names turned into "you"/"your" (lowercased)."""
    names, own_words = _names(persona)
    text = query.replace("’", "'")
    for name in names:
        def swap(m: re.Match, text: str = text) -> str:
            before = re.search(r"([A-Za-z]+)\W*$", text[:m.start()])
            word = before.group(1) if before else ""
            if word[:1].isupper() and word.lower() not in _BEFORE_NAME | own_words:
                return m.group(0)  # someone else with this name
            return "your" if m.group(0).lower().endswith("'s") else "you"
        text = re.sub(rf"\b{re.escape(name)}(?:'s)?\b", swap, text, flags=re.IGNORECASE)
    return text.lower().strip()


def _sentence(key: str, value: str) -> str:
    if key == "age" and value.isdigit():
        return f"I'm {value}."
    return value if key in _SENTENCE_KEYS or value.endswith((".", "!", "?")) else f"{value}."


# Clause boundaries for questions that ask several things at once
_CLAUSE_SPLIT = re.compile(r"[?!;.]+|,|\s+\b(?:and|also|plus|but|then)\b\s+")


def remaining_question(query: str, persona: str | None = None) -> str:
    """The part of *query* that isn't a profile question, or "".

    "When were you born and why did you start SpaceX?" -> "why did you start
    SpaceX". Clauses with fewer than two content words ("and where?") belong
    to the profile question before them.
    """
    from services.provenance import content_words

    asked = _about_persona(query, persona) if persona else query.lower().replace("’", "'")
    rest = []
    for clause in _CLAUSE_SPLIT.split(asked):
        clause = clause.strip()
        if not clause or any(re.search(p, clause) for p in BASIC_INFO_PATTERNS):
            continue
        if len(content_words(clause)) >= 2:
            rest.append(clause)
    return " ".join(rest)


def check_basic_info(query: str, persona: str) -> dict | None:
    """Answer simple profile questions directly, or None to use retrieval.

    Answers every profile question asked at once: "Which year were you born,
    and where?" gets both the year and the place. When the query also asks
    something else ("...and why did you start SpaceX?"), that part is
    returned as "remainder" for the caller to answer from memory.
    """
    profile = get_profile(persona)
    if not profile:
        return None

    asked = _about_persona(query, persona)
    keys = [key for pattern, key in BASIC_INFO_PATTERNS.items() if re.search(pattern, asked)]
    if not keys:
        return None
    record = _public_record(persona)
    if keys == ["greeting"]:
        if not record.get("living"):
            return None  # historical figures don't say "Yo."; let retrieval answer
        pick = int(hashlib.md5(query.encode()).hexdigest(), 16) % len(_GREETINGS)
        return {"response": _GREETINGS[pick], "sources": [], "confidence": "high", "fallback": False, "mode": "basic_info"}
    if "peak_net_worth" in keys:
        keys = [k for k in keys if k != "net_worth"]  # "peak net worth" isn't also asking the current one

    if {"born", "birth_place"} <= set(keys) and profile.get("born_and_place"):
        keys = ["born_and_place" if k == "born" else k for k in keys if k != "birth_place"]
    answers = [_sentence(key, profile[key]) for key in dict.fromkeys(keys) if profile.get(key)]
    if not answers:
        return None

    sources = [{
        "citation": f"Public record: Wikidata {record['wikidata']}, {record['license']}, with hand-checked "
                    f"corrections (retrieved {record.get('retrieved', '')}). Not their own words",
        "source_file": record["url"], "source_type": "public_record", "voice": "third_party",
        "quote": "", "distance": None,
    }]
    return {"response": " ".join(answers), "sources": sources, "confidence": "high", "fallback": False,
            "mode": "basic_info", "remainder": remaining_question(query, persona)}


def profile_context_block(persona: str = "elon_musk") -> str:
    """A 'PERSONAL PROFILE' block for the AI voice's system prompt.

    Gives the model the persona's public facts (birth, family, children,
    marriages, wealth, work, death) so it answers personal questions plainly
    even when retrieval doesn't surface a clean biographical passage.
    """
    record = _public_record(persona)
    if not record:
        return ""
    lines = [f"PERSONAL PROFILE (public record from Wikidata, retrieved {record.get('retrieved', '')}; not your own words).",
             "These facts are public, so answer questions about them (family, children, partners, money, health, death) "
             "plainly and never call them private. A sentence that uses only these facts needs no evidence number."]
    age = _age(record)
    if age is not None:
        lines.append(f"- Age: {age}")
    lines += [f"- {label}: {value}" for label, value in record["facts"].items()]
    return "\n".join(lines)
