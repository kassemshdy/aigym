"""Decision 10's authority mechanism, the dispatch half: interprets an
ai_plan_drafts.payload and says what it would write, without writing
anything itself — the route (app/api/ai_drafts.py) performs the actual
insert/update, same "domain decides, route does I/O" split as
workout.py/dues.py. A kind='tip' draft carries no payload; approving one
only changes its status.
"""

import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProgramExerciseSpec:
    exercise_id: uuid.UUID
    sets: int
    reps: dict[str, Any]
    target_weight_kg: float | None = None


@dataclass(frozen=True)
class ProgramExerciseUpdate:
    title: dict[str, Any]
    exercises: list[ProgramExerciseSpec]


@dataclass(frozen=True)
class CalorieTargetUpdate:
    daily_kcal_target: int


def apply_draft(
    payload: dict[str, Any] | None,
) -> ProgramExerciseUpdate | CalorieTargetUpdate | None:
    if payload is None:
        return None

    payload_type = payload.get("type")
    if payload_type == "program_exercise_update":
        return ProgramExerciseUpdate(
            title=payload["title"],
            exercises=[
                ProgramExerciseSpec(
                    exercise_id=uuid.UUID(str(item["exercise_id"])),
                    sets=int(item["sets"]),
                    reps=item["reps"],
                    target_weight_kg=(
                        float(item["target_weight_kg"])
                        if item.get("target_weight_kg") is not None
                        else None
                    ),
                )
                for item in payload["exercises"]
            ],
        )
    if payload_type == "calorie_target_update":
        return CalorieTargetUpdate(daily_kcal_target=int(payload["daily_kcal_target"]))
    return None
