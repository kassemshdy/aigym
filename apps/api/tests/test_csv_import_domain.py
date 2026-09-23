"""The parsing half of the member import, with no database in sight.

The phone table is the part worth reading. Every form in it is one a
Lebanese gym owner actually writes in a spreadsheet, and getting any of
them wrong means importing a member under a number that cannot be messaged.
"""

from datetime import date

from app.domain.csv_import import (
    ERROR_DATE_INVALID,
    ERROR_DUPLICATE_IN_FILE,
    ERROR_NAME_MISSING,
    ERROR_PHONE_INVALID,
    ERROR_PHONE_MISSING,
    MAX_ROWS,
    decode,
    normalize_phone,
    parse_date,
    parse_rows,
)


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


def test_dates_are_read_day_first() -> None:
    """03/04/2026 is the 3rd of April in Lebanon. Reading it the American
    way would silently move a member's renewal by a month."""
    assert parse_date("03/04/2026") == date(2026, 4, 3)
    assert parse_date("2026-04-03") == date(2026, 4, 3)
    assert parse_date("3-4-2026") == date(2026, 4, 3)
    assert parse_date("") is None
    assert parse_date("next tuesday") is None


def test_an_excel_bom_does_not_become_part_of_the_first_header() -> None:
    raw = "﻿name,phone\nرامي,70123456\n".encode()
    parsed = parse_rows(decode(raw))
    assert parsed.missing_columns == [], "the BOM swallowed the name column"
    assert parsed.rows[0].name == "رامي"


def test_an_arabic_windows_export_still_decodes() -> None:
    """cp1256 is what an older Excel on an Arabic Windows writes. Without
    the fallback the whole file is unreadable and the gym is told their
    export is broken when it is perfectly ordinary."""
    raw = "name,phone\nرامي حداد,70123456\n".encode("cp1256")
    text = decode(raw)
    assert "رامي حداد" in text
    assert parse_rows(text).rows[0].name == "رامي حداد"


def test_arabic_headers_are_recognised() -> None:
    parsed = parse_rows("الاسم,الرقم,الاشتراك,تاريخ الانتهاء\nنور,03123456,شهري,01/12/2026\n")
    assert parsed.missing_columns == []
    row = parsed.rows[0]
    assert (row.name, row.phone, row.plan) == ("نور", "+9613123456", "شهري")
    assert row.ends_at == date(2026, 12, 1)


def test_a_header_with_no_phone_column_stops_everything() -> None:
    """Guessing which column held the number is how a gym imports 300
    members under the wrong ones."""
    parsed = parse_rows("name,age\nرامي,30\n")
    assert parsed.missing_columns == ["phone"]
    assert parsed.rows == []


def test_one_bad_row_does_not_condemn_the_file() -> None:
    parsed = parse_rows(
        "name,phone\n"
        "رامي,70123456\n"
        ",71123456\n"          # no name
        "مايا,\n"              # no phone
        "جاد,banana\n"         # not a phone
        "علي,70123456\n"       # the same number as رامي
        "سيرين,76123456\n"
    )
    by_line = {r.line: r for r in parsed.rows}
    assert by_line[2].errors == []
    assert by_line[3].errors == [ERROR_NAME_MISSING]
    assert by_line[4].errors == [ERROR_PHONE_MISSING]
    assert by_line[5].errors == [ERROR_PHONE_INVALID]
    assert by_line[6].errors == [ERROR_DUPLICATE_IN_FILE]
    assert by_line[7].errors == []
    assert [r.line for r in parsed.importable] == [2, 7]


def test_line_numbers_match_the_spreadsheet_the_owner_is_looking_at() -> None:
    """Off by one here and the manager fixes the wrong row."""
    parsed = parse_rows("name,phone\nA,70000001\nB,70000002\n")
    assert [r.line for r in parsed.rows] == [2, 3]


def test_a_bad_date_blocks_its_row_and_nothing_else() -> None:
    parsed = parse_rows("name,phone,ends\nرامي,70123456,tomorrow\nنور,71123456,01/12/2026\n")
    assert parsed.rows[0].errors == [ERROR_DATE_INVALID]
    assert parsed.rows[1].errors == []


def test_blank_lines_and_a_missing_english_name_are_not_errors() -> None:
    parsed = parse_rows("name,phone\nرامي,70123456\n\n   \n")
    assert len(parsed.rows) == 1
    # Falls back rather than failing: both name columns are NOT NULL, and a
    # real export is far more likely to have Arabic than English.
    assert parsed.rows[0].name_en == "رامي"


def test_a_file_longer_than_the_cap_is_truncated_and_says_so() -> None:
    body = "".join(f"M{i},7{i:07d}\n" for i in range(MAX_ROWS + 50))
    parsed = parse_rows("name,phone\n" + body)
    assert len(parsed.rows) == MAX_ROWS
    assert parsed.truncated is True


def test_an_empty_file_is_missing_everything_rather_than_crashing() -> None:
    parsed = parse_rows("")
    assert parsed.missing_columns == ["name", "phone"]
    assert parsed.rows == []
