"""Changing and revoking staff access — the gaps decision 25 named.

The interesting assertions here are not the happy paths. They are: that a
demoted manager's *existing session* stops working, that a gym can never be
left without a super_admin, and that revoking someone at one gym leaves the
same person's access at another gym completely alone.
"""

import itertools
import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.db import tenant_session
from app.models import StaffGymRole, StaffUser

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"
_counter = itertools.count(1)


def _idem(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


class Gym:
    def __init__(self, gym_id: uuid.UUID, username: str, headers: dict[str, str]) -> None:
        self.gym_id = gym_id
        self.username = username
        self.headers = headers


async def _onboard(client: AsyncClient, *, slug: str) -> Gym:
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
    return Gym(uuid.UUID(onboard.json()["gym_id"]), username, await _headers(client, username))


async def _headers(
    client: AsyncClient, username: str, password: str = "hunter22"
) -> dict[str, str]:
    login = await client.post(
        "/auth/staff/login", json={"username": username, "password": password}
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _tokens(client: AsyncClient, username: str, password: str = "hunter22") -> dict[str, str]:
    login = await client.post(
        "/auth/staff/login", json={"username": username, "password": password}
    )
    assert login.status_code == 200, login.text
    pair: dict[str, str] = login.json()
    return pair


async def _create(
    client: AsyncClient, headers: dict[str, str], *, username: str, role: str
) -> uuid.UUID:
    created = await client.post(
        "/staff",
        headers=_idem(headers),
        json={
            "username": username, "password": "hunter22", "name": username.title(),
            "phone": f"+96176{next(_counter):06d}", "role": role,
        },
    )
    assert created.status_code == 201, created.text
    return uuid.UUID(created.json()["id"])


async def _role_row(gym_id: uuid.UUID, staff_user_id: uuid.UUID) -> StaffGymRole | None:
    async with tenant_session(gym_id) as session:
        return (
            await session.execute(
                select(StaffGymRole).where(StaffGymRole.staff_user_id == staff_user_id)
            )
        ).scalar_one_or_none()


# --------------------------------------------------------------- role changes


async def test_a_super_admin_promotes_a_coach_to_manager(client: AsyncClient) -> None:
    gym = await _onboard(client, slug="roles-a")
    coach_id = await _create(client, gym.headers, username="karim", role="coach")

    changed = await client.patch(
        f"/staff/{coach_id}", headers=_idem(gym.headers), json={"role": "manager"}
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["role"] == "manager"

    listing = await client.get("/staff", headers=gym.headers)
    assert {row["username"]: row["role"] for row in listing.json()}["karim"] == "manager"


async def test_a_manager_cannot_change_anyones_role(client: AsyncClient) -> None:
    """Not an omission of the flat-roles trap: a manager promoting a coach
    would be handing out access they were never given authority to hand
    out, and demoting a peer is worse. There is nothing left for them to
    do here, so the endpoint is closed rather than half-open."""
    gym = await _onboard(client, slug="roles-b")
    await _create(client, gym.headers, username="nour", role="manager")
    coach_id = await _create(client, gym.headers, username="abed", role="coach")

    manager_headers = await _headers(client, "nour")
    refused = await client.patch(
        f"/staff/{coach_id}", headers=_idem(manager_headers), json={"role": "manager"}
    )
    assert refused.status_code == 403


async def test_a_coach_cannot_reach_any_of_this(client: AsyncClient) -> None:
    gym = await _onboard(client, slug="roles-c")
    coach_id = await _create(client, gym.headers, username="sami", role="coach")
    coach_headers = await _headers(client, "sami")

    assert (
        await client.patch(
            f"/staff/{coach_id}", headers=_idem(coach_headers), json={"role": "manager"}
        )
    ).status_code == 403
    assert (
        await client.delete(f"/staff/{coach_id}", headers=_idem(coach_headers))
    ).status_code == 403
    assert (
        await client.post(f"/staff/{coach_id}/password/reset", headers=_idem(coach_headers))
    ).status_code == 403


# ------------------------------------------------- the last-super_admin floor


async def test_the_only_super_admin_cannot_step_down(client: AsyncClient) -> None:
    """A gym with no super_admin can never grant a role again — nobody left
    is allowed to reach this endpoint, and there is no operator UI to
    repair it from."""
    gym = await _onboard(client, slug="floor-a")
    owner_id = (await client.get("/staff", headers=gym.headers)).json()[0]["id"]

    refused = await client.patch(
        f"/staff/{owner_id}", headers=_idem(gym.headers), json={"role": "manager"}
    )
    assert refused.status_code == 409, refused.text

    refused_delete = await client.delete(f"/staff/{owner_id}", headers=_idem(gym.headers))
    assert refused_delete.status_code == 409


async def test_a_super_admin_can_step_down_once_a_second_one_exists(
    client: AsyncClient,
) -> None:
    gym = await _onboard(client, slug="floor-b")
    owner_id = (await client.get("/staff", headers=gym.headers)).json()[0]["id"]
    await _create(client, gym.headers, username="rita", role="super_admin")

    stepped_down = await client.patch(
        f"/staff/{owner_id}", headers=_idem(gym.headers), json={"role": "manager"}
    )
    assert stepped_down.status_code == 200, stepped_down.text
    assert stepped_down.json()["role"] == "manager"


# ------------------------------------------- the session a role change leaves


async def test_a_role_change_kills_the_refresh_token(client: AsyncClient) -> None:
    """The whole point of the stage. Without this, a demoted manager keeps
    manager access for up to refresh_token_days (30) on the token already
    in their hand, because /auth/refresh copies the role forward from the
    old token's claims rather than re-reading staff_gym_roles."""
    gym = await _onboard(client, slug="revoke-a")
    coach_id = await _create(client, gym.headers, username="tony", role="coach")
    coach_tokens = await _tokens(client, "tony")

    still_good = await client.post(
        "/auth/refresh", json={"refresh_token": coach_tokens["refresh_token"]}
    )
    assert still_good.status_code == 200, "sanity: the token works before the change"
    rotated = still_good.json()["refresh_token"]

    changed = await client.patch(
        f"/staff/{coach_id}", headers=_idem(gym.headers), json={"role": "manager"}
    )
    assert changed.status_code == 200, changed.text

    dead = await client.post("/auth/refresh", json={"refresh_token": rotated})
    assert dead.status_code == 401


async def test_re_sending_the_same_role_does_not_sign_anyone_out(
    client: AsyncClient,
) -> None:
    """A UI that PATCHes a whole form would otherwise log someone out for
    saving a screen without touching the role control."""
    gym = await _onboard(client, slug="revoke-b")
    coach_id = await _create(client, gym.headers, username="layla", role="coach")
    coach_tokens = await _tokens(client, "layla")

    noop = await client.patch(
        f"/staff/{coach_id}", headers=_idem(gym.headers), json={"role": "coach"}
    )
    assert noop.status_code == 200

    still_good = await client.post(
        "/auth/refresh", json={"refresh_token": coach_tokens["refresh_token"]}
    )
    assert still_good.status_code == 200


async def test_revoking_access_kills_the_refresh_token_too(client: AsyncClient) -> None:
    gym = await _onboard(client, slug="revoke-c")
    coach_id = await _create(client, gym.headers, username="jad", role="coach")
    coach_tokens = await _tokens(client, "jad")

    removed = await client.delete(f"/staff/{coach_id}", headers=_idem(gym.headers))
    assert removed.status_code == 204, removed.text

    dead = await client.post(
        "/auth/refresh", json={"refresh_token": coach_tokens["refresh_token"]}
    )
    assert dead.status_code == 401


async def test_revoking_one_persons_access_leaves_their_colleagues_signed_in(
    client: AsyncClient,
) -> None:
    """The obvious bug in a revocation query is forgetting to narrow it to
    the one person — and it hides well, because the target is signed out
    correctly either way. This is the assertion that catches it."""
    gym = await _onboard(client, slug="revoke-d")
    leaving_id = await _create(client, gym.headers, username="leaving", role="coach")
    await _create(client, gym.headers, username="staying", role="coach")
    staying_tokens = await _tokens(client, "staying")

    removed = await client.delete(f"/staff/{leaving_id}", headers=_idem(gym.headers))
    assert removed.status_code == 204, removed.text

    alive = await client.post(
        "/auth/refresh", json={"refresh_token": staying_tokens["refresh_token"]}
    )
    assert alive.status_code == 200, "the colleague on shift keeps working"


# ------------------------------------------------------------ revoking access


async def test_a_manager_removes_a_coach_but_not_a_peer(client: AsyncClient) -> None:
    gym = await _onboard(client, slug="remove-a")
    await _create(client, gym.headers, username="mira", role="manager")
    peer_id = await _create(client, gym.headers, username="wael", role="manager")
    coach_id = await _create(client, gym.headers, username="ziad", role="coach")

    manager_headers = await _headers(client, "mira")

    assert (
        await client.delete(f"/staff/{peer_id}", headers=_idem(manager_headers))
    ).status_code == 403
    removed = await client.delete(f"/staff/{coach_id}", headers=_idem(manager_headers))
    assert removed.status_code == 204, removed.text

    listing = (await client.get("/staff", headers=gym.headers)).json()
    usernames = {row["username"] for row in listing}
    assert "ziad" not in usernames
    assert "wael" in usernames


async def test_revoking_access_keeps_the_account_and_the_other_gyms_role(
    client: AsyncClient,
) -> None:
    """StaffUser is global and StaffGymRole is per-gym, and this is the
    reason that split exists: one person coaching at two gyms must not
    lose the second when the first lets them go."""
    gym_b = await _onboard(client, slug="shared-b")
    coach_id = await _create(client, gym_b.headers, username="shared-coach", role="coach")
    coach_tokens = await _tokens(client, "shared-coach")

    # Granted a second role directly: there is no endpoint for adding an
    # existing account to another gym, which is stage 12's operator work.
    gym_a = await _onboard(client, slug="shared-a")
    async with tenant_session(gym_a.gym_id) as session:
        session.add(StaffGymRole(gym_id=gym_a.gym_id, staff_user_id=coach_id, role="coach"))

    removed = await client.delete(f"/staff/{coach_id}", headers=_idem(gym_a.headers))
    assert removed.status_code == 204, removed.text

    assert await _role_row(gym_a.gym_id, coach_id) is None, "gone from the gym that removed them"
    kept = await _role_row(gym_b.gym_id, coach_id)
    assert kept is not None and kept.role == "coach", "untouched at the other gym"

    async with tenant_session(None) as session:
        account = await session.get(StaffUser, coach_id)
    assert account is not None, "the account itself is never deleted"

    # refresh_tokens is gym-scoped, so gym A's revocation cannot reach the
    # session they hold at gym B.
    alive = await client.post(
        "/auth/refresh", json={"refresh_token": coach_tokens["refresh_token"]}
    )
    assert alive.status_code == 200, alive.text


async def test_another_gyms_staff_id_is_a_404_not_a_403(client: AsyncClient) -> None:
    """A 403 would confirm the id is real. One gym has no business learning
    who is on another's payroll."""
    gym_a = await _onboard(client, slug="cross-a")
    gym_b = await _onboard(client, slug="cross-b")
    theirs = await _create(client, gym_b.headers, username="theirs", role="coach")

    assert (
        await client.patch(
            f"/staff/{theirs}", headers=_idem(gym_a.headers), json={"role": "manager"}
        )
    ).status_code == 404
    assert (
        await client.delete(f"/staff/{theirs}", headers=_idem(gym_a.headers))
    ).status_code == 404
    assert (
        await client.post(f"/staff/{theirs}/password/reset", headers=_idem(gym_a.headers))
    ).status_code == 404


# ----------------------------------------------------------- password resets


async def test_a_manager_resets_a_coachs_password(client: AsyncClient) -> None:
    gym = await _onboard(client, slug="pw-a")
    await _create(client, gym.headers, username="boss", role="manager")
    coach_id = await _create(client, gym.headers, username="rami", role="coach")
    coach_tokens = await _tokens(client, "rami")

    manager_headers = await _headers(client, "boss")
    reset = await client.post(
        f"/staff/{coach_id}/password/reset", headers=_idem(manager_headers)
    )
    assert reset.status_code == 200, reset.text
    new_password = reset.json()["password"]
    assert reset.json()["username"] == "rami"
    assert reset.json()["phone"].startswith("+961"), "the manager needs it to send the password"

    old = await client.post(
        "/auth/staff/login", json={"username": "rami", "password": "hunter22"}
    )
    assert old.status_code == 401, "the old password stops working"

    fresh = await client.post(
        "/auth/staff/login", json={"username": "rami", "password": new_password}
    )
    assert fresh.status_code == 200, fresh.text

    dead = await client.post(
        "/auth/refresh", json={"refresh_token": coach_tokens["refresh_token"]}
    )
    assert dead.status_code == 401, "the session open on their phone ends too"


async def test_a_manager_cannot_reset_a_peers_password(client: AsyncClient) -> None:
    """Handing a manager another manager's new password is account takeover
    of a peer, not administration."""
    gym = await _onboard(client, slug="pw-b")
    await _create(client, gym.headers, username="one", role="manager")
    peer_id = await _create(client, gym.headers, username="two", role="manager")

    manager_headers = await _headers(client, "one")
    refused = await client.post(
        f"/staff/{peer_id}/password/reset", headers=_idem(manager_headers)
    )
    assert refused.status_code == 403


async def test_an_admin_reset_does_not_rate_limit_the_self_service_one(
    client: AsyncClient,
) -> None:
    """staff_users.password_reset_at belongs to the unauthenticated endpoint.
    Writing it here would mean a manager helping a coach silently locks that
    coach out of self-service for the cooldown."""
    gym = await _onboard(client, slug="pw-c")
    coach_id = await _create(client, gym.headers, username="selfserve", role="coach")

    admin_reset = await client.post(
        f"/staff/{coach_id}/password/reset", headers=_idem(gym.headers)
    )
    assert admin_reset.status_code == 200

    self_serve = await client.post(
        "/auth/staff/password/reset", json={"username": "selfserve"}
    )
    assert self_serve.status_code == 200, self_serve.text
