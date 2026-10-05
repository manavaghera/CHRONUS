"""
Theme classifier for CHRONUS response pipeline.

Classifies user queries into 7 semantic themes for Mix Method response
generation.  The classifier uses a multi-signal scoring approach:

1. **Exact keyword matching** — each theme carries 15-25 keywords plus
   multi-word phrases, scored against the lowercased query.
2. **Stem-prefix expansion** — every keyword also matches any query word
   that starts with the same stem (e.g. "fail" matches "failure", "failing",
   "failed"), eliminating the need for exhaustive inflection lists.
3. **Phrase boosting** — multi-word phrases (e.g. "first principles") receive
   a 2× weight because they are stronger semantic signals than single words.
4. **IDF weighting** — keywords that are unique to one theme score higher
   than keywords shared across themes, rewarding specificity.
5. **Question-word priors** — interrogative words ("why", "how", "what if")
   nudge toward themes they statistically correlate with.
6. **Confidence calibration** — raw match ratios are rescaled through a
   sigmoid-like curve so that 2-3 strong matches already produce useful
   confidence, while single weak matches stay low.

The result dict exposes the winning theme, its calibrated confidence, the
matched keywords, and the full score vector for debugging / downstream use.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

# ---------------------------------------------------------------------------
# Theme definitions
# ---------------------------------------------------------------------------
# Each theme carries:
#   keywords  – single words and multi-word phrases (lowercased)
#   weight    – global multiplier (1.0 = normal, >1 = boosted theme)
#   priors    – question-word priors: extra score added when the query starts
#               with one of these interrogatives
# ---------------------------------------------------------------------------

THEMES: dict[str, dict[str, Any]] = {
    "love_relationships": {
        "keywords": [
            # core relationship words
            "love", "relationship", "partner", "family", "friend",
            "marriage", "married", "wedding", "divorce",
            "children", "child", "kids", "son", "daughter",
            "dad", "mom", "father", "mother", "parent",
            "dating", "girlfriend", "boyfriend", "spouse", "wife", "husband",
            # emotional connection
            "bond", "intimacy", "trust", "loyalty", "companionship",
            "heartbreak", "breakup", "romance", "affection",
            # Elon-specific
            "grimes", "justine", "talulah", "x æ a-12", "exa dark",
            # phrases (multi-word → boosted)
            "personal life", "love life", "significant other",
            "fell in love", "broken heart",
        ],
        "weight": 1.0,
        "priors": {"who": 0.05},
    },

    "work_purpose": {
        "keywords": [
            # mission / purpose
            "mission", "purpose", "goal", "vision", "ambition", "dream",
            "build", "create", "innovate", "invent", "engineer", "design",
            "company", "business", "startup", "enterprise", "venture",
            "career", "job", "profession", "industry",
            "product", "ship", "launch", "scale", "grow",
            # work ethic
            "work", "hustle", "grind", "overtime", "hardcore",
            "factory", "production", "manufacturing",
            # Elon companies
            "tesla", "spacex", "neuralink", "boring company",
            "x.com", "paypal", "openai", "xai", "starlink",
            # phrases
            "first principles", "make it happen", "move fast",
            "change the world", "multi-planetary",
        ],
        "weight": 1.0,
        "priors": {"what": 0.03, "how": 0.03},
    },

    "fear_resilience": {
        "keywords": [
            # fear / risk
            "fear", "afraid", "scare", "terrify", "dread", "worry", "worried",
            "risk", "danger", "threat", "peril", "hazard", "concern", "concerned",
            "anxiety", "stress", "pressure", "overwhelm", "burnout", "nervous",
            # resilience / endurance
            "resilience", "resilient", "endure", "survive", "persevere",
            "overcome", "withstand", "tough", "strength", "grit",
            "courage", "brave", "bold",
            # challenges
            "challenge", "struggle", "difficult", "hardship", "adversity",
            "obstacle", "setback", "crisis",
            # AI risk (strong fear signal when combined with worry words)
            "ai danger", "ai risk", "ai safety", "ai threat",
            "worried about ai", "dangerous ai", "ai dangerous",
            # Elon-specific
            "existential risk", "extinction", "bankruptcy", "darkest",
            # phrases
            "keep going", "never give up", "worst moment",
            "how do you cope", "what scares you", "biggest fear",
            "are you worried", "does it scare", "keeps you up at night",
        ],
        "weight": 1.0,
        "priors": {"how": 0.02},
    },

    "meaning": {
        "keywords": [
            # philosophy / existence
            "meaning", "purpose", "exist", "existence", "consciousness",
            "philosophy", "philosophical", "metaphysics",
            "universe", "cosmos", "reality", "simulation",
            "life", "death", "mortal", "immortal", "legacy",
            "soul", "spirit", "belief", "believe", "faith",
            "truth", "wisdom", "enlighten",
            # deeper questions
            "why", "reason", "point", "matter", "worth",
            "happiness", "fulfillment", "satisfaction", "content",
            # Elon-specific
            "simulation theory", "fermi paradox", "great filter",
            "pale blue dot", "hitchhiker",
            # phrases
            "meaning of life", "why are we here", "what matters",
            "bigger picture", "grand scheme", "deeper purpose",
        ],
        "weight": 1.0,
        "priors": {"why": 0.08},
    },

    "failure_growth": {
        "keywords": [
            # failure
            "fail", "failure", "mistake", "error", "blunder", "flop",
            "wrong", "regret", "loss", "lose", "lost",
            "crash", "explode", "explosion", "blow up",
            # growth / learning
            "learn", "lesson", "growth", "grow", "improve", "evolve",
            "adapt", "iterate", "pivot", "recover", "rebuild",
            "feedback", "reflect", "retrospect",
            # Elon-specific
            "falcon 1", "amos-6", "cybertruck window",
            "model x delay", "roadster recall", "solarcity",
            # phrases
            "lesson learned", "what went wrong", "biggest mistake",
            "learned from", "bounced back", "tried again",
            "how did you fail", "worst failure",
        ],
        "weight": 1.0,
        "priors": {"how": 0.02, "what": 0.02},
    },

    "change_decisions": {
        "keywords": [
            # decisions
            "decision", "decide", "choice", "choose", "chose", "pick",
            "option", "tradeoff", "trade-off", "dilemma", "crossroads",
            "judgment", "call",
            # change / pivots
            "change", "pivot", "shift", "transform", "transition",
            "switch", "move", "turn", "disrupt", "reinvent",
            # strategy / planning
            "strategy", "plan", "future", "next", "roadmap", "timeline",
            "predict", "forecast", "bet", "gamble", "calculated",
            # Elon-specific
            "buy twitter", "acquire", "merger", "restructure", "layoff",
            "rebrand", "rename",
            # phrases
            "why did you", "what made you", "turning point",
            "strategic decision", "game plan", "long term",
            "changed your mind", "biggest decision",
            "make decisions", "how do you decide", "tough call",
            "how do you choose", "what drives your decisions",
        ],
        "weight": 1.0,
        "priors": {"why": 0.04, "when": 0.03, "how": 0.02},
    },

    "humanity_society": {
        "keywords": [
            # civilization
            "humanity", "human", "civilization", "society", "species",
            "population", "people", "world", "global", "earth",
            "planet", "interplanetary", "multiplanetary",
            # space / Mars (strong humanity signal for Elon)
            "mars", "moon", "space", "colonize", "colony", "terraform",
            "rocket", "starship", "spaceship",
            # future
            "future", "progress", "advance", "evolve", "generation",
            "sustain", "sustainable", "renewable", "climate", "energy",
            # governance / systems
            "government", "regulation", "policy", "democracy", "freedom",
            "economy", "inequality", "poverty", "war", "peace",
            "education", "healthcare", "infrastructure",
            # technology & society
            "ai safety", "alignment", "agi", "superintelligence",
            "singularity", "automation", "robot",
            # Elon-specific
            "mars colony", "starship", "colonize", "terraform",
            "birth rate", "depopulation", "free speech",
            # phrases
            "future of humanity", "save the world", "next generation",
            "existential threat", "multi-planetary species",
            "human civilization", "what happens to",
            "think about mars", "go to mars", "life on mars",
        ],
        "weight": 1.0,
        "priors": {"what": 0.02, "where": 0.03},
    },
}


# ---------------------------------------------------------------------------
# Pre-compute IDF weights
# ---------------------------------------------------------------------------
# A keyword appearing in only 1 theme is a strong discriminator (IDF ≈ 1.95).
# A keyword in all 7 themes is useless (IDF ≈ 0.0).
# ---------------------------------------------------------------------------

_NUM_THEMES = len(THEMES)


def _build_idf_table() -> dict[str, float]:
    """Compute inverse-document-frequency weight for every keyword."""
    doc_freq: Counter[str] = Counter()
    for cfg in THEMES.values():
        # Count each keyword at most once per theme
        seen: set[str] = set()
        for kw in cfg["keywords"]:
            # Normalize to the stem (first word for phrases)
            token = kw.split()[0] if " " not in kw else kw
            if token not in seen:
                doc_freq[token] += 1
                seen.add(token)
    idf: dict[str, float] = {}
    for token, df in doc_freq.items():
        idf[token] = math.log((_NUM_THEMES + 1) / (df + 1)) + 1.0
    return idf


_IDF = _build_idf_table()


def _idf_for(keyword: str) -> float:
    """Return IDF weight for a keyword, falling back to max IDF."""
    token = keyword.split()[0] if " " not in keyword else keyword
    return _IDF.get(token, math.log((_NUM_THEMES + 1) / 2) + 1.0)


# ---------------------------------------------------------------------------
# Stem-prefix helpers
# ---------------------------------------------------------------------------
# Minimum prefix length to avoid false positives (e.g. "a" matching "ai").
_MIN_STEM_LEN = 4


def _tokenize(text: str) -> list[str]:
    """Split text into lowercase alpha-numeric tokens."""
    return re.findall(r"[a-z0-9æ]+(?:[-'][a-z0-9]+)*", text.lower())


def _stem_matches(keyword: str, query_tokens: set[str]) -> bool:
    """Check if *keyword* (single word) matches any query token by prefix."""
    if len(keyword) < _MIN_STEM_LEN:
        return keyword in query_tokens
    return any(
        tok.startswith(keyword) or keyword.startswith(tok)
        for tok in query_tokens
        if len(tok) >= _MIN_STEM_LEN
    )


# ---------------------------------------------------------------------------
# Confidence calibration
# ---------------------------------------------------------------------------

def _calibrate(raw: float) -> float:
    """Map a raw score ratio through a sigmoid curve.

    Designed so that:
      0.0   → 0.0
      0.10  → ~0.35
      0.20  → ~0.60
      0.35  → ~0.80
      0.50+ → ~0.90+
    """
    if raw <= 0.0:
        return 0.0
    # Scaled logistic: 1 / (1 + e^(-k*(x - x0)))
    k = 12.0
    x0 = 0.18
    return round(1.0 / (1.0 + math.exp(-k * (raw - x0))), 4)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_theme(
    query: str,
    default: str = "work_purpose",
) -> dict[str, Any]:
    """
    Classify a query into one of 7 semantic themes.

    Args:
        query: The user's natural-language question.
        default: Fallback theme when no keywords match at all.

    Returns:
        A dict with keys:
          - theme           (str)   : winning theme name
          - confidence      (float) : 0.0–1.0, calibrated
          - matched_keywords(list)  : keywords that fired for the winning theme
          - all_scores      (dict)  : {theme: calibrated_score} for every theme
          - raw_scores      (dict)  : {theme: raw_score} before calibration
          - secondary_theme (str|None): second-highest theme if its score
                                        is ≥ 50 % of the winner's score
    """
    query_lower = query.lower().strip()
    query_tokens = set(_tokenize(query_lower))

    # Detect leading question word for prior boosts
    first_word = query_lower.split()[0].rstrip("?,:") if query_lower else ""

    scores: dict[str, float] = {}
    matches: dict[str, list[str]] = {}

    for theme, cfg in THEMES.items():
        keywords: list[str] = cfg["keywords"]
        theme_weight: float = cfg.get("weight", 1.0)
        priors: dict[str, float] = cfg.get("priors", {})

        hit_keywords: list[str] = []
        weighted_hits = 0.0

        for kw in keywords:
            is_phrase = " " in kw
            matched = False

            if is_phrase:
                # Phrase: substring match in the full query
                if kw in query_lower:
                    matched = True
            else:
                # Single word: exact or stem-prefix match
                if kw in query_tokens or _stem_matches(kw, query_tokens):
                    matched = True

            if matched:
                hit_keywords.append(kw)
                idf = _idf_for(kw)
                boost = 2.0 if is_phrase else 1.0
                weighted_hits += boost * idf

        # Normalize: weighted hits / max possible score for this theme
        max_possible = sum(
            (2.0 if " " in kw else 1.0) * _idf_for(kw) for kw in keywords
        )
        raw = (weighted_hits / max_possible) if max_possible > 0 else 0.0

        # Apply theme weight
        raw *= theme_weight

        # Apply question-word prior
        if first_word in priors:
            raw += priors[first_word]

        scores[theme] = raw
        matches[theme] = hit_keywords

    # --- Pick winner ---
    best_theme = max(scores, key=lambda t: scores[t])
    best_raw = scores[best_theme]

    # If nothing matched at all, fall back to default
    if best_raw <= 0.0:
        best_theme = default
        best_raw = 0.0

    # Calibrate all scores
    calibrated: dict[str, float] = {t: _calibrate(s) for t, s in scores.items()}

    # Secondary theme: second-highest if ≥ 50 % of winner
    sorted_themes = sorted(scores.keys(), key=lambda t: scores[t], reverse=True)
    secondary = None
    if len(sorted_themes) >= 2:
        runner_up = sorted_themes[1]
        if best_raw > 0 and scores[runner_up] >= 0.5 * best_raw:
            secondary = runner_up

    return {
        "theme": best_theme,
        "confidence": calibrated.get(best_theme, 0.0),
        "matched_keywords": matches.get(best_theme, []),
        "all_scores": calibrated,
        "raw_scores": {t: round(s, 6) for t, s in scores.items()},
        "secondary_theme": secondary,
    }


# ---------------------------------------------------------------------------
# Theme-specific prompt fragments
# ---------------------------------------------------------------------------

_THEME_PROMPTS: dict[str, str] = {
    "love_relationships": (
        "Speaking from real personal experience about relationships "
        "and human connection,"
    ),
    "work_purpose": (
        "Regarding the mission, the engineering, and the relentless "
        "drive to build,"
    ),
    "fear_resilience": (
        "When it comes to staring down fear, absorbing risk, and "
        "refusing to quit,"
    ),
    "meaning": (
        "Thinking about the deeper question — why any of this matters "
        "in the first place,"
    ),
    "failure_growth": (
        "Looking back honestly at the failures, the explosions, and "
        "what they actually taught,"
    ),
    "change_decisions": (
        "On the hard calls — the pivots, the bets, and the logic "
        "behind the decisions,"
    ),
    "humanity_society": (
        "Considering the trajectory of human civilization and what "
        "it will take to preserve it,"
    ),
}


def get_theme_prompt(theme: str) -> str:
    """
    Return a theme-specific elaboration prompt fragment.

    Used by the Mix Method to frame Part 2 of a CHRONUS response, steering
    the LLM toward the correct emotional register and subject framing.

    Args:
        theme: One of the 7 canonical theme keys.

    Returns:
        A sentence fragment to prepend to the elaboration instruction.
    """
    return _THEME_PROMPTS.get(theme, _THEME_PROMPTS["work_purpose"])


def get_all_themes() -> list[str]:
    """Return the canonical list of theme names."""
    return list(THEMES.keys())


def describe_theme(theme: str) -> str:
    """Return a short human-readable description of a theme."""
    descriptions: dict[str, str] = {
        "love_relationships": "Romantic relationships, family, friendships, partnerships",
        "work_purpose": "Missions, companies, career, building things, professional goals",
        "fear_resilience": "Fears, risks, failures, challenges, difficulties, setbacks",
        "meaning": "Life meaning, existence, philosophy, deeper purpose",
        "failure_growth": "Specific failures, mistakes, lessons learned, improvement",
        "change_decisions": "Decisions, pivots, changes, strategic choices, future plans",
        "humanity_society": "Civilization, humanity's future, society, world issues",
    }
    return descriptions.get(theme, "Unknown theme")
