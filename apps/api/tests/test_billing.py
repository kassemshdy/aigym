"""What we charge a gym, and the wall between that and the gym's own data.

The structural test is the one that matters: `gyms` has no Row-Level
Security to lean on, and no role helps either — app/api/onboarding.py
grants super_admin to every gym's first account, so the owner would pass
any role check on their own billing row. The only thing keeping billing
away from customers is which fields the staff-facing response models
select, and a human remembering that is not a guarantee. So the test walks
the whole OpenAPI schema instead.
"""

import itertools
import uuid
from typing import Any

from httpx import AsyncClient

from app.main import create_app

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"
OPERATOR = {"X-Onboarding-Secret": ONBOARDING_SECRET}
_counter = itertools.count(1)

BILLING_FIELDS = {"billing_status", "monthly_usd", "paid_through", "billing_notes"}

#: The only paths allowed to mention billing. Everything else in the app is
#: reachable with a staff or member token.
OPERATOR_PATHS = {"/gyms", "/gyms/{gym_id}/billing"}


async def _onboard(client: AsyncClient, *, slug: str, username: str | None = None) -> dict:
    response = await client.post(
        "/gyms",
        headers=OPERATOR,
        json={
            "name_ar": "نادي", "name_en": "Gym", "slug": slug,
            "manager_name": "Owner",
            "manager_username": username or f"owner-{slug}",
            "manager_password": "hunter22",
            "manager_phone": f"+96179{next(_counter):06d}",
        },
    )
    body: dict = response.json()
    body["_status"] = response.status_code
    return body


def _property_names(schema: Any, components: dict[str, Any], seen: set[str]) -> set[str]:
    """Every property name reachable from a response schema, following
    $ref, arrays and any/all/oneOf. Recursive because a nested model is
    exactly how a field leaks without anyone noticing."""
    if not isinstance(schema, dict):
        return set()

    ref = schema.get("$ref")
    if isinstance(ref, str):
        name = ref.rsplit("/", 1)[-1]
        if name in seen:
            return set()
        seen.add(name)
        return _property_names(components.get(name, {}), components, seen)

    names: set[str] = set()
    properties = schema.get("properties")
    if isinstance(properties, dict):
        names |= set(properties)
        for child in properties.values():
            names |= _property_names(child, components, seen)
    for key in ("items", "additionalProperties"):
        names |= _property_names(schema.get(key), components, seen)
    for key in ("anyOf", "allOf", "oneOf"):
        for child in schema.get(key, []) or []:
            names |= _property_names(child, components, seen)
    return names


def test_no_customer_facing_response_mentions_billing() -> None:
    """A future engineer adding monthly_usd to GymOut for a 'small
    convenience' fails here rather than shipping it."""
    spec = create_app().openapi()
    components: dict[str, Any] = spec.get("components", {}).get("schemas", {})

    checked = 0
    for path, operations in spec["paths"].items():
        if path in OPERATOR_PATHS:
            continue
        for method, operation in operations.items():
            for response in operation.get("responses", {}).values():
                schema = (
                    response.get("content", {}).get("application/json", {}).get("schema")
                )
                if schema is None:
                    continue
                checked += 1
                leaked = _property_names(schema, components, set()) & BILLING_FIELDS
                assert not leaked, f"{method.upper()} {path} exposes {sorted(leaked)}"

    assert checked > 30, "the walk found almost nothing — the spec shape changed"


async def test_gyms_me_still_answers_branding_only(client: AsyncClient) -> None:
    """The same rule from the other side: an actual request, with an actual
    staff token, over the wire."""
    await _onboard(client, slug="billing-branding")
    login = await client.post(
        "/auth/staff/login",
        json={"username": "owner-billing-branding", "password": "hunter22"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    body = (await client.get("/gyms/me", headers=headers)).json()
    assert set(body) == {"id", "name", "slug", "logo_key"}
    assert not set(body) & BILLING_FIELDS


# ------------------------------------------------------- provisioning


async def test_onboarding_returns_enough_to_hand_over_a_login(
    client: AsyncClient,
) -> None:
    created = await _onboard(client, slug="prov-ok")
    assert created["_status"] == 201, created
    assert created["slug"] == "prov-ok"
    assert created["manager_username"] == "owner-prov-ok"
    uuid.UUID(created["staff_user_id"])

    # And it works.
    login = await client.post(
        "/auth/staff/login", json={"username": "owner-prov-ok", "password": "hunter22"}
    )
    assert login.status_code == 200, login.text


async def test_a_duplicate_slug_is_a_409_not_a_500(client: AsyncClient) -> None:
    """Both of these are unique constraints that used to raise an
    IntegrityError at commit — outside the handler, reaching the operator
    as a crash with nothing to act on."""
    await _onboard(client, slug="prov-dupe")
    again = await _onboard(client, slug="prov-dupe", username="someone-else")
    assert again["_status"] == 409, again
    assert "slug" in again["detail"].lower()


async def test_a_duplicate_username_is_a_409_across_every_gym(
    client: AsyncClient,
) -> None:
    """staff_users has no RLS and usernames are unique platform-wide
    (decision 16), so this collides even though the gyms are different."""
    await _onboard(client, slug="prov-u-a", username="shared-name")
    clash = await _onboard(client, slug="prov-u-b", username="shared-name")
    assert clash["_status"] == 409, clash
    assert "username" in clash["detail"].lower()

    # The second gym was not half-created.
    listed = await client.get("/gyms", headers=OPERATOR)
    assert "prov-u-b" not in {g["slug"] for g in listed.json()}


# ------------------------------------------------------------ billing


async def test_a_new_gym_starts_on_trial_with_nothing_agreed(
    client: AsyncClient,
) -> None:
    created = await _onboard(client, slug="bill-new")
    billing = await client.get(f"/gyms/{created['gym_id']}/billing", headers=OPERATOR)
    assert billing.status_code == 200, billing.text
    assert billing.json()["billing_status"] == "trial"
    assert billing.json()["monthly_usd"] is None
    assert billing.json()["paid_through"] is None


async def test_the_operator_records_and_then_clears_what_was_agreed(
    client: AsyncClient,
) -> None:
    created = await _onboard(client, slug="bill-edit")
    gym_id = created["gym_id"]

    agreed = await client.patch(
        f"/gyms/{gym_id}/billing",
        headers=OPERATOR,
        json={
            "billing_status": "active", "monthly_usd": 40,
            "paid_through": "2026-12-31", "billing_notes": "Cash, monthly, collected in person",
        },
    )
    assert agreed.status_code == 200, agreed.text
    assert agreed.json()["monthly_usd"] == 40.0
    assert agreed.json()["paid_through"] == "2026-12-31"

    # A status change alone leaves the rest alone.
    lapsed = await client.patch(
        f"/gyms/{gym_id}/billing", headers=OPERATOR, json={"billing_status": "past_due"}
    )
    assert lapsed.json()["billing_status"] == "past_due"
    assert lapsed.json()["monthly_usd"] == 40.0

    # An explicit null clears, which is what a cancellation needs.
    cancelled = await client.patch(
        f"/gyms/{gym_id}/billing",
        headers=OPERATOR,
        json={"billing_status": "cancelled", "paid_through": None, "monthly_usd": None},
    )
    assert cancelled.json()["paid_through"] is None
    assert cancelled.json()["monthly_usd"] is None
    assert cancelled.json()["billing_notes"] == "Cash, monthly, collected in person"


async def test_an_invented_billing_status_is_refused(client: AsyncClient) -> None:
    created = await _onboard(client, slug="bill-status")
    refused = await client.patch(
        f"/gyms/{created['gym_id']}/billing",
        headers=OPERATOR,
        json={"billing_status": "vibes"},
    )
    assert refused.status_code == 422


async def test_a_gym_owner_cannot_reach_their_own_billing(client: AsyncClient) -> None:
    """The point of gating on the secret rather than a role: super_admin
    means owner of this gym, and an owner would happily pass a role check
    on the row that says what they owe us."""
    created = await _onboard(client, slug="bill-owner")
    login = await client.post(
        "/auth/staff/login", json={"username": "owner-bill-owner", "password": "hunter22"}
    )
    owner = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert (await client.get("/gyms", headers=owner)).status_code == 401
    assert (
        await client.get(f"/gyms/{created['gym_id']}/billing", headers=owner)
    ).status_code == 401
    assert (
        await client.patch(
            f"/gyms/{created['gym_id']}/billing",
            headers=owner,
            json={"monthly_usd": 0, "billing_status": "active"},
        )
    ).status_code == 401


async def test_the_operator_list_covers_every_gym(client: AsyncClient) -> None:
    await _onboard(client, slug="bill-list-a")
    await _onboard(client, slug="bill-list-b")
    listed = await client.get("/gyms", headers=OPERATOR)
    assert listed.status_code == 200, listed.text
    slugs = {g["slug"] for g in listed.json()}
    assert {"bill-list-a", "bill-list-b"} <= slugs
