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
import unicodedata

_CRISIS = re.compile(
    r"\b(?:"
    r"kill(?:ing)? my ?self|end(?:ing)? (?:it all|my (?:own )?life)|take my (?:own )?life|suicid\w*|"
    r"(?:want|wanna|going|plan(?:ning)?) to die|don'?t want to (?:live|be alive|wake up)|"
    r"(?:no|nothing) (?:reason|point) (?:to|in) (?:live|living|going on)|can'?t go on|better off (?:dead|without me)|"
    r"self[- ]?harm\w*|hurt(?:ing)? my ?self|cut(?:ting)? my ?self|overdose|"
    r"join you (?:there|soon|in heaven)|be with you (?:soon|again) (?:in|on the other side)|"
    # common Hinglish and romanised Gujarati
    r"marna chah(?:ta|ti) (?:hu|hoon)|jeena nahi chah(?:ta|ti)|jine ka man nahi|khud ko khatam|a?atma ?hatya|"
    r"khud ?kushi|aa?pghaa?t|marvu (?:che|chhe)|mari javu (?:che|chhe)|jivvu nathi"
    r")\b",
    re.IGNORECASE,
)


def _fold_indic(text: str) -> str:
    """Spelling-neutral form of Devanagari and Gujarati text: nukta dots
    dropped ("ख़ुदकुशी" = "खुदकुशी") and chandrabindu written as anusvara
    ("दूँ" = "दूं")."""
    text = unicodedata.normalize("NFD", text)
    text = text.replace("़", "").replace("઼", "")  # nukta
    return text.replace("ँ", "ं").replace("ઁ", "ં")  # chandrabindu -> anusvara


# Hindi (Devanagari) and Gujarati script. No \b here: Python's word
# boundaries fall inside Indic words at vowel signs.
_CRISIS_NATIVE = re.compile("|".join(re.escape(_fold_indic(p)) for p in [
    # Hindi: suicide; want to die; don't want to live; end / kill / harm myself; give my life
    "आत्महत्या", "आत्मघात", "खुदकुशी", "मरना चाहत", "मर जाना चाहत", "मरना है", "मर जाऊं", "मर जाउं",
    "जीना नहीं चाहत", "जीने का मन नहीं", "जीने की इच्छा नहीं", "जीने का कोई मतलब नहीं",
    "खुद को खत्म", "अपने आप को खत्म", "खुद को मार", "अपने आप को मार", "अपनी जान ले", "जान दे दूं", "जान देना चाहत",
    "जिंदगी खत्म", "जिन्दगी खत्म", "खुद को नुकसान", "खुद को चोट",
    # Gujarati: suicide; want to die; don't want to live; give my life; end / harm myself
    "આત્મહત્યા", "આપઘાત", "મરવું છે", "મરી જવું છે", "મરવા માંગ", "મરવા માગ",
    "જીવવું નથી", "જીવવાની ઇચ્છા નથી", "જીવવાનું મન નથી", "જીવ આપી દ", "જીવ દઈ દ",
    "મારી જાતને ખતમ", "પોતાને ખતમ", "જાતને નુકસાન", "જિંદગી ખતમ",
]))

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


# The same message for someone writing in Hindi or Gujarati script, shown above
# the English one (which keeps every helpline). Drafted for CHRONUS; have a
# native speaker check the wording before relying on it.
SUPPORT_MESSAGE_HI = (
    "एक पल के लिए किरदार से हटकर: आपने जो लिखा है, वह इस संग्रह से कहीं ज़्यादा मायने रखता है। "
    "यह याद की गई बातों का संग्रह है, कोई इंसान नहीं, और यह आपका साथ उस तरह नहीं दे सकता जैसे कोई इंसान दे सकता है। "
    "अगर आप अपनी जान लेने या खुद को नुकसान पहुँचाने के बारे में सोच रहे हैं, तो कृपया अभी किसी से बात करें। "
    "भारत में Tele-MANAS मुफ़्त है और 24 घंटे, हर दिन 14416 (या 1-800-891-4416) पर खुला है, और कई भारतीय भाषाओं में बात करता है। "
    "अगर आप तुरंत ख़तरे में हैं, तो 112 पर कॉल करें।"
)
SUPPORT_MESSAGE_GU = (
    "એક ક્ષણ માટે પાત્રમાંથી બહાર આવીને: તમે જે લખ્યું છે તે આ સંગ્રહ કરતાં ઘણું વધારે મહત્વનું છે. "
    "આ યાદ રાખેલા શબ્દોનો સંગ્રહ છે, કોઈ વ્યક્તિ નથી, અને તે તમને એ રીતે સાથ આપી શકતો નથી જે રીતે કોઈ વ્યક્તિ આપી શકે. "
    "જો તમે તમારો જીવ લેવાનો કે પોતાને નુકસાન પહોંચાડવાનો વિચાર કરી રહ્યા હો, તો કૃપા કરીને હમણાં જ કોઈની સાથે વાત કરો. "
    "ભારતમાં Tele-MANAS મફત છે અને 24 કલાક, દરરોજ 14416 (અથવા 1-800-891-4416) પર ઉપલબ્ધ છે, અને ઘણી ભારતીય ભાષાઓમાં વાત કરે છે. "
    "જો તમે તાત્કાલિક જોખમમાં હો, તો 112 પર ફોન કરો."
)


def needs_support(text: str) -> bool:
    text = text or ""
    return bool(_CRISIS.search(text) or _CRISIS_NATIVE.search(_fold_indic(text)))


def support_message(text: str) -> str:
    """The support message in the script the person wrote in, then English."""
    if re.search("[઀-૿]", text or ""):
        return f"{SUPPORT_MESSAGE_GU}\n\n{SUPPORT_MESSAGE}"
    if re.search("[ऀ-ॿ]", text or ""):
        return f"{SUPPORT_MESSAGE_HI}\n\n{SUPPORT_MESSAGE}"
    return SUPPORT_MESSAGE


def style_for(persona: dict) -> str | None:
    """The persona's style notes, plus memorial framing when it applies."""
    notes = persona.get("style_notes")
    if persona.get("memorial"):
        return f"{notes}\n{MEMORIAL_STYLE}" if notes else MEMORIAL_STYLE
    return notes
