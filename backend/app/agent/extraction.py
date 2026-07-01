"""Deterministic appliance, symptom, and ZIP extraction helpers."""

from __future__ import annotations

import re

APPLIANCE_ALIASES: dict[str, tuple[str, ...]] = {
    "refrigerator": ("refrigerator", "refridgerator", "fridge", "freezer"),
    "washer": ("washer", "washing machine"),
    "dryer": ("dryer",),
    "dishwasher": ("dishwasher",),
    "oven": ("oven", "range", "stove"),
}

SYMPTOM_PATTERNS: dict[str, tuple[str, ...]] = {
    "not cooling": (
        "not cooling",
        "not cool",
        "not cold",
        "isn't cooling",
        "is not cooling",
        "warm",
        "too warm",
        "won't cool",
        "will not cool",
        "doesn't cool",
    ),
    "leaking": ("leaking", "is leaking", "leak", "water on the floor", "dripping"),
    "not starting": ("won't start", "will not start", "doesn't start", "not starting"),
    "not heating": ("not heating", "no heat", "cold air", "will not heat", "won't heat"),
    "making noise": ("noise", "loud", "rattling", "grinding", "buzzing"),
    "not draining": ("not draining", "won't drain", "standing water"),
}

ZIP_PATTERN = re.compile(r"\b(?P<zip>\d{5})(?:-\d{4})?\b")
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
UPLOAD_INTENT_TERMS = ("photo", "image", "picture", "upload")
SPOKEN_DIGITS: dict[str, str] = {
    "zero": "0",
    "oh": "0",
    "o": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "for": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "ate": "8",
    "nine": "9",
}


def extract_appliance_type(text: str) -> str | None:
    normalized = text.lower()
    for appliance_type, aliases in APPLIANCE_ALIASES.items():
        if any(alias in normalized for alias in aliases):
            return appliance_type
    return None


def extract_symptoms(text: str, existing: list[str] | None = None) -> list[str]:
    normalized = text.lower()
    symptoms = list(existing or [])
    seen = set(symptoms)
    for symptom, patterns in SYMPTOM_PATTERNS.items():
        if symptom in seen:
            continue
        if any(pattern in normalized for pattern in patterns):
            symptoms.append(symptom)
            seen.add(symptom)
    return symptoms


def extract_zip_code(text: str) -> str | None:
    match = ZIP_PATTERN.search(text)
    if match is not None:
        return match.group("zip")
    return extract_spoken_zip_code(text)


def extract_email(text: str) -> str | None:
    match = EMAIL_PATTERN.search(text)
    if match is not None:
        return match.group(0).lower()
    return extract_spoken_email(text)


def requests_image_upload(text: str) -> bool:
    normalized = text.lower()
    return any(term in normalized for term in UPLOAD_INTENT_TERMS)


def extract_spoken_zip_code(text: str) -> str | None:
    tokens = re.findall(r"[a-zA-Z]+|\d", text.lower())
    digits: list[str] = []
    for token in tokens:
        if token.isdigit():
            digits.append(token)
        elif token in SPOKEN_DIGITS:
            digits.append(SPOKEN_DIGITS[token])
        else:
            digits = []
            continue
        if len(digits) == 5:
            return "".join(digits)
    return None


def extract_spoken_email(text: str) -> str | None:
    normalized = _replace_spoken_at(f" {text.lower()} ")
    if "@" not in normalized:
        return None
    before_at, after_at = normalized.rsplit("@", 1)
    local_part = _extract_spoken_email_local_part(before_at)
    if local_part is None:
        return None
    domain_text = _normalize_spoken_email_domain(after_at)
    domain_match = re.match(r"[a-z0-9.-]+\.[a-z]{2,}", domain_text)
    if domain_match is None:
        return None
    candidate = f"{local_part}@{domain_match.group(0)}"
    if EMAIL_PATTERN.fullmatch(candidate):
        return candidate
    return None


def _replace_spoken_at(text: str) -> str:
    normalized = text
    for spoken in (" at sign ", " at symbol ", " at "):
        normalized = normalized.replace(spoken, " @ ")
    return normalized


def _extract_spoken_email_local_part(text: str) -> str | None:
    normalized = _replace_spoken_email_symbols(text)
    compacted = re.sub(r"\s*([._%+-])\s*", r"\1", normalized)
    local_match = re.search(r"[a-z0-9._%+-]+$", compacted.strip())
    if local_match is not None and len(local_match.group(0).strip("._%+-")) >= 3:
        return local_match.group(0)
    return _extract_spelled_email_local_part(text)


def _extract_spelled_email_local_part(text: str) -> str | None:
    dot_marker = " SPOKEN_DOT_MARKER "
    normalized = _replace_spoken_email_symbols(text, dot_marker=dot_marker)
    normalized = re.sub(r"[.,;:]+", " ", normalized)
    symbols = re.findall(r"SPOKEN_DOT_MARKER|[a-z0-9]+|[_%+-]", normalized)
    parts: list[str] = []
    has_alnum = False
    for symbol in reversed(symbols):
        if symbol == "SPOKEN_DOT_MARKER":
            parts.append(".")
            continue
        if symbol in {"_", "%", "+", "-"}:
            parts.append(symbol)
            continue
        if len(symbol) == 1 and symbol.isalnum():
            parts.append(symbol)
            has_alnum = True
            continue
        break
    if not has_alnum:
        return None
    local_part = re.sub(r"\.{2,}", ".", "".join(reversed(parts))).strip("._%+-")
    if len(local_part) < 3:
        return None
    return local_part


def _normalize_spoken_email_domain(text: str) -> str:
    normalized = _replace_spoken_email_symbols(text)
    return re.sub(r"\s+", "", normalized).strip(".,;:")


def _replace_spoken_email_symbols(text: str, *, dot_marker: str = " . ") -> str:
    normalized = text
    replacements = {
        " dot ": dot_marker,
        " period ": dot_marker,
        " point ": dot_marker,
        " underscore ": " _ ",
        " under score ": " _ ",
        " dash ": " - ",
        " hyphen ": " - ",
        " plus ": " + ",
    }
    for spoken, symbol in replacements.items():
        normalized = normalized.replace(spoken, symbol)
    return normalized
