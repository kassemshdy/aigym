"""One shape for a Lebanese phone number, wherever one enters the system.

Pure: a string in, a string or None out. No HTTP, no SQLAlchemy — same
convention as dues.py and analytics.py.

This function was written inside csv_import.py, for a notebook export. It
belongs here because the shape is not about CSV. A member typing their own
number into the login screen, a manager adding a member at the front desk,
and a 300-row spreadsheet all have to agree on what "the same number"
means. When they do not, the failure is the worst kind: the login endpoint
finds nobody, says `sent: true` anyway because it must not leak whether a
number is a member's (decision 20), and the member sits waiting for a code
that was never addressed to them. Decision 44.
"""


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
