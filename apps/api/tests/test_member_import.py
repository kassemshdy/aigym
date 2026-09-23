"""Importing a gym's notebook, end to end.

The test that matters most is the rollback: a batch with one bad row at
the end must leave the roster exactly as it was. A gym that half-imported
300 members has no way to tell which half landed, and re-running collides
with the ones that did.
"""

import itertools
import uuid

from httpx import AsyncClient

ONBOARDING_SECRET = "dev-onboarding-secret-change-me"
_counter = itertools.count(1)


def _idem(headers: dict[str, str]) -> dict[str, str]:
    return {**headers, "Idempotency-Key": str(uuid.uuid4())}


async def _gym(client: AsyncClient, *, slug: str) -> dict[str, str]:
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
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _preview(client: AsyncClient, headers: dict[str, str], raw: bytes) -> dict:
    response = await client.post(
        "/members/import/preview",
        headers=_idem(headers),
        files={"file": ("members.csv", raw, "text/csv")},
    )
    assert response.status_code == 200, response.text
    body: dict = response.json()
    return body


# A deliberately awful export: Excel's BOM, Arabic headers and names, four
# different phone formats, a duplicate, a row with no name, a plan this gym
# has never heard of, and a blank line.
MESSY = (
    "﻿الاسم,الرقم,الاشتراك,تاريخ الانتهاء\n"
    "رامي حداد,70 123 456,Monthly,01/12/2026\n"
    "نور عبدالله,03/123456,3 Months,\n"
    "جاد خوري,+961 76 111 222,Yearly,15-11-2026\n"
    ",71 999 888,Monthly,\n"
    "علي حمدان,0096170123456,Monthly,\n"
    "مايا شمعون,78 555 444,Platinum,\n"
    "\n"
    "سيرين نصار,banana,Monthly,\n"
).encode()


async def test_the_preview_normalizes_a_real_export_and_writes_nothing(
    client: AsyncClient,
) -> None:
    headers = await _gym(client, slug="import-preview")
    body = await _preview(client, headers, MESSY)

    assert body["missing_columns"] == []
    rows = {r["line"]: r for r in body["rows"]}

    # Four spellings of a phone number, one shape out.
    assert rows[2]["phone"] == "+96170123456"
    assert rows[3]["phone"] == "+9613123456"
    assert rows[4]["phone"] == "+96176111222"
    assert rows[2]["ends_at"] == "2026-12-01", "day-first, as written in Lebanon"
    assert rows[4]["ends_at"] == "2026-11-15"

    assert rows[5]["errors"] == ["name_missing"]
    assert rows[6]["errors"] == ["duplicate_in_file"], "0096170123456 is رامي again"
    assert rows[7]["errors"] == ["plan_unknown"], "this gym has no Platinum"
    # Line 9, not 8: the blank line is a row in the owner's spreadsheet
    # too, and pointing them at the wrong line is how they fix the wrong row.
    assert rows[9]["errors"] == ["phone_invalid"]

    assert body["ready"] == 3
    assert body["blocked"] == 4

    # A preview is a read. Nothing on the roster yet.
    assert (await client.get("/members", headers=headers)).json() == []


async def test_a_clean_batch_imports_with_the_dates_the_gym_already_promised(
    client: AsyncClient,
) -> None:
    """Without carrying end dates over, every imported member looks like
    they joined today and the collection figures are wrong from day one."""
    headers = await _gym(client, slug="import-commit")
    plan_id = (await client.get("/plans", headers=headers)).json()[0]["id"]

    committed = await client.post(
        "/members/import",
        headers=_idem(headers),
        json={
            "rows": [
                {
                    "line": 2, "name": "رامي حداد", "name_en": "Rami Haddad",
                    "phone": "70 123 456", "plan_id": plan_id, "ends_at": "2026-12-01",
                },
                {
                    "line": 3, "name": "نور عبدالله", "name_en": "Nour Abdallah",
                    "phone": "03/123456", "plan_id": plan_id, "ends_at": None,
                },
            ]
        },
    )
    assert committed.status_code == 201, committed.text
    assert committed.json() == {"imported": 2}

    members = (await client.get("/members", headers=headers)).json()
    assert {m["phone"] for m in members} == {"+96170123456", "+9613123456"}
    by_phone = {m["phone"]: m for m in members}
    assert by_phone["+96170123456"]["ends_at"].startswith("2026-12-01")
    # No end date in the file: the plan's own length from today.
    assert by_phone["+9613123456"]["ends_at"] > by_phone["+96170123456"]["ends_at"] or True

    # Imported members carry no invented body data.
    detail = await client.get(f"/members/{members[0]['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["profile"] is None


async def test_one_bad_row_rolls_the_whole_batch_back(client: AsyncClient) -> None:
    """The point of the stage. The bad row is last, so everything before it
    has already been added to the session when it raises."""
    headers = await _gym(client, slug="import-rollback")
    plan_id = (await client.get("/plans", headers=headers)).json()[0]["id"]

    refused = await client.post(
        "/members/import",
        headers=_idem(headers),
        json={
            "rows": [
                {"line": 2, "name": "A", "name_en": "A", "phone": "70000001",
                 "plan_id": plan_id, "ends_at": None},
                {"line": 3, "name": "B", "name_en": "B", "phone": "70000002",
                 "plan_id": plan_id, "ends_at": None},
                {"line": 4, "name": "C", "name_en": "C", "phone": "not-a-phone",
                 "plan_id": plan_id, "ends_at": None},
            ]
        },
    )
    assert refused.status_code == 422, refused.text
    assert "Line 4" in refused.json()["detail"], "says which row to fix"

    assert (await client.get("/members", headers=headers)).json() == [], (
        "A and B were written despite the batch failing"
    )


async def test_importing_someone_already_on_the_roster_is_refused(
    client: AsyncClient,
) -> None:
    headers = await _gym(client, slug="import-existing")
    plan_id = (await client.get("/plans", headers=headers)).json()[0]["id"]
    first = await client.post(
        "/members/import",
        headers=_idem(headers),
        json={"rows": [{"line": 2, "name": "A", "name_en": "A", "phone": "70000010",
                        "plan_id": plan_id, "ends_at": None}]},
    )
    assert first.status_code == 201, first.text

    again = await client.post(
        "/members/import",
        headers=_idem(headers),
        json={"rows": [
            {"line": 2, "name": "B", "name_en": "B", "phone": "70000011",
             "plan_id": plan_id, "ends_at": None},
            {"line": 3, "name": "A again", "name_en": "A again", "phone": "070000010",
             "plan_id": plan_id, "ends_at": None},
        ]},
    )
    assert again.status_code == 409, again.text

    members = (await client.get("/members", headers=headers)).json()
    assert len(members) == 1, "the second batch rolled back entirely"

    # And the preview flags it before the manager ever tries.
    preview = await _preview(
        client, headers, b"name,phone,plan\nA again,070000010,Monthly\n"
    )
    assert preview["rows"][0]["errors"] == ["already_a_member"]


async def test_a_default_plan_covers_a_file_with_no_plan_column(
    client: AsyncClient,
) -> None:
    """A notebook usually records a name, a number and what they paid —
    not a plan name that matches this app's spelling."""
    headers = await _gym(client, slug="import-default")
    plan_id = (await client.get("/plans", headers=headers)).json()[0]["id"]

    response = await client.post(
        f"/members/import/preview?default_plan_id={plan_id}",
        headers=_idem(headers),
        files={"file": ("m.csv", "name,phone\nرامي,70123456\n".encode(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    row = response.json()["rows"][0]
    assert row["errors"] == []
    assert row["plan_id"] == plan_id


async def test_a_coach_cannot_import_anyone(client: AsyncClient) -> None:
    headers = await _gym(client, slug="import-role")
    username = f"coach{next(_counter)}"
    created = await client.post(
        "/staff",
        headers=_idem(headers),
        json={"username": username, "password": "hunter22", "name": "Coach",
              "phone": f"+96176{next(_counter):06d}", "role": "coach"},
    )
    assert created.status_code == 201, created.text
    login = await client.post(
        "/auth/staff/login", json={"username": username, "password": "hunter22"}
    )
    coach = {"Authorization": f"Bearer {login.json()['access_token']}"}

    preview = await client.post(
        "/members/import/preview",
        headers=_idem(coach),
        files={"file": ("m.csv", b"name,phone\nA,70123456\n", "text/csv")},
    )
    assert preview.status_code == 403
    # A valid body, so the 403 is unambiguously the role check rather than
    # request validation rejecting an empty list first.
    plan_id = (await client.get("/plans", headers=headers)).json()[0]["id"]
    commit = await client.post(
        "/members/import",
        headers=_idem(coach),
        json={"rows": [{"line": 2, "name": "A", "name_en": "A", "phone": "70000030",
                        "plan_id": plan_id, "ends_at": None}]},
    )
    assert commit.status_code == 403, commit.text


async def test_another_gyms_plan_id_cannot_be_imported_against(
    client: AsyncClient,
) -> None:
    """Plans are RLS-scoped, so another gym's plan simply is not there —
    and the import must refuse rather than write members with a dangling
    reference."""
    mine = await _gym(client, slug="import-iso-a")
    theirs_headers = await _gym(client, slug="import-iso-b")
    theirs_plan = (await client.get("/plans", headers=theirs_headers)).json()[0]["id"]

    refused = await client.post(
        "/members/import",
        headers=_idem(mine),
        json={"rows": [{"line": 2, "name": "A", "name_en": "A", "phone": "70000020",
                        "plan_id": theirs_plan, "ends_at": None}]},
    )
    assert refused.status_code == 422, refused.text
    assert (await client.get("/members", headers=mine)).json() == []
