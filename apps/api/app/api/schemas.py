"""Request models shared by more than one endpoint module.

Small on purpose: this is not a dumping ground for every schema, only the
ones two routers would otherwise define twice and let drift apart.
"""

from typing import Annotated

from pydantic import BaseModel, Field


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
