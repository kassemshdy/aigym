"""Composes already-fetched rows into the two-part system prompt the chat
assistants send Claude (app/api/chat.py, stage 7) — pure, no HTTP/
SQLAlchemy/Anthropic-client awareness, same convention as dues.py/
workout.py/guardrails.py. The fetching half (app/ai/gather.py) is
deliberately impure and lives outside this module.

Two blocks, split at a cache_control breakpoint, per the claude-api
skill's caching guidance (stable content first, tools -> system ->
messages order):

  1. Cache-stable block: identical for every member at this gym, every
     turn — the persona/authority instructions the caller supplies, plus
     the gym's exercise and video catalogs.
  2. Volatile block, after the breakpoint: this member's own
     profile/injuries/recent sessions/today's food — changes every turn
     and every member, so it must never sit inside the cached prefix.

Caching only pays off once the stable block clears the model's minimum
cacheable prefix (a few hundred to a few thousand tokens depending on
model) — for a small gym's catalog that may simply not activate; verify
with usage.cache_read_input_tokens on real traffic, not assumed from
design (docs/DECISIONS.md, decision 29).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import TypedDict

from app.schemas.injuries import MemberInjury


class TextBlock(TypedDict, total=False):
    type: str
    text: str
    cache_control: dict[str, str]


@dataclass(frozen=True)
class MemberContextRow:
    goal: str
    level: str
    height_cm: int
    weight_kg: float
    body_fat: float | None
    injuries: list[MemberInjury]
    days_per_week: int
    job: str
    sleep_hours: float
    daily_kcal_target: int | None


@dataclass(frozen=True)
class RecentSessionRow:
    started_at: datetime
    finished_at: datetime | None
    effort_band: str | None
    exercise_names: list[str]


@dataclass(frozen=True)
class FoodEntryRow:
    label: str
    kcal: int
    protein: int
    carbs: int
    fat: int


@dataclass(frozen=True)
class CatalogExerciseRow:
    name: dict[str, str]
    muscle_group: str


@dataclass(frozen=True)
class CatalogVideoRow:
    title: dict[str, str]
    muscle_group: str


_JOB_LABEL = {
    "ar": {"desk": "مكتبي", "active": "حركة", "shift": "ورديات"},
    "en": {"desk": "desk job", "active": "active job", "shift": "shift work"},
}


def _format_catalog(
    exercises: list[CatalogExerciseRow], videos: list[CatalogVideoRow], lang: str
) -> str:
    lines = ["Gym exercise catalog:"]
    for e in exercises:
        lines.append(f"- {e.name.get(lang, e.name.get('en', ''))} ({e.muscle_group})")
    lines.append("")
    lines.append("Coach Assaf's technique videos:")
    for v in videos:
        lines.append(f"- {v.title.get(lang, v.title.get('en', ''))} ({v.muscle_group})")
    return "\n".join(lines)


def _format_member_data(
    profile: MemberContextRow,
    recent_sessions: list[RecentSessionRow],
    today_food: list[FoodEntryRow],
    lang: str,
) -> str:
    lines = ["Member profile:"]
    lines.append(f"- goal: {profile.goal}, level: {profile.level}")
    lines.append(f"- height: {profile.height_cm} cm, weight: {profile.weight_kg} kg")
    if profile.body_fat is not None:
        lines.append(f"- body fat: {profile.body_fat}%")
    lines.append(f"- trains {profile.days_per_week} days/week, {_JOB_LABEL[lang][profile.job]}")
    lines.append(f"- sleeps {profile.sleep_hours} hours/night")
    if profile.daily_kcal_target is not None:
        lines.append(f"- daily calorie target: {profile.daily_kcal_target} kcal")
    if profile.injuries:
        injury_notes = ", ".join(
            f"{i.body_part} ({i.note.get(lang, i.note.get('en', ''))})" for i in profile.injuries
        )
        lines.append(f"- recorded injuries: {injury_notes}")
    else:
        lines.append("- no recorded injuries")

    lines.append("")
    lines.append("Recent workout sessions (most recent first):")
    if recent_sessions:
        for s in recent_sessions:
            status = "finished" if s.finished_at else "in progress"
            effort = f", effort: {s.effort_band}" if s.effort_band else ""
            exercises = ", ".join(s.exercise_names) if s.exercise_names else "no sets logged"
            lines.append(f"- {s.started_at.date().isoformat()} ({status}{effort}): {exercises}")
    else:
        lines.append("- none logged yet")

    lines.append("")
    lines.append("Today's food so far:")
    if today_food:
        for f in today_food:
            lines.append(f"- {f.label}: {f.kcal} kcal, {f.protein}g protein")
    else:
        lines.append("- nothing logged yet today")

    return "\n".join(lines)


def build_system_prompt(
    *,
    persona_instructions: str,
    lang: str,
    exercises: list[CatalogExerciseRow],
    videos: list[CatalogVideoRow],
    profile: MemberContextRow,
    recent_sessions: list[RecentSessionRow],
    today_food: list[FoodEntryRow],
) -> list[TextBlock]:
    stable_text = f"{persona_instructions}\n\n{_format_catalog(exercises, videos, lang)}"
    volatile_text = _format_member_data(profile, recent_sessions, today_food, lang)
    return [
        {"type": "text", "text": stable_text, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": volatile_text},
    ]
