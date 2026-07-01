from __future__ import annotations

from app.agent.extraction import extract_email, extract_zip_code


def test_extract_zip_code_accepts_spoken_digits() -> None:
    assert extract_zip_code("The ZIP code is seven five two zero one.") == "75201"
    assert extract_zip_code("My zip is 7 5 2 0 1") == "75201"


def test_extract_email_accepts_spoken_address() -> None:
    assert extract_email("Send it to customer at example dot test.") == "customer@example.test"
    assert (
        extract_email("Send it to damien plus sears at buildr lab dot com.")
        == "damien+sears@buildrlab.com"
    )
