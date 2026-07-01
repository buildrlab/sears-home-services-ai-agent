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
    normalized = f" {text.lower()} "
    replacements = {
        " at sign ": " @ ",
        " at symbol ": " @ ",
        " at ": " @ ",
        " dot ": " . ",
        " period ": " . ",
        " point ": " . ",
        " underscore ": " _ ",
        " under score ": " _ ",
        " dash ": " - ",
        " hyphen ": " - ",
        " plus ": " + ",
    }
    for spoken, symbol in replacements.items():
        normalized = normalized.replace(spoken, symbol)
    normalized = re.sub(r"\s*([@._%+-])\s*", r"\1", normalized)
    if "@" not in normalized:
        return None
    before_at, after_at = normalized.rsplit("@", 1)
    local_match = re.search(r"[a-z0-9._%+-]+$", before_at.strip())
    if local_match is None:
        return None
    domain_text = re.sub(r"\s+", "", after_at).strip(".,;:")
    domain_match = re.match(r"[a-z0-9.-]+\.[a-z]{2,}", domain_text)
    if domain_match is None:
        return None
    candidate = f"{local_match.group(0)}@{domain_match.group(0)}"
    if EMAIL_PATTERN.fullmatch(candidate):
        return candidate
    return None
