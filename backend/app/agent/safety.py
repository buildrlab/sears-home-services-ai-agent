"""Safety guardrails for appliance troubleshooting conversations."""

from __future__ import annotations

UNSAFE_PATTERNS: tuple[str, ...] = (
    "gas smell",
    "smell gas",
    "smells like gas",
    "gas leak",
    "sparking",
    "spark",
    "smoke",
    "fire",
    "burning smell",
    "electrical shock",
    "shocked",
    "carbon monoxide",
)

SAFETY_RESPONSE = (
    "For safety, stop using the appliance now. If you smell gas, see smoke or fire, "
    "notice sparking, or suspect an electrical shock or carbon monoxide risk, leave "
    "the area and contact emergency services or your utility provider. I can still "
    "help arrange a Sears Home Services technician once everyone is safe."
)


def is_unsafe_troubleshooting_request(text: str) -> bool:
    normalized = text.lower()
    return any(pattern in normalized for pattern in UNSAFE_PATTERNS)
