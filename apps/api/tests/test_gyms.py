"""The gym's own name and logo.

Two things here are load-bearing beyond the happy path: that GET /gyms/me
returns branding and nothing else (stage 12 puts billing on this same
table), and that `gyms` having no Row-Level Security does not mean one gym
can read or write another's row.
"""

import itertools
import uuid

from httpx import AsyncClient

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"
_counter = itertools.count(1)

# A 1x1 PNG, so POST /media has something real to store.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c63000100000500010d0a2db4000000"
    "0049454e44ae426082"
)


def _idem(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


async def _gym(client: AsyncClient, *, slug: str) -> tuple[uuid.UUID, dict[str, str]]:
    username = f"owner-{slug}"
    onboard = await client.post(
        "/gyms",
        headers={"X-Onboarding-Secret": ONBOARDING_SECRET},
        json={
            "name_ar": "نادي", "name_en": "Gym", "slug": slug,
            "manager_name": "Owner", "manager_username": username,
            "manager_password": "hunter22", "manager_phone": f"+96179{next(_counter):06d}",
        },
    )
    assert onboard.status_code == 201, onboard.text
    login = await client.post(
        "/auth/staff/login", json={"username": username, "password": "hunter22"}
    )
    return (
        uuid.UUID(onboard.json()["gym_id"]),
        {"Authorization": f"Bearer {login.json()['access_token']}"},
    )


async def _upload(client: AsyncClient, headers: dict[str, str]) -> str:
    uploaded = await client.post(
        "/media",
        headers=_idem(headers),
        files={"file": ("logo.png", PNG, "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    key: str = uploaded.json()["key"]
    return key


async def test_gyms_me_returns_branding_and_nothing_else(client: AsyncClient) -> None:
    """Pinned to an exact key set on purpose. Stage 12 adds billing columns
    to this same table, and a response model widened by accident is how
    "what we charge the gym" ends up readable by the gym."""
    gym_id, headers = await _gym(client, slug="brand-a")

    body = (await client.get("/gyms/me", headers=headers)).json()
    assert set(body) == {"id", "name", "slug", "logo_key"}
    assert body["id"] == str(gym_id)
    assert body["name"] == {"ar": "نادي", "en": "Gym"}
    assert body["logo_key"] is None, "a new gym has no logo and the client falls back"


async def test_an_owner_renames_the_gym(client: AsyncClient) -> None:
    _gym_id, headers = await _gym(client, slug="brand-rename")

    renamed = await client.patch(
        "/gyms/me",
        headers=_idem(headers),
        json={"name": {"ar": "نادي تريبل إي", "en": "Triple A Gym"}},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == {"ar": "نادي تريبل إي", "en": "Triple A Gym"}
    assert renamed.json()["slug"] == "brand-rename", "the slug is not the name"


async def test_a_name_in_one_language_is_refused(client: AsyncClient) -> None:
    _gym_id, headers = await _gym(client, slug="brand-onelang")
    refused = await client.patch(
        "/gyms/me", headers=_idem(headers), json={"name": {"en": "Triple A Gym"}}
    )
    assert refused.status_code == 422


async def test_a_logo_round_trips_through_the_media_route(client: AsyncClient) -> None:
    """The gap this stage closes: a logo_key matches neither a progress
    photo nor a food entry, so GET /media/{key} used to 404 on one."""
    _gym_id, headers = await _gym(client, slug="brand-logo")
    key = await _upload(client, headers)

    # Before it is the gym's logo, the key is an orphan nobody may read.
    assert (await client.get(f"/media/{key}", headers=headers)).status_code == 404

    saved = await client.patch("/gyms/me", headers=_idem(headers), json={"logo_key": key})
    assert saved.status_code == 200, saved.text
    assert saved.json()["logo_key"] == key

    served = await client.get(f"/media/{key}", headers=headers)
    assert served.status_code == 200, served.text
    assert served.headers["content-type"] == "image/png"
    assert served.content == PNG


async def test_a_logo_can_be_cleared(client: AsyncClient) -> None:
    """An explicit null means remove it. Every other PATCH in this service
    reads None as "not provided", so this one needs model_fields_set or a
    gym could set a logo and never take it off."""
    _gym_id, headers = await _gym(client, slug="brand-clear")
    key = await _upload(client, headers)
    await client.patch("/gyms/me", headers=_idem(headers), json={"logo_key": key})

    cleared = await client.patch("/gyms/me", headers=_idem(headers), json={"logo_key": None})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["logo_key"] is None

    # And the image stops being readable, since nothing references it now.
    assert (await client.get(f"/media/{key}", headers=headers)).status_code == 404


async def test_a_rename_alone_leaves_the_logo_alone(client: AsyncClient) -> None:
    """The other half of the model_fields_set rule: omitting logo_key must
    not read as clearing it."""
    _gym_id, headers = await _gym(client, slug="brand-partial")
    key = await _upload(client, headers)
    await client.patch("/gyms/me", headers=_idem(headers), json={"logo_key": key})

    renamed = await client.patch(
        "/gyms/me", headers=_idem(headers), json={"name": {"ar": "جديد", "en": "New"}}
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["logo_key"] == key


async def test_a_logo_key_that_names_nothing_is_refused(client: AsyncClient) -> None:
    """Otherwise the header of every screen on every surface renders a
    broken image with nothing to say why."""
    _gym_id, headers = await _gym(client, slug="brand-badkey")

    for bad in ("not-a-key", f"{uuid.uuid4().hex}.png", "../../etc/passwd"):
        refused = await client.patch(
            "/gyms/me", headers=_idem(headers), json={"logo_key": bad}
        )
        assert refused.status_code == 422, f"{bad} was accepted: {refused.text}"


async def test_a_coach_reads_the_branding_but_cannot_change_it(client: AsyncClient) -> None:
    _gym_id, headers = await _gym(client, slug="brand-role")
    username = f"coach{next(_counter)}"
    created = await client.post(
        "/staff",
        headers=_idem(headers),
        json={
            "username": username, "password": "hunter22", "name": "Coach",
            "phone": f"+96176{next(_counter):06d}", "role": "coach",
        },
    )
    assert created.status_code == 201, created.text
    login = await client.post(
        "/auth/staff/login", json={"username": username, "password": "hunter22"}
    )
    coach = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # The gym name is in the header on the coach's iPad too.
    assert (await client.get("/gyms/me", headers=coach)).status_code == 200
    refused = await client.patch(
        "/gyms/me", headers=_idem(coach), json={"name": {"ar": "x", "en": "x"}}
    )
    assert refused.status_code == 403


async def test_one_gyms_branding_is_never_another_gyms(client: AsyncClient) -> None:
    """`gyms` carries no RLS (decision 16), so these endpoints filter on
    the token's gym_id by hand. This is the test that says the hand-written
    filter is actually there."""
    gym_a, headers_a = await _gym(client, slug="brand-iso-a")
    gym_b, headers_b = await _gym(client, slug="brand-iso-b")

    key_b = await _upload(client, headers_b)
    await client.patch("/gyms/me", headers=_idem(headers_b), json={"logo_key": key_b})
    await client.patch(
        "/gyms/me", headers=_idem(headers_a), json={"name": {"ar": "أ", "en": "A"}}
    )

    a_sees = (await client.get("/gyms/me", headers=headers_a)).json()
    assert a_sees["id"] == str(gym_a)
    assert a_sees["logo_key"] is None, "gym B's logo is not gym A's"

    b_sees = (await client.get("/gyms/me", headers=headers_b)).json()
    assert b_sees["id"] == str(gym_b)
    assert b_sees["name"] == {"ar": "نادي", "en": "Gym"}, "gym A's rename stayed at gym A"

    # And gym A cannot fetch gym B's logo bytes by guessing the key.
    assert (await client.get(f"/media/{key_b}", headers=headers_a)).status_code == 404
    assert (await client.get(f"/media/{key_b}", headers=headers_b)).status_code == 200
