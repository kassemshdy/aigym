from datetime import UTC, datetime

from app.domain.ai_context import (
    CatalogExerciseRow,
    CatalogVideoRow,
    FoodEntryRow,
    MemberContextRow,
    RecentSessionRow,
    build_system_prompt,
)
from app.schemas.injuries import MemberInjury

_PROFILE = MemberContextRow(
    goal="strength", level="mid", height_cm=178, weight_kg=80.0, body_fat=18.0,
    injuries=[MemberInjury(body_part="knee_right", note={"ar": "ركبة", "en": "Knee"})],
    days_per_week=4, job="desk", sleep_hours=6.5, daily_kcal_target=2200,
)


def _prompt(**overrides):
    kwargs = {
        "persona_instructions": "You are the nutrition assistant.",
        "lang": "en",
        "exercises": [CatalogExerciseRow(name={"ar": "سكوات", "en": "Squat"}, muscle_group="legs")],
        "videos": [CatalogVideoRow(title={"ar": "فيديو", "en": "Video"}, muscle_group="legs")],
        "profile": _PROFILE,
        "recent_sessions": [],
        "today_food": [],
    }
    kwargs.update(overrides)
    return build_system_prompt(**kwargs)


def test_returns_exactly_two_blocks() -> None:
    blocks = _prompt()
    assert len(blocks) == 2


def test_only_the_first_block_carries_a_cache_breakpoint() -> None:
    blocks = _prompt()
    assert blocks[0].get("cache_control") == {"type": "ephemeral"}
    assert "cache_control" not in blocks[1]


def test_stable_block_contains_persona_and_catalog_never_member_data() -> None:
    blocks = _prompt()
    stable = blocks[0]["text"]
    assert "You are the nutrition assistant." in stable
    assert "Squat" in stable
    assert "Video" in stable
    # Nothing member-specific (weight, injuries) belongs in the cached prefix.
    assert "80.0" not in stable
    assert "Knee" not in stable


def test_volatile_block_contains_member_data_never_the_catalog() -> None:
    blocks = _prompt()
    volatile = blocks[1]["text"]
    assert "80.0" in volatile
    assert "knee_right" in volatile
    assert "Squat" not in volatile
    assert "You are the nutrition assistant." not in volatile


def test_volatile_block_picks_the_requested_language_for_injury_notes() -> None:
    ar_blocks = _prompt(lang="ar")
    assert "ركبة" in ar_blocks[1]["text"]
    en_blocks = _prompt(lang="en")
    assert "Knee" in en_blocks[1]["text"]


def test_no_injuries_says_so_explicitly() -> None:
    no_injury_profile = MemberContextRow(
        goal="health", level="new", height_cm=165, weight_kg=60.0, body_fat=None,
        injuries=[], days_per_week=2, job="active", sleep_hours=8.0, daily_kcal_target=None,
    )
    blocks = _prompt(profile=no_injury_profile)
    assert "no recorded injuries" in blocks[1]["text"]


def test_recent_sessions_and_today_food_render_in_the_volatile_block() -> None:
    blocks = _prompt(
        recent_sessions=[
            RecentSessionRow(
                started_at=datetime(2026, 9, 1, tzinfo=UTC), finished_at=None,
                effort_band="hard", exercise_names=["Squat", "Bench Press"],
            )
        ],
        today_food=[FoodEntryRow(label="Chicken and rice", kcal=620, protein=45, carbs=68, fat=14)],
    )
    volatile = blocks[1]["text"]
    assert "Squat, Bench Press" in volatile
    assert "hard" in volatile
    assert "Chicken and rice: 620 kcal" in volatile


def test_empty_sessions_and_food_say_so_explicitly() -> None:
    blocks = _prompt()
    volatile = blocks[1]["text"]
    assert "none logged yet" in volatile
    assert "nothing logged yet today" in volatile
