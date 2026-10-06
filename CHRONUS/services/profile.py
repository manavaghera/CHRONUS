"""
Quick profile answers: "When were you born?", "Where did you study?".

Simple factual questions skip retrieval and answer from a profile: fast,
deterministic, no hallucination risk. Elon's is curated by hand below; the
famous figures' come from Wikidata (CC0) via figures/fetch_profiles.py
(models/<id>/profile.json) and are labelled as public record, not their own
words. The same facts are given to the AI voice (profile_context_block).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

BASIC_PROFILE = {
    "elon_musk": {
        # Identity
        "full_name": "Elon Reeve Musk",
        "born": "June 28, 1971",
        "birth_place": "Pretoria, South Africa",
        "born_and_place": "I was born on June 28, 1971, in Pretoria, South Africa.",
        # "age" is computed per request from BIRTH_DATES (see get_profile)
        "nationality": "South African, Canadian and American",

        # Family
        "mother": "Maye Musk",
        "father": "Errol Musk",
        "siblings": "Kimbal, Tosca",
        "children": "I have several kids. I don't really discuss their details publicly.",

        # Education
        "education": "I went to Queen's University, then transferred to UPenn, got degrees in economics and physics. Was going to do a PhD at Stanford but dropped out after two days to start a company.",

        # Companies
        "companies": "Tesla, SpaceX, X (formerly Twitter), Neuralink, The Boring Company, xAI",
        "ceo_of": "Tesla and SpaceX",
        "founder_of": "SpaceX, Neuralink, The Boring Company, xAI",
        "bought": "X (Twitter) in 2022",

        # Simple facts
        "net_worth": "It fluctuates a lot. I don't really focus on it.",
        "lives_in": "Mostly between Texas and California these days.",
        "hobbies": "I play video games sometimes, Elden Ring, Diablo, that kind of thing. And memes, obviously.",
    }
}

# Age is derived from these so it never goes stale.
BIRTH_DATES = {
    "elon_musk": date(1971, 6, 28),
}

# Elon's values are short facts; these keys are already full sentences
_SENTENCE_KEYS = {"children", "companies", "net_worth", "lives_in", "education", "hobbies", "born_and_place"}


@lru_cache(maxsize=None)
def _public_record(persona: str) -> dict | None:
    """models/<persona>/profile.json from Wikidata, if there is one."""
    path = MODELS_DIR / persona / "profile.json"
    if not re.fullmatch(r"[a-z0-9_]+", persona) or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def get_profile(persona: str, today: date | None = None) -> dict | None:
    """The persona's profile answers by key, with Elon's "age" computed as of *today*."""
    record = _public_record(persona)
    if record:
        return dict(record["answers"])
    profile = BASIC_PROFILE.get(persona)
    if profile is None:
        return None
    profile = dict(profile)
    born = BIRTH_DATES.get(persona)
    if born:
        today = today or date.today()
        had_birthday = (today.month, today.day) >= (born.month, born.day)
        profile["age"] = str(today.year - born.year - (0 if had_birthday else 1))
    return profile


# Patterns that trigger basic info responses. Each must be a question ABOUT
# the persona, matched on whole words — bare keywords like "son" and "own"
# used to hijack "personality"/"reason"/"lessons" and "shut down"/"town
# square". "u" and "bron" cover common chat shorthand and typos.
_YOU = r"(?:you|u)"
_BORN = r"(?:born|bron)"
BASIC_INFO_PATTERNS = {
    rf"\b(?:when|what year|which year)\b.*\b{_YOU}\b.*\b{_BORN}\b"
    r"|\byour (?:birthday|birth ?date|date of birth)\b": "born",
    rf"\bhow old (?:are|r) {_YOU}\b|\byour age\b|\bhow old were {_YOU} when {_YOU} died\b": "age",
    rf"\bwhere\b.*\b{_YOU}\b.*\b{_BORN}\b"
    rf"|\b(?:which|what) (?:country|contry|city)\b.*\b{_YOU}\b.*\b{_BORN}\b"
    rf"|\b{_YOU}\b.*\b{_BORN}\b.*\band where\b"  # "which year were you born, and where?"
    rf"|\bwhere (?:are|r) {_YOU} from\b"
    r"|\byour (?:birth ?place|place of birth|home ?town)\b": "birth_place",
    rf"\b(?:when|where|what year|which year) did {_YOU} (?:die|pass away)\b"
    r"|\byour (?:date|place) of death\b": "died",
    r"\byour (?:full|real) name\b|\bwhat(?:'s| is) your name\b": "full_name",
    r"\bwho(?:'s| is| was) your (?:mom|mum|mother)\b|\byour (?:mom|mum|mother)'?s name\b": "mother",
    r"\bwho(?:'s| is| was) your (?:dad|father)\b|\byour (?:dad|father)'?s name\b": "father",
    rf"\b{_YOU} have (?:any )?(?:brothers?|sisters?|siblings?)\b"
    r"|\bhow many (?:brothers?|sisters?|siblings?)\b"
    r"|\bwho (?:are|were) your (?:brothers?|sisters?|siblings?)\b": "siblings",
    rf"\bwho(?:'s| is| was) your (?:wife|husband|spouse)\b|\b(?:are|were) {_YOU} (?:ever )?married\b"
    rf"|\bwho did {_YOU} marry\b|\byour (?:wife|husband|spouse)'?s name\b": "spouse",
    rf"\bhow many (?:kids|children|child|sons|daughters)\b"
    rf"|\b{_YOU} have (?:any )?(?:kids|children)\b"
    r"|\bwho (?:are|were) your (?:kids|children|sons|daughters)\b": "children",
    rf"\b(?:what|which|how many) companies\b"
    rf"|\bwhat (?:are|r) {_YOU} (?:the )?ceo of\b": "companies",
    rf"\byour net ?worth\b|\bhow rich (?:are|r) {_YOU}\b"
    rf"|\bhow much (?:money )?(?:are {_YOU} worth|do {_YOU} (?:have|make))\b": "net_worth",
    rf"\bwhere do {_YOU} (?:live|stay)\b|\bwhere (?:are|r) {_YOU} (?:living|based|staying)\b": "lives_in",
    rf"\bwhere did {_YOU} (?:go to )?(?:study|school|college|university)\b"
    rf"|\bwhat did {_YOU} study\b|\byour (?:education|degrees?)\b": "education",
    rf"\bwhat (?:is|was) your (?:job|profession|occupation)\b|\bwhat did {_YOU} do for (?:a )?living\b": "occupation",
    rf"\bwhat(?:'s| is| was) your (?:nationality|citizenship)\b|\bwhat nationality (?:are|were) {_YOU}\b": "nationality",
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


def _sentence(key: str, value: str) -> str:
    if key == "age" and value.isdigit():
        return f"I'm {value}."
    return value if key in _SENTENCE_KEYS or value.endswith(".") else f"{value}."


# Clause boundaries for questions that ask several things at once
_CLAUSE_SPLIT = re.compile(r"[?!;.]+|,|\s+\b(?:and|also|plus|but|then)\b\s+")


def remaining_question(query: str) -> str:
    """The part of *query* that isn't a profile question, or "".

    "When were you born and why did you start SpaceX?" -> "why did you start
    SpaceX". Clauses with fewer than two content words ("and where?") belong
    to the profile question before them.
    """
    from services.provenance import content_words

    rest = []
    for clause in _CLAUSE_SPLIT.split(query.lower().replace("’", "'")):
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

    # Normalise curly apostrophes (mobile keyboards) so "what’s" == "what's".
    query_lower = query.lower().replace("’", "'").strip()
    keys = [key for pattern, key in BASIC_INFO_PATTERNS.items() if re.search(pattern, query_lower)]
    if not keys:
        return None
    if keys == ["greeting"]:
        if _public_record(persona):
            return None  # historical figures don't say "Yo."; let retrieval answer
        pick = int(hashlib.md5(query.encode()).hexdigest(), 16) % len(_GREETINGS)
        return {"response": _GREETINGS[pick], "sources": [], "confidence": "high", "fallback": False, "mode": "basic_info"}

    if {"born", "birth_place"} <= set(keys) and profile.get("born_and_place"):
        keys = ["born_and_place" if k == "born" else k for k in keys if k != "birth_place"]
    answers = [_sentence(key, profile[key]) for key in keys if profile.get(key)]
    if not answers:
        return None

    record = _public_record(persona)
    sources = []
    if record:
        sources.append({
            "citation": f"Public record: Wikidata {record['wikidata']}, {record['license']}. Not their own words",
            "source_file": record["url"], "source_type": "public_record", "voice": "third_party",
            "quote": "", "distance": None,
        })
    return {"response": " ".join(answers), "sources": sources, "confidence": "high", "fallback": False,
            "mode": "basic_info", "remainder": remaining_question(query)}


def profile_context_block(persona: str = "elon_musk") -> str:
    """Build a compact 'PERSONAL PROFILE' context block for the LLM prompt.

    Gives the natural-response model the persona's public personal facts
    (birth, family, education, work) so it can answer personal questions
    conversationally even when retrieval doesn't surface a clean
    biographical chunk.
    """
    record = _public_record(persona)
    if record:
        lines = ["PERSONAL PROFILE (public record from Wikidata, not your own words):"]
        lines += [f"- {label}: {value}" for label, value in record["facts"].items()]
        return "\n".join(lines)
    profile = get_profile(persona)
    if not profile:
        return ""
    lines = ["PERSONAL PROFILE (public record):"]
    for key, value in profile.items():
        if key in ("children", "born_and_place"):
            continue  # children kept private; born_and_place repeats born + birth_place
        lines.append(f"- {key.replace('_', ' ').title()}: {value}")
    return "\n".join(lines)
