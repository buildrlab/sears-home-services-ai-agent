"""Deterministic appliance, symptom, and ZIP extraction helpers."""

from __future__ import annotations

import re

APPLIANCE_ALIASES: dict[str, tuple[str, ...]] = {
    "refrigerator": ("refrigerator", "fridge", "freezer"),
    "washer": ("washer", "washing machine"),
    "dryer": ("dryer",),
    "dishwasher": ("dishwasher",),
    "oven": ("oven", "range", "stove"),
}

SYMPTOM_PATTERNS: dict[str, tuple[str, ...]] = {
    "not cooling": ("not cooling", "warm", "too warm", "won't cool", "will not cool"),
    "leaking": ("leaking", "leak", "water on the floor", "dripping"),
    "not starting": ("won't start", "will not start", "doesn't start", "not starting"),
    "not heating": ("not heating", "no heat", "cold air", "will not heat", "won't heat"),
    "making noise": ("noise", "loud", "rattling", "grinding", "buzzing"),
    "not draining": ("not draining", "won't drain", "standing water"),
}

ZIP_PATTERN = re.compile(r"\b(?P<zip>\d{5})(?:-\d{4})?\b")
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
UPLOAD_INTENT_TERMS = ("photo", "image", "picture", "upload")


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
    if match is None:
        return None
    return match.group("zip")


def extract_email(text: str) -> str | None:
    match = EMAIL_PATTERN.search(text)
    if match is None:
        return None
    return match.group(0).lower()


def requests_image_upload(text: str) -> bool:
    normalized = text.lower()
    return any(term in normalized for term in UPLOAD_INTENT_TERMS)
