"""One shape for a phone number, whoever typed it.

Every form in the table below is one a Lebanese gym owner actually writes —
in a spreadsheet, on the member-add form, or into their own login screen.
Getting any of them wrong means a member stored under a number that cannot
be messaged and cannot be logged in with. Decision 44.
"""

from app.domain.phone import normalize_phone


def test_every_way_a_lebanese_number_gets_written() -> None:
    for written, expected in [
        ("+96170123456", "+96170123456"),
        ("70123456", "+96170123456"),
        ("070123456", "+96170123456"),
        ("00961 70 123 456", "+96170123456"),
        ("961-70-123-456", "+96170123456"),
        ("70/123456", "+96170123456"),
        ("(03) 123-456", "+9613123456"),
        ("03 123 456", "+9613123456"),
        ("  +961 3 123456  ", "+9613123456"),
    ]:
        assert normalize_phone(written) == expected, written


def test_a_number_that_cannot_be_lebanese_is_rejected_rather_than_mangled() -> None:
    for written in ("", "   ", "abc", "12345", "701234567890", "+1 415 555 0100"):
        assert normalize_phone(written) is None, written
