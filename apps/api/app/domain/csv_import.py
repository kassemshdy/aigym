"""Turning a gym's notebook export into rows we can create members from.

Pure: text in, dataclasses out. No HTTP, no SQLAlchemy, no network — same
convention as dues.py and analytics.py. The route does the fetching and
the writing.

**Why this is on the server rather than in the browser.** Python's stdlib
`csv` costs nothing to ship, where Papaparse is ~19 KB against a 200 KB
budget. But the real reason is that a preview the client parses and a
commit the server validates are two implementations of the same rules,
and they drift. Here the preview and the commit call the same functions,
so what the manager approved is what gets written.

**What a real export actually looks like.** Arabic names, an Excel BOM,
phone numbers written every way a person writes them (03 123456,
+961 3 123 456, 70/123456, 0096170123456), blank cells, the same member
twice, and a header row in Arabic. Every one of those is handled here
rather than being a reason to tell a gym their file is wrong.
"""

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime

#: Errors are stable keys, not sentences: the client renders them through
#: t() in the manager's own language, and an English string baked in here
#: could not be translated at the point it is shown.
ERROR_NAME_MISSING = "name_missing"
ERROR_PHONE_MISSING = "phone_missing"
ERROR_PHONE_INVALID = "phone_invalid"
ERROR_DUPLICATE_IN_FILE = "duplicate_in_file"
ERROR_DATE_INVALID = "date_invalid"
#: Raised by the route, not here — it needs the gym's own plans and roster.
ERROR_PLAN_UNKNOWN = "plan_unknown"
ERROR_ALREADY_A_MEMBER = "already_a_member"

MAX_ROWS = 2000

# Header names a Lebanese gym's spreadsheet actually uses. Matched after
# lowercasing and trimming, so "Phone " and "phone" are the same column.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("name", "full name", "member", "الاسم", "اسم", "الإسم", "اسم المشترك"),
    "name_en": ("name_en", "english name", "name en", "english", "الاسم بالانكليزي"),
    "phone": (
        "phone", "mobile", "number", "tel",
        "رقم", "الرقم", "هاتف", "الهاتف", "موبايل", "تلفون",
    ),
    "plan": ("plan", "subscription", "package", "الاشتراك", "اشتراك", "خطة", "الخطة"),
    "ends_at": (
        "ends_at", "ends", "end", "end date", "expiry", "expires", "valid until",
        "تاريخ الانتهاء", "ينتهي", "الانتهاء", "تاريخ النهاية",
    ),
}


@dataclass
class ImportRow:
    """One line of the file, normalized. `errors` empty means importable."""

    #: 1-based and counting the header, so it is the line number the gym
    #: owner sees in their own spreadsheet rather than an index.
    line: int
    name: str
    name_en: str
    phone: str
    #: As written in the file; the route resolves it against the gym's
    #: plans, since this module has no idea what they are.
    plan: str
    ends_at: date | None
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class ParsedFile:
    rows: list[ImportRow]
    #: Required columns the header did not have. When this is non-empty
    #: `rows` is empty too: there is nothing useful to preview, and
    #: guessing which column held the phone number is how you import 300
    #: members under the wrong numbers.
    missing_columns: list[str]
    truncated: bool = False

    @property
    def importable(self) -> list[ImportRow]:
        return [r for r in self.rows if r.ok]


def decode(raw: bytes) -> str:
    """UTF-8 first (with or without Excel's byte-order mark), then cp1256.

    cp1256 is the Windows Arabic code page, and it is what an older Excel
    on an Arabic Windows install writes by default. Without this fallback
    a file full of Arabic names decodes into nothing usable and the gym is
    told their export is broken when it is perfectly ordinary.
    """
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        # errors="replace" rather than another raise: one bad byte in a
        # 300-row file should cost that one name, not the whole import.
        return raw.decode("cp1256", errors="replace")


def normalize_phone(value: str) -> str | None:
    """A Lebanese mobile number in one shape, or None if it cannot be one.

    Accepts the forms people actually type: 03 123456, 70/123 456,
    +961 3 123456, 0096170123456, (03) 123-456. Returns +961 followed by
    7 or 8 digits, which is what every other phone in this product looks
    like — the WhatsApp links depend on it (app/domain/whatsapp.py).
    """
    digits = "".join(ch for ch in value if ch.isdigit())
    if not digits:
        return None

    if digits.startswith("00961"):
        national = digits[5:]
    elif digits.startswith("961"):
        national = digits[3:]
    elif digits.startswith("0"):
        # A local trunk prefix: 03 123456 is the same number as +961 3 123456.
        national = digits[1:]
    else:
        national = digits

    # Lebanese mobiles are 7 digits (03 X XX XX XX) or 8 (70/71/76/78/79/81).
    if len(national) not in (7, 8):
        return None
    return f"+961{national}"


#: Day-first, because that is how dates are written in Lebanon. An
#: ambiguous 03/04/2026 is the 3rd of April here, never the 4th of March.
_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d")


def parse_date(value: str) -> date | None:
    text = value.strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _column_map(header: list[str]) -> dict[str, int]:
    """Which position each known field sits at. A column the file does not
    have simply does not appear."""
    found: dict[str, int] = {}
    for index, raw in enumerate(header):
        cleaned = raw.strip().lower().lstrip("﻿")
        for field_name, aliases in COLUMN_ALIASES.items():
            if field_name in found:
                continue
            if cleaned in aliases:
                found[field_name] = index
                break
    return found


def parse_rows(text: str) -> ParsedFile:
    """Normalize every line, attaching per-row errors rather than stopping.

    A file with one bad row is not a broken file: the manager fixes that
    row in the preview and imports the rest. Only a header with no name or
    phone column stops everything, because then there is nothing to show.
    """
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return ParsedFile(rows=[], missing_columns=["name", "phone"])

    columns = _column_map(header)
    missing = [name for name in ("name", "phone") if name not in columns]
    if missing:
        return ParsedFile(rows=[], missing_columns=missing)

    def cell(row: list[str], key: str) -> str:
        index = columns.get(key)
        if index is None or index >= len(row):
            return ""
        return row[index].strip()

    rows: list[ImportRow] = []
    seen_phones: set[str] = set()
    truncated = False

    for offset, raw_row in enumerate(reader):
        if len(rows) >= MAX_ROWS:
            truncated = True
            break
        if not any(c.strip() for c in raw_row):
            continue  # a blank line at the end of the file is not a row

        line = offset + 2  # +1 for the header, +1 because spreadsheets are 1-based
        name = cell(raw_row, "name")
        raw_phone = cell(raw_row, "phone")
        phone = normalize_phone(raw_phone) or ""
        raw_ends = cell(raw_row, "ends_at")
        ends_at = parse_date(raw_ends)

        errors: list[str] = []
        if not name:
            errors.append(ERROR_NAME_MISSING)
        if not raw_phone:
            errors.append(ERROR_PHONE_MISSING)
        elif not phone:
            errors.append(ERROR_PHONE_INVALID)
        elif phone in seen_phones:
            errors.append(ERROR_DUPLICATE_IN_FILE)
        if raw_ends and ends_at is None:
            errors.append(ERROR_DATE_INVALID)

        if phone:
            seen_phones.add(phone)

        rows.append(
            ImportRow(
                line=line,
                name=name,
                # Falls back to whatever they wrote: both columns are
                # NOT NULL, and an English column is rarer than an Arabic
                # one in a real export.
                name_en=cell(raw_row, "name_en") or name,
                phone=phone,
                plan=cell(raw_row, "plan"),
                ends_at=ends_at,
                errors=errors,
            )
        )

    return ParsedFile(rows=rows, missing_columns=[], truncated=truncated)
