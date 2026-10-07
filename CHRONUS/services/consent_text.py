"""
Consent statements in the language the person consents in.

A relative should read what they agree to in their own language, and the
record should keep exactly the words they agreed to. The website shows these
texts (GET /consent-text?lang=gu) beside the consent boxes, and the model's
consent record stores the statement and its language.

The Hindi and Gujarati wording was drafted for CHRONUS; have a native
speaker check it before relying on it.
"""

from __future__ import annotations

from typing import Literal

Language = Literal["en", "hi", "gu"]

MODEL = {
    "en": "I am this person, or I have their permission (or their estate's) to build this model from their words.",
    "hi": "मैं यही व्यक्ति हूँ, या मेरे पास उनकी (या उनके परिवार/उत्तराधिकारियों की) अनुमति है कि उनके शब्दों से यह मॉडल बनाया जाए।",
    "gu": "હું આ જ વ્યક્તિ છું, અથવા તેમના શબ્દો પરથી આ મોડેલ બનાવવા માટે મારી પાસે તેમની (અથવા તેમના પરિવાર/વારસદારોની) પરવાનગી છે.",
}

VOICE = {
    "en": ("This person, or their estate, agreed to their voice being used for this model, and to the recording being "
           "sent to Fish Audio (a cloud service) to make a private voice from it. Voice is biometric data: removing the "
           "voice deletes it here and at Fish Audio."),
    "hi": ("इस व्यक्ति ने, या उनके परिवार/उत्तराधिकारियों ने, इस मॉडल के लिए उनकी आवाज़ के उपयोग की, और निजी आवाज़ बनाने के लिए "
           "रिकॉर्डिंग को Fish Audio (एक क्लाउड सेवा) पर भेजने की सहमति दी है। आवाज़ बायोमेट्रिक डेटा है: आवाज़ हटाने पर वह यहाँ "
           "से और Fish Audio से भी मिट जाती है।"),
    "gu": ("આ વ્યક્તિએ, અથવા તેમના પરિવાર/વારસદારોએ, આ મોડેલ માટે તેમના અવાજના ઉપયોગની, અને ખાનગી અવાજ બનાવવા માટે રેકોર્ડિંગ "
           "Fish Audio (એક ક્લાઉડ સેવા) પર મોકલવાની સંમતિ આપી છે. અવાજ બાયોમેટ્રિક ડેટા છે: અવાજ દૂર કરવાથી તે અહીંથી અને "
           "Fish Audio પરથી પણ ભૂંસાઈ જાય છે."),
}


def texts(language: str) -> dict:
    language = language if language in MODEL else "en"
    return {"language": language, "model": MODEL[language], "voice": VOICE[language]}
