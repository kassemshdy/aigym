"""One shape for a phone number, wherever one enters the system.

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

It used to accept Lebanese mobiles only, which refused a member with a
foreign SIM outright — and a gym has those. Decision 49 kept the one
stored shape (+ and digits, which is what WhatsApp links are built from)
and widened what is accepted: any number written with its country code.
"""

#: E.164 caps a number at 15 digits including the country code. The floor
#: is a sanity check, not a rule: no real mobile with its country code is
#: shorter than this, and anything shorter is a typo.
MIN_INTERNATIONAL_DIGITS = 8
MAX_INTERNATIONAL_DIGITS = 15


def normalize_phone(value: str) -> str | None:
    """A phone number as + and digits, or None if it cannot be one.

    Lebanese forms need no country code, because that is how people here
    write them: 03 123456, 70/123 456, +961 3 123456, 0096170123456,
    (03) 123-456 all become +961 followed by 7 or 8 digits.

    Anything else must carry its country code, written with + or 00
    (+33 6 12 34 56 78, 0044 7700 900123). Without one there is no telling
    which country a bare foreign number belongs to, and guessing stores a
    number nobody can reach.
    """
    written = value.strip()
    digits = "".join(ch for ch in written if ch.isdigit())
    if not digits:
        return None

    international = written.startswith("+") or digits.startswith("00")
    if digits.startswith("00"):
        digits = digits[2:]

    if digits.startswith("961") and (international or len(digits) in (10, 11)):
        national = digits[3:]
        # +961 with the wrong length is a mistyped Lebanese number, not a
        # number in some other country — refuse it rather than store it.
        return f"+961{national}" if len(national) in (7, 8) else None

    if international:
        if MIN_INTERNATIONAL_DIGITS <= len(digits) <= MAX_INTERNATIONAL_DIGITS:
            return f"+{digits}"
        return None

    # A local trunk prefix: 03 123456 is the same number as +961 3 123456.
    national = digits[1:] if digits.startswith("0") else digits
    # Lebanese mobiles are 7 digits (03 X XX XX XX) or 8 (70/71/76/78/79/81).
    if len(national) in (7, 8):
        return f"+961{national}"
    return None
