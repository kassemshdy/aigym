"""Roadmap Phase 5's safety rule: "injury contraindications and a calorie
floor are checked before a reply is sent, not requested in the prompt."
Every function here is pure — no HTTP, no SQLAlchemy, no Anthropic client
— the caller (app/ai/gather.py, app/api/chat.py) fetches rows and hands
them in, same convention as dues.py/workout.py. The point of keeping this
deterministic is exactly what decision 10 already established for the
`draft` flag: the model can propose, but code decides whether the
proposal is safe to write anywhere.
"""

import re
from dataclasses import dataclass

from app.schemas.injuries import MemberInjury

# A member's weight, in kg, times this factor is the absolute floor no
# proposed calorie target may go below — a conservative rule-of-thumb
# minimum, not a personalized recommendation.
_KCAL_PER_KG_FLOOR = 10
_ABSOLUTE_KCAL_FLOOR = 1200


@dataclass(frozen=True)
class GuardrailResult:
    blocked: bool
    reason: dict[str, str] | None = None


# muscle_group -> (name pattern, risk tags). An exercise whose muscle_group
# matches and whose (English) name matches the pattern is treated as
# contraindicated for a member with any of the listed injuries. Deliberately
# no Exercise.contraindication column — this is a small, hand-maintained
# table, cheaper than a migration and easy to extend as real gym data shows
# gaps.
_EXERCISE_RISK_RULES: list[tuple[str, re.Pattern[str], frozenset[str]]] = [
    ("legs", re.compile(r"squat|leg press|lunge", re.I),
     frozenset({"knee_left", "knee_right", "lower_back", "hip"})),
    ("legs", re.compile(r"deadlift", re.I), frozenset({"lower_back", "hip"})),
    ("back", re.compile(r"deadlift|row|pull", re.I),
     frozenset({"lower_back", "shoulder_left", "shoulder_right"})),
    ("chest", re.compile(r"bench|press|fly", re.I),
     frozenset({"shoulder_left", "shoulder_right"})),
    ("shoulders", re.compile(r".*"),
     frozenset({"shoulder_left", "shoulder_right", "neck"})),
]

_INJURY_REPLY = {
    "ar": "هاد التمرين ممكن يأثر على إصابة مسجلة عندك — احكي مع الكوتش قبل ما تجربه.",
    "en": "This exercise may aggravate a recorded injury — check with your coach before trying it.",
}


def resolve_exercise_risk_tags(*, muscle_group: str, name_en: str) -> frozenset[str]:
    tags: set[str] = set()
    for group, pattern, risk_tags in _EXERCISE_RISK_RULES:
        if group == muscle_group and pattern.search(name_en):
            tags |= risk_tags
    return frozenset(tags)


def check_injury_contraindication(
    injuries: list[MemberInjury], *, muscle_group: str, name_en: str
) -> GuardrailResult:
    risk_tags = resolve_exercise_risk_tags(muscle_group=muscle_group, name_en=name_en)
    if any(injury.body_part in risk_tags for injury in injuries):
        return GuardrailResult(blocked=True, reason=_INJURY_REPLY)
    return GuardrailResult(blocked=False)


def calorie_floor(weight_kg: float) -> int:
    return max(_ABSOLUTE_KCAL_FLOOR, round(_KCAL_PER_KG_FLOOR * weight_kg))


def check_calorie_floor(*, weight_kg: float, proposed_kcal: int) -> GuardrailResult:
    floor = calorie_floor(weight_kg)
    if proposed_kcal >= floor:
        return GuardrailResult(blocked=False)
    return GuardrailResult(
        blocked=True,
        reason={
            "ar": f"هيدا الرقم تحت الحد الآمن ({floor} سعرة) — ما بقدر اقترحه من دون الكوتش.",
            "en": f"That's below a safe floor of {floor} kcal — "
                  "I can't suggest it without your coach.",
        },
    )


# A deterministic pre-filter that runs *before* any Claude call — catches
# the obvious cases for free (no API spend, no risk of the model answering
# anyway) and short-circuits app/api/chat.py's flow entirely. The
# structured reply schema (stage 7) also carries a model-set `referred`
# field for the cases this regex misses; either signal makes the route
# swap in REFERRAL_TEXT, never the model's own prose.
_MEDICAL_PATTERN = re.compile(
    r"chest pain|shortness of breath|can'?t breathe|dizz|faint|medication|"
    r"prescri|diagnos|numbness|"
    r"ألم في الصدر|صعوبة (في )?التنفس|دوخة|إغماء|دواء|وصفة طبية|تشخيص|تنميل",
    re.I,
)

REFERRAL_TEXT = {
    "ar": "هاد سؤال طبي وما بقدر جاوب عليه — احكي مع طبيبك أو مع الكوتش أساف مباشرة.",
    "en": "That's a medical question I can't answer — "
          "please talk to a doctor or Coach Assaf directly.",
}


def is_obviously_medical(text: str) -> bool:
    return bool(_MEDICAL_PATTERN.search(text))
