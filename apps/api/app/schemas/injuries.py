"""The shape `MemberProfile.injuries` (raw JSONB) is validated against at
the API boundary. Used by the members API and by the guardrail domain
logic (app/domain/guardrails.py, Phase 5 stage 3), which needs a stable
`body_part` key to intersect against an exercise's risk tags — free text
plus per-turn LLM judgment would defeat "checked in code, not requested
in the prompt." See docs/DECISIONS.md, decision 30.
"""

from typing import Literal

from pydantic import BaseModel

BodyPart = Literal[
    "lower_back",
    "knee_left",
    "knee_right",
    "shoulder_left",
    "shoulder_right",
    "hip",
    "neck",
    "wrist",
    "ankle",
    "other",
]

Severity = Literal["mild", "moderate", "severe"]


class MemberInjury(BaseModel):
    body_part: BodyPart
    note: dict[str, str]
    severity: Severity | None = None
