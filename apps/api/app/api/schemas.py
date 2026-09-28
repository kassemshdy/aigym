"""Request models shared by more than one endpoint module.

Small on purpose: this is not a dumping ground for every schema, only the
ones two routers would otherwise define twice and let drift apart.
"""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from app.domain.phone import normalize_phone


class BilingualName(BaseModel):
    """Both languages required.

    Looser than the `dict[str, Any]` the exercise and video endpoints take,
    deliberately: those carry seeded content, while a gym owner types the
    ones validated here — and a name saved with only English renders as a
    blank on the Arabic side of the app rather than failing anywhere
    visible.
    """

    ar: Annotated[str, Field(min_length=1, max_length=60)]
    en: Annotated[str, Field(min_length=1, max_length=60)]


def _canonical_phone(value: str) -> str:
    phone = normalize_phone(value)
    if phone is None:
        raise ValueError("not a phone number: outside Lebanon, include the country code")
    return phone


#: A phone number stored in one shape, whoever typed it (decision 44). The
#: value that reaches the route is already `+` and digits (`+961…` for a
#: Lebanese number, decision 49 for any other), so the roster, the
#: WhatsApp links and the member's own login all compare equal.
#:
#: A number that cannot be one becomes a 422 naming the field, rather than
#: a row nobody can ever reach: `wa_link` would build wa.me/03123456 and
#: the member's login would never match. The two `/auth/member/*` endpoints
#: deliberately do *not* use this — one must always answer `sent: true` and
#: the other always 401, so neither can say anything about the input.
PhoneNumber = Annotated[str, AfterValidator(_canonical_phone)]
