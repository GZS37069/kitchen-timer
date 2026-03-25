"""
Voice command parser.
Converts raw Vosk transcript strings into typed command dicts.
"""

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Number word → digit normalization
# ---------------------------------------------------------------------------

_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}

# Build a full word→digit map including all tens+ones combos ("fifty five" → "55")
_WORD_TO_NUM: dict[str, str] = {}
for w, v in {**_ONES, **_TENS}.items():
    _WORD_TO_NUM[w] = str(v)
for tw, tv in _TENS.items():
    for ow, ov in _ONES.items():
        if ov > 0:
            _WORD_TO_NUM[f"{tw} {ow}"] = str(tv + ov)   # "fifty five" → "55"
            _WORD_TO_NUM[f"{tw}-{ow}"] = str(tv + ov)   # "fifty-five" → "55"


def _normalize_numbers(text: str) -> str:
    """Replace spoken number words with digits (longest/compound matches first)."""
    for word, num in sorted(_WORD_TO_NUM.items(), key=lambda x: -len(x[0])):
        text = re.sub(r'\b' + re.escape(word) + r'\b', num, text, flags=re.IGNORECASE)
    return text


# ---------------------------------------------------------------------------
# Duration parsing
# ---------------------------------------------------------------------------

_UNIT_RE = re.compile(r'(\d+(?:\.\d+)?)\s*(hours?|hr?s?|minutes?|mins?|seconds?|secs?)', re.I)

def _unit_to_seconds(value: float, unit: str) -> int:
    u = unit.lower()
    if u.startswith('h'):
        return int(value * 3600)
    if u.startswith('m'):
        return int(value * 60)
    return int(value)


def _parse_duration(text: str) -> Optional[int]:
    """
    Parse a duration phrase into total seconds.

    Handles:
      "10 minutes"
      "1.5 hours"
      "3 minutes 20 seconds"
      "1 and a half hours"   → 5400
      "2 and a half minutes" → 150
      "half a minute"        → 30
      "half an hour"         → 1800
    """
    # Normalize "X and a half [unit]" → "X.5 [unit]"
    text = re.sub(
        r'(\d+)\s+and\s+a\s+half',
        lambda m: str(int(m.group(1)) + 0.5),
        text, flags=re.I
    )
    # "half a/an [unit]" → "0.5 [unit]"
    text = re.sub(r'\bhalf\s+an?\b', '0.5', text, flags=re.I)
    # "a [unit]" → "1 [unit]"  (e.g. "a minute")
    text = re.sub(r'\ba\s+(hours?|minutes?|mins?|seconds?|secs?)\b', r'1 \1', text, flags=re.I)

    total = 0
    found = False
    for m in _UNIT_RE.finditer(text):
        found = True
        total += _unit_to_seconds(float(m.group(1)), m.group(2))

    return total if found else None


def _duration_label(phrase: str) -> str:
    """
    Produce a short display label from a duration phrase, e.g.
    "1.5 minutes" → "1.5 Minute"
    "3 minutes 20 seconds" → "3 Min 20 Sec"
    """
    parts = []
    for m in _UNIT_RE.finditer(phrase):
        val = m.group(1)
        unit = re.sub(r's$', '', m.group(2).lower().split()[0])  # singular
        # shorten for display
        if unit.startswith('hour'):   unit = 'Hr'
        elif unit.startswith('min'):  unit = 'Min'
        elif unit.startswith('sec'):  unit = 'Sec'
        parts.append(f"{val} {unit}")
    return ' '.join(parts) if parts else phrase.strip().title()


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_KW = r'(?:kitchen|janet)'  # either wake keyword works in parser

# "kitchen start a 10 minute timer [for pasta]"  — duration before the word "timer"
_ADD = re.compile(
    r'(?:hey\s+)?' + _KW + r'\s+'
    r'(?:(?:add|at|had|has|have|and|that|hat|app|set|start|create)\s+)?'
    r'(?:a\s+)?'
    r'(.+?)\s+timer'
    r'(?:\s+(?:for|four|far|named?|called)\s+([a-z][a-z\s]{0,30}))?'
    r'\s*$',
    re.IGNORECASE,
)

# "kitchen start a timer for 10 minutes [for pasta]"  — duration after "timer for"
_ADD_ALT = re.compile(
    r'(?:hey\s+)?' + _KW + r'\s+'
    r'(?:(?:add|at|had|has|have|and|that|hat|app|set|start|create)\s+)?'
    r'(?:a\s+)?'
    r'timer\s+for\s+'
    r'(.+?)'
    r'(?:\s+(?:for|four|far|named?|called)\s+([a-z][a-z\s]{0,30}))?'
    r'\s*$',
    re.IGNORECASE,
)

_CANCEL = re.compile(
    _KW + r'\s+(?:cancel|stop|delete|remove|end)\s+(?:the\s+)?'
    r'([a-z][a-z\s]*?)\s+timer',
    re.IGNORECASE,
)

_PAUSE = re.compile(
    _KW + r'\s+(?:pause|hold|freeze)\s+(?:the\s+)?'
    r'([a-z][a-z\s]*?)\s+timer',
    re.IGNORECASE,
)

_RESUME = re.compile(
    _KW + r'\s+(?:resume|continue|unpause|restart)\s+(?:the\s+)?'
    r'([a-z][a-z\s]*?)\s+timer',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse(text: str) -> Optional[dict]:
    """
    Parse a voice transcript into a command dict, or return None.

    Returns one of:
        {"type": "ADD",    "name": str, "duration": int}
        {"type": "CANCEL", "name": str}
        {"type": "PAUSE",  "name": str}
        {"type": "RESUME", "name": str}
    """
    text = _normalize_numbers(text.lower().strip())

    # Check control commands first (they share verbs with ADD pattern)
    m = _CANCEL.search(text)
    if m:
        return {"type": "CANCEL", "name": m.group(1).strip().rstrip(".")}

    m = _PAUSE.search(text)
    if m:
        return {"type": "PAUSE", "name": m.group(1).strip().rstrip(".")}

    m = _RESUME.search(text)
    if m:
        return {"type": "RESUME", "name": m.group(1).strip().rstrip(".")}

    # Try both ADD forms; prefer _ADD (duration-first) over _ADD_ALT (timer-for-duration)
    for pattern in (_ADD, _ADD_ALT):
        m = pattern.search(text)
        if m:
            duration_phrase = m.group(1).strip()
            raw_name = m.group(2)

            duration = _parse_duration(duration_phrase)
            if duration is None or duration <= 0:
                continue  # try next pattern

            if raw_name:
                name = raw_name.strip().rstrip(".")
                name = re.sub(r'\s*timer\s*$', '', name, flags=re.IGNORECASE).strip()
            else:
                name = _duration_label(duration_phrase)

            return {"type": "ADD", "name": name, "duration": duration}

    return None
