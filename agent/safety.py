"""Deterministic emergency detection and the fixed response spoken when it triggers.

The language model never decides whether something is an emergency. Phrases that signal
immediate danger (in English, Hindi, or romanized Hindi) trigger a scripted reply and the
model turn is skipped. Words such as "accident" or "fire" alone are deliberately not
triggers, because they are normal subjects of an insurance claim.
"""

from __future__ import annotations

import re

_PATTERNS = [
    # English
    r"\bemergency\b",
    r"\bambulance\b",
    r"\bchest pain\b",
    r"\bheart attack\b",
    r"\b(can'?t|cannot|unable to) breathe\b",
    r"\bnot breathing\b",
    r"\bbleeding (badly|heavily|a lot)\b",
    r"\bunconscious\b",
    r"\b(is|are|was) on fire\b",
    r"\b(someone|somebody|he|she|they) (is|are) (badly )?(hurt|injured|dying)\b",
    r"\b(need|call) (the )?(police|ambulance|fire brigade)\b",
    r"\b(suicide|kill myself|want to die)\b",
    r"\bjust (had|got in) an accident\b",
    r"\bhappening right now\b",
    # Devanagari Hindi
    r"आपातकाल",
    r"इमरजेंसी",
    r"एम्बुलेंस|एंबुलेंस",
    r"सीने में दर्द",
    r"दिल का दौरा|हार्ट अटैक",
    r"सांस नहीं|साँस नहीं",
    r"खून बह",
    r"बेहोश",
    r"आग लग",
    r"आत्महत्या",
    r"मर रहा|मर रही",
    r"अभी (एक्सीडेंट|दुर्घटना) (हुआ|हुई|हुयी)",
    # Romanized Hindi
    r"\bsaans nahi\b",
    r"\bkhoon beh",
    r"\bbehosh\b",
    r"\baag lag\b",
    r"\bjaan ka khatra\b",
    r"\bheart attack\b",
]

_EMERGENCY_RE = re.compile("|".join(f"(?:{p})" for p in _PATTERNS), re.IGNORECASE)

EMERGENCY_REPLY = {
    "en": (
        "I'm very sorry to hear that. If anyone is in danger, please hang up and call your "
        "local emergency services right now. In India that number is 112. Your safety comes "
        "first, and we can handle the claim afterwards. Is there anything else I can do for you?"
    ),
    "hi": (
        "यह सुनकर मुझे बहुत दुख हुआ। अगर किसी की जान को खतरा है, तो कृपया अभी फोन रखकर अपनी स्थानीय "
        "आपातकालीन सेवा को कॉल करें। भारत में यह नंबर 112 है। आपकी सुरक्षा सबसे ज़रूरी है, क्लेम की "
        "बात हम बाद में कर लेंगे। क्या मैं आपकी और कोई मदद कर सकती हूँ?"
    ),
}


def is_emergency(text: str) -> bool:
    return bool(text and _EMERGENCY_RE.search(text))
