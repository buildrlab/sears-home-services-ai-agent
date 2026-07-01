#!/usr/bin/env python3
"""List available voice-capable Twilio local numbers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _client import TwilioClient, TwilioConfig, TwilioScriptError  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Search available Twilio local numbers. This does not purchase numbers."
        )
    )
    parser.add_argument("--country", default="US", help="Two-letter ISO country code.")
    parser.add_argument("--area-code", help="US/Canada area code filter.")
    parser.add_argument("--contains", help="Twilio Contains pattern, for example 555.")
    parser.add_argument("--in-region", help="Region/state filter, for example NY.")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum candidates to request from Twilio, 1-100. Defaults to 10.",
    )
    parser.add_argument(
        "--include-address-required",
        action="store_true",
        help="Include candidates that require regulatory address setup.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = run(args)
    except TwilioScriptError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_text_summary(result)
    return 0


def run(args: argparse.Namespace) -> dict[str, Any]:
    config = TwilioConfig.from_env()
    client = TwilioClient(config)
    numbers = client.list_available_local_numbers(
        country_code=args.country,
        area_code=args.area_code,
        contains=args.contains,
        in_region=args.in_region,
        limit=args.limit,
        exclude_address_required=not args.include_address_required,
    )
    return {
        "country": args.country.upper(),
        "filters": {
            "area_code": args.area_code,
            "contains": args.contains,
            "in_region": args.in_region,
            "voice_enabled": True,
            "include_address_required": args.include_address_required,
        },
        "count": len(numbers),
        "numbers": numbers,
        "next_step": (
            "Pick a number, purchase/assign it in Twilio, export "
            "TWILIO_PHONE_NUMBER, then run scripts/twilio/setup.py."
        ),
    }


def print_text_summary(result: dict[str, Any]) -> None:
    print("Available Twilio local numbers")
    print(f"- Country: {result['country']}")
    print(f"- Count: {result['count']}")
    for item in result["numbers"]:
        capabilities = item.get("capabilities") or {}
        voice = capabilities.get("voice")
        sms = capabilities.get("sms")
        print(
            "- "
            f"{item.get('phone_number')} "
            f"{item.get('locality') or ''} "
            f"{item.get('region') or ''} "
            f"voice={voice} sms={sms} "
            f"address={item.get('address_requirements')}"
        )
    print(f"- Next step: {result['next_step']}")


if __name__ == "__main__":
    raise SystemExit(main())
